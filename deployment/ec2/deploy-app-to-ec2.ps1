param(
    [string]$Ec2PublicIp,
    [string]$SshKeyPath,
    [string]$SshUser = "ubuntu",
    [string]$DatabasePassword,
    [string]$SmtpPassword,
    [string]$SmtpFrom,
    [string]$GoogleApiKey = "",
    [string]$GeneratedDirectory = "deployment/ec2/generated",
    [switch]$SkipEnvGeneration
)

$ErrorActionPreference = "Stop"

function Read-SecretValue($Prompt) {
    $secure = Read-Host -Prompt $Prompt -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    }
    finally {
        if ($ptr -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
        }
    }
}

function Invoke-NativeChecked {
    param(
        [string]$Command,
        [string[]]$Arguments
    )

    $oldErrorPreference = $ErrorActionPreference
    $oldNativePreference = $null
    $hasNativePreference = Test-Path Variable:\PSNativeCommandUseErrorActionPreference
    $script:ErrorActionPreference = "Continue"
    if ($hasNativePreference) {
        $oldNativePreference = $PSNativeCommandUseErrorActionPreference
        $script:PSNativeCommandUseErrorActionPreference = $false
    }

    try {
        & $Command @Arguments
        $exitCode = $LASTEXITCODE
    }
    finally {
        $script:ErrorActionPreference = $oldErrorPreference
        if ($hasNativePreference) {
            $script:PSNativeCommandUseErrorActionPreference = $oldNativePreference
        }
    }

    if ($exitCode -ne 0) {
        throw "$Command failed with exit code $exitCode"
    }
}

function Invoke-SshScript {
    param(
        [string]$Script,
        [string[]]$Arguments
    )

    $oldErrorPreference = $ErrorActionPreference
    $oldNativePreference = $null
    $hasNativePreference = Test-Path Variable:\PSNativeCommandUseErrorActionPreference
    $script:ErrorActionPreference = "Continue"
    if ($hasNativePreference) {
        $oldNativePreference = $PSNativeCommandUseErrorActionPreference
        $script:PSNativeCommandUseErrorActionPreference = $false
    }

    try {
        $Script | ssh @Arguments
        $exitCode = $LASTEXITCODE
    }
    finally {
        $script:ErrorActionPreference = $oldErrorPreference
        if ($hasNativePreference) {
            $script:PSNativeCommandUseErrorActionPreference = $oldNativePreference
        }
    }

    if ($exitCode -ne 0) {
        throw "ssh failed with exit code $exitCode"
    }
}

if (-not $Ec2PublicIp) { throw "Required: -Ec2PublicIp" }
if (-not $SshKeyPath) { throw "Required: -SshKeyPath" }
if (-not (Test-Path $SshKeyPath)) { throw "SSH key not found: $SshKeyPath" }
$ResolvedSshKeyPath = (Resolve-Path $SshKeyPath).Path

if (-not (Get-Command ssh -ErrorAction SilentlyContinue)) { throw "OpenSSH ssh is not available in PATH." }
if (-not (Get-Command scp -ErrorAction SilentlyContinue)) { throw "OpenSSH scp is not available in PATH." }
if (-not (Get-Command tar -ErrorAction SilentlyContinue)) { throw "tar is not available in PATH." }
if (-not (Get-Command ssh-keygen -ErrorAction SilentlyContinue)) { throw "OpenSSH ssh-keygen is not available in PATH." }

try {
    $publicKey = & ssh-keygen -y -f $ResolvedSshKeyPath
    $keyExitCode = $LASTEXITCODE
    if ($keyExitCode -ne 0 -or -not $publicKey) {
        throw "ssh-keygen failed with exit code $keyExitCode"
    }
}
catch {
    throw @"
OpenSSH cannot read the SSH private key:
  $ResolvedSshKeyPath

Fix it from an Administrator PowerShell:
  .\deployment\ec2\repair-ssh-key-permissions.ps1 -SshKeyPath "$ResolvedSshKeyPath"

Then rerun deploy-app-to-ec2.ps1.

Original error:
$($_.Exception.Message)
"@
}

$sshOptions = @(
    "-o", "StrictHostKeyChecking=accept-new",
    "-o", "ConnectTimeout=30",
    "-o", "ServerAliveInterval=30",
    "-o", "ServerAliveCountMax=4"
)

if (-not (Test-Path $GeneratedDirectory)) {
    New-Item -ItemType Directory -Path $GeneratedDirectory | Out-Null
}

