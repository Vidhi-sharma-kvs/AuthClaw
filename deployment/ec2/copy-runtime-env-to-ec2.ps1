param(
    [string]$Ec2PublicIp,
    [string]$SshKeyPath,
    [string]$SshUser = "ubuntu",
    [string]$GeneratedDirectory = "deployment/ec2/generated"
)

$ErrorActionPreference = "Stop"

if (-not $Ec2PublicIp) { throw "Required: -Ec2PublicIp" }
if (-not $SshKeyPath) { throw "Required: -SshKeyPath" }

$backendEnv = Join-Path $GeneratedDirectory "backend.env"
$frontendEnv = Join-Path $GeneratedDirectory "frontend.env.production"

if (-not (Test-Path $backendEnv)) { throw "Missing generated backend env: $backendEnv" }
if (-not (Test-Path $frontendEnv)) { throw "Missing generated frontend env: $frontendEnv" }

scp -i $SshKeyPath $backendEnv "${SshUser}@${Ec2PublicIp}:/tmp/backend.env"
scp -i $SshKeyPath $frontendEnv "${SshUser}@${Ec2PublicIp}:/tmp/frontend.env.production"

ssh -i $SshKeyPath "${SshUser}@${Ec2PublicIp}" "sudo mkdir -p /opt/authclaw/frontend && sudo mv /tmp/backend.env /opt/authclaw/.env && sudo mv /tmp/frontend.env.production /opt/authclaw/frontend/.env.production && if id authclaw >/dev/null 2>&1; then sudo chown authclaw:authclaw /opt/authclaw/.env; fi"

Write-Host "Runtime env files copied to EC2."
Write-Host "Backend:  /opt/authclaw/.env"
Write-Host "Frontend: /opt/authclaw/frontend/.env.production"
