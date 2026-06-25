param(
    [string]$SshKeyPath = ".\authclaw-key.pem",
    [string]$Ec2PublicIp = "100.30.237.231",
    [string]$SshUser = "ubuntu",
    [switch]$CopyToUserSsh
)

$ErrorActionPreference = "Stop"

function Get-CurrentUserSid {
    return [System.Security.Principal.WindowsIdentity]::GetCurrent().User
}

function Set-OwnerOnlyReadAcl {
    param([string]$Path)

    $resolvedPath = (Resolve-Path $Path).Path
    $currentSid = Get-CurrentUserSid

    takeown.exe /F $resolvedPath | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "takeown failed for $resolvedPath with exit code $LASTEXITCODE. Run PowerShell as Administrator."
    }

    $acl = Get-Acl -LiteralPath $resolvedPath
    $acl.SetOwner($currentSid)
    $acl.SetAccessRuleProtection($true, $false)

    foreach ($rule in @($acl.Access)) {
        [void]$acl.RemoveAccessRuleAll($rule)
    }

    $ownerReadRule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        $currentSid,
        [System.Security.AccessControl.FileSystemRights]::Read,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
    $acl.AddAccessRule($ownerReadRule)
    Set-Acl -LiteralPath $resolvedPath -AclObject $acl

    return $resolvedPath
}

function Test-OpenSshKey {
    param([string]$Path)

    ssh-keygen.exe -y -f $Path | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Test-Ec2Ssh {
    param(
        [string]$Path,
        [string]$User,
        [string]$HostName
    )

    ssh.exe `
        -o StrictHostKeyChecking=accept-new `
        -o ConnectTimeout=20 `
        -o BatchMode=yes `
        -i $Path `
        "${User}@${HostName}" `
        "echo authclaw-ssh-ok"

    return ($LASTEXITCODE -eq 0)
}

if (-not (Test-Path $SshKeyPath)) {
    throw "SSH key not found: $SshKeyPath"
}

if (-not (Get-Command ssh-keygen.exe -ErrorAction SilentlyContinue)) {
    throw "ssh-keygen.exe is not available in PATH."
}

if (-not (Get-Command ssh.exe -ErrorAction SilentlyContinue)) {
    throw "ssh.exe is not available in PATH."
}

$resolvedKeyPath = (Resolve-Path $SshKeyPath).Path
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

Write-Host "Repairing SSH key permissions for Windows OpenSSH"
Write-Host "  Key:  $resolvedKeyPath"
Write-Host "  User: $currentUser"
Write-Host ""

$fixedKeyPath = Set-OwnerOnlyReadAcl -Path $resolvedKeyPath

Write-Host "Owner-only ACL applied:"
icacls.exe $fixedKeyPath | Out-Host

Write-Host ""
Write-Host "Validating key format with ssh-keygen..."
$keyIsReadable = Test-OpenSshKey -Path $fixedKeyPath

if (-not $keyIsReadable -and $CopyToUserSsh) {
    $sshDirectory = Join-Path $env:USERPROFILE ".ssh"
    if (-not (Test-Path $sshDirectory)) {
        New-Item -ItemType Directory -Path $sshDirectory | Out-Null
    }

    $fallbackKeyPath = Join-Path $sshDirectory (Split-Path -Leaf $fixedKeyPath)
    Copy-Item -LiteralPath $fixedKeyPath -Destination $fallbackKeyPath -Force
    $fixedKeyPath = Set-OwnerOnlyReadAcl -Path $fallbackKeyPath

    Write-Host ""
    Write-Host "Fallback copy created with owner-only ACL:"
    Write-Host "  $fixedKeyPath"
    icacls.exe $fixedKeyPath | Out-Host

    Write-Host ""
    Write-Host "Validating fallback key format with ssh-keygen..."
    $keyIsReadable = Test-OpenSshKey -Path $fixedKeyPath
}

if (-not $keyIsReadable) {
    throw @"
OpenSSH can read the file ACL now, but the key content is not a valid private key format.

Expected first line should be one of:
  -----BEGIN RSA PRIVATE KEY-----
  -----BEGIN OPENSSH PRIVATE KEY-----

This usually means the .pem file was overwritten, copied incorrectly, downloaded as HTML/text, or is not the private half of the EC2 key pair.
"@
}

Write-Host "Key format is valid."
Write-Host ""
Write-Host "Testing SSH to ${SshUser}@${Ec2PublicIp}..."

if (Test-Ec2Ssh -Path $fixedKeyPath -User $SshUser -HostName $Ec2PublicIp) {
    Write-Host ""
    Write-Host "SSH key permissions repaired successfully."
    Write-Host "Use this key path:"
    Write-Host "  $fixedKeyPath"
}
else {
    throw @"
The key file is now accepted by OpenSSH, but EC2 rejected it with Permission denied (publickey).

That means this private key does not match the public key installed on the EC2 instance for user '$SshUser'.
Do not regenerate the instance yet; use EC2 Instance Connect or confirm the correct original private key for key pair 'authclaw-key'.
"@
}