if (-not $SkipEnvGeneration) {
    if (-not $DatabasePassword) {
        $DatabasePassword = Read-SecretValue "Local PostgreSQL password to create on EC2"
    }
    if (-not $SmtpPassword) {
        $SmtpPassword = Read-SecretValue "SendGrid API key"
    }
    if (-not $SmtpFrom) {
        $SmtpFrom = Read-Host -Prompt "Verified SendGrid sender email"
    }
    if (-not $GoogleApiKey) {
        $GoogleApiKey = Read-SecretValue "Google Gemini API key"
    }

    & "deployment/ec2/generate-runtime-env.ps1" `
        -Ec2PublicIp $Ec2PublicIp `
        -UseLocalPostgres `
        -DatabasePassword $DatabasePassword `
        -SmtpPassword $SmtpPassword `
        -SmtpFrom $SmtpFrom `
        -GoogleApiKey $GoogleApiKey `
        -OutputDirectory $GeneratedDirectory
}

$backendEnv = Join-Path $GeneratedDirectory "backend.env"
$frontendEnv = Join-Path $GeneratedDirectory "frontend.env.production"
$archivePath = Join-Path $GeneratedDirectory "authclaw-source.tar.gz"

if (-not (Test-Path $backendEnv)) { throw "Missing generated backend env: $backendEnv" }
if (-not (Test-Path $frontendEnv)) { throw "Missing generated frontend env: $frontendEnv" }
if (Test-Path $archivePath) { Remove-Item -LiteralPath $archivePath -Force }

$root = (Resolve-Path ".").Path
$excludedTopLevelNames = @(
    ".git",
    ".agents",
    ".codex",
    "venv",
    ".venv",
    "node_modules",
    "dist",
    "authclaw-key.pem",
    ".env",
    ".aws",
    "credentials",
    "config"
)
$excludedTopLevelExtensions = @(".pem", ".ppk", ".key", ".crt", ".env")

Write-Host "Selecting source entries without private keys or generated secrets..."
$sourceEntries = Get-ChildItem -LiteralPath $root -Force |
    Where-Object {
        $name = $_.Name
        if ($excludedTopLevelNames -contains $name) { return $false }
        if ($_.PSIsContainer) { return $true }
        if ($excludedTopLevelExtensions -contains $_.Extension.ToLowerInvariant()) { return $false }
        if ($name -like ".env.*") { return $false }
        return $true
    } |
    ForEach-Object { $_.Name }

if (-not $sourceEntries) {
    throw "No source entries selected for archive."
}

$tarArgs = @(
    "-czf", $archivePath,
    "--exclude=.git",
    "--exclude=.agents",
    "--exclude=.codex",
    "--exclude=venv",
    "--exclude=.venv",
    "--exclude=node_modules",
    "--exclude=frontend/node_modules",
    "--exclude=frontend/dist",
    "--exclude=deployment/ec2/generated",
    "--exclude=deployment/ec2/generated-*",
    "--exclude=./authclaw-key.pem",
    "--exclude=authclaw-key.pem",
    "--exclude=./*.pem",
    "--exclude=*.pem",
    "--exclude=./*.ppk",
    "--exclude=*.ppk",
    "--exclude=./*.key",
    "--exclude=*.key",
    "--exclude=./*.crt",
    "--exclude=*.crt",
    "--exclude=./.aws",
    "--exclude=.aws",
    "--exclude=./credentials",
    "--exclude=credentials",
    "--exclude=./config",
    "--exclude=config",
    "--exclude=./.env",
    "--exclude=.env",
    "--exclude=./*.env",
    "--exclude=*.env",
    "--exclude=./.env.*",
    "--exclude=.env.*",
    "--exclude=frontend/.env",
    "--exclude=frontend/.env.*",
    "--exclude=__pycache__",
    "--exclude=.pytest_cache",
    "--exclude=.mypy_cache",
    "-C", $root
) + $sourceEntries

Write-Host "Creating source archive..."
Invoke-NativeChecked -Command "tar" -Arguments $tarArgs

Write-Host "Copying source and env files to EC2..."
Invoke-NativeChecked -Command "scp" -Arguments ($sshOptions + @("-i", $ResolvedSshKeyPath, $archivePath, "${SshUser}@${Ec2PublicIp}:/tmp/authclaw-source.tar.gz"))
Invoke-NativeChecked -Command "scp" -Arguments ($sshOptions + @("-i", $ResolvedSshKeyPath, $backendEnv, "${SshUser}@${Ec2PublicIp}:/tmp/backend.env"))
Invoke-NativeChecked -Command "scp" -Arguments ($sshOptions + @("-i", $ResolvedSshKeyPath, $frontendEnv, "${SshUser}@${Ec2PublicIp}:/tmp/frontend.env.production"))

$remoteScript = @'
set -euo pipefail

sudo mkdir -p /opt/authclaw /opt/authclaw/frontend /var/www/authclaw
sudo rm -rf /opt/authclaw/*
sudo tar -xzf /tmp/authclaw-source.tar.gz -C /opt/authclaw

sudo mv /tmp/backend.env /opt/authclaw/.env
sudo mv /tmp/frontend.env.production /opt/authclaw/frontend/.env.production

sudo bash /opt/authclaw/deployment/ec2/install-ubuntu.sh
sudo bash /opt/authclaw/deployment/ec2/setup-local-postgres.sh
sudo bash /opt/authclaw/deployment/ec2/setup-app.sh

echo ""
echo "Local service checks:"
curl -fsS http://127.0.0.1:8000/health/ready
echo ""
curl -fsS http://127.0.0.1/health
echo ""

echo "Listening ports:"
sudo ss -ltnp | grep -E ':(80|8000)\s'
'@

Write-Host "Installing and starting AuthClaw on EC2..."
Invoke-SshScript -Script $remoteScript -Arguments ($sshOptions + @("-i", $ResolvedSshKeyPath, "${SshUser}@${Ec2PublicIp}", "bash -s"))

Write-Host ""
Write-Host "Deployment finished."
Write-Host "Frontend: http://$Ec2PublicIp"
Write-Host "Backend:  http://$Ec2PublicIp`:8000/health/ready"
