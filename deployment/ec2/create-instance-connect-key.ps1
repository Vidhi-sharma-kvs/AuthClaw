param(
    [string]$InstanceId = "i-00e9ebbdd70f0d488",
    [string]$AvailabilityZone = "us-east-1d",
    [string]$Region = "us-east-1",
    [string]$SshUser = "ubuntu",
    [string]$OutputKeyPath = "deployment/ec2/generated/eic-temp-key"
)

$ErrorActionPreference = "Stop"

function Resolve-AwsCli {
    $command = Get-Command aws -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $defaultPath = "C:\Program Files\Amazon\AWSCLIV2\aws.exe"
    if (Test-Path $defaultPath) {
        return $defaultPath
    }

    throw "AWS CLI is not installed or not available. Install it with: winget install --id Amazon.AWSCLI -e"
}

if (-not (Get-Command ssh-keygen -ErrorAction SilentlyContinue)) {
    throw "OpenSSH ssh-keygen is not available in PATH."
}

if (-not $InstanceId) { throw "Required: -InstanceId" }
if (-not $AvailabilityZone) { throw "Required: -AvailabilityZone" }

$AwsCli = Resolve-AwsCli
$keyDirectory = Split-Path -Parent $OutputKeyPath
if ($keyDirectory -and -not (Test-Path $keyDirectory)) {
    New-Item -ItemType Directory -Path $keyDirectory | Out-Null
}

$privateKeyPath = (Join-Path (Resolve-Path $keyDirectory).Path (Split-Path -Leaf $OutputKeyPath))
$publicKeyPath = "$privateKeyPath.pub"

Remove-Item -LiteralPath $privateKeyPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $publicKeyPath -Force -ErrorAction SilentlyContinue

ssh-keygen -t ed25519 -N "" -f $privateKeyPath -C "authclaw-eic-temp" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "ssh-keygen failed to create a temporary key."
}

$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
icacls.exe $privateKeyPath /inheritance:r | Out-Null
icacls.exe $privateKeyPath /grant:r "${currentUser}:R" | Out-Null

Write-Host "Sending temporary EC2 Instance Connect public key..."
& $AwsCli ec2-instance-connect send-ssh-public-key `
    --region $Region `
    --instance-id $InstanceId `
    --availability-zone $AvailabilityZone `
    --instance-os-user $SshUser `
    --ssh-public-key "file://$publicKeyPath" | Out-Host

if ($LASTEXITCODE -ne 0) {
    throw "EC2 Instance Connect failed. Confirm your IAM user has ec2-instance-connect:SendSSHPublicKey permission and the instance supports EC2 Instance Connect."
}

Write-Host ""
Write-Host "Temporary SSH key created and pushed."
Write-Host "Use it immediately; EC2 Instance Connect keys expire quickly."
Write-Host ""
Write-Host "Deploy command:"
Write-Host ".\deployment\ec2\deploy-app-to-ec2.ps1 -Ec2PublicIp 100.30.237.231 -SshKeyPath `"$privateKeyPath`""
