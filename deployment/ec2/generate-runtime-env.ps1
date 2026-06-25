param(
    [string]$Ec2PublicIp,
    [string]$RdsEndpoint,
    [switch]$UseLocalPostgres,
    [string]$DatabasePassword,
    [string]$DatabaseUsername = "authclaw",
    [string]$DatabaseName = "authclaw",
    [string]$SmtpHost = "smtp.sendgrid.net",
    [string]$SmtpUsername = "apikey",
    [string]$SmtpPassword,
    [string]$SmtpFrom,
    [string]$SmtpPort = "587",
    [string]$AwsRegion = "us-east-1",
    [string]$GoogleApiKey = "",
    [string]$ModelProvider = "gemini",
    [string]$ModelName = "gemini-2.5-flash-lite",
    [string]$OutputDirectory = "deployment/ec2/generated"
)

$ErrorActionPreference = "Stop"

function New-UrlSafeSecret([int]$Bytes) {
    $buffer = New-Object byte[] $Bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($buffer)
    }
    finally {
        $rng.Dispose()
    }
    return [Convert]::ToBase64String($buffer).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

function New-FernetKey {
    $buffer = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($buffer)
    }
    finally {
        $rng.Dispose()
    }
    return [Convert]::ToBase64String($buffer).Replace("+", "-").Replace("/", "_")
}

if (-not $Ec2PublicIp) { throw "Required: -Ec2PublicIp" }
if (-not $UseLocalPostgres -and -not $RdsEndpoint) { throw "Required: -RdsEndpoint unless -UseLocalPostgres is set" }
if (-not $DatabasePassword) { throw "Required: -DatabasePassword" }
if (-not $SmtpPassword) { throw "Required: -SmtpPassword" }
if (-not $SmtpFrom) { throw "Required: -SmtpFrom" }
if ($ModelProvider -eq "gemini" -and -not $GoogleApiKey) { throw "Required: -GoogleApiKey when -ModelProvider is gemini" }

if (-not (Test-Path $OutputDirectory)) {
    New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
}

$frontendOrigin = "http://$Ec2PublicIp"
$backendUrl = "/api"
if ($UseLocalPostgres) {
    $databaseUrl = "postgresql://$DatabaseUsername`:$DatabasePassword@127.0.0.1:5432/$DatabaseName"
}
else {
    $databaseUrl = "postgresql://$DatabaseUsername`:$DatabasePassword@$RdsEndpoint`:5432/$DatabaseName"
}
$jwtSecret = New-UrlSafeSecret 48
$fernetKey = New-FernetKey

$backendEnv = @"
AUTHCLAW_ENV=production
AUTHCLAW_ALLOWED_ORIGINS=$frontendOrigin
AUTHCLAW_RATE_LIMIT_PER_MINUTE=120
ENABLE_DEV_MODE=false
SKIP_EMAIL_DELIVERY_FOR_TESTING=false
SKIP_DOMAIN_VERIFICATION=true
DISABLE_MFA_FOR_TESTING=false

DATABASE_URL=$databaseUrl
JWT_SECRET=$jwtSecret
AUTHCLAW_ENCRYPTION_KEY=$fernetKey

SMTP_HOST=$SmtpHost
SMTP_PORT=$SmtpPort
SMTP_USERNAME=$SmtpUsername
SMTP_PASSWORD=$SmtpPassword
SMTP_FROM=$SmtpFrom
SMTP_USE_TLS=true

AWS_SECRETS_MANAGER_ENABLED=false
AWS_REGION=$AwsRegion

MODEL_PROVIDER=$ModelProvider
MODEL_NAME=$ModelName
GOOGLE_API_KEY=$GoogleApiKey

AUTHCLAW_USE_COOKIES=false
AUTHCLAW_COOKIE_SECURE=false
AUTHCLAW_COOKIE_SAMESITE=lax
"@

$frontendEnv = @"
VITE_API_BASE_URL=$backendUrl
"@

$backendPath = Join-Path $OutputDirectory "backend.env"
$frontendPath = Join-Path $OutputDirectory "frontend.env.production"

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText((Resolve-Path -LiteralPath (Split-Path $backendPath -Parent)).Path + [System.IO.Path]::DirectorySeparatorChar + (Split-Path $backendPath -Leaf), $backendEnv, $utf8NoBom)
[System.IO.File]::WriteAllText((Resolve-Path -LiteralPath (Split-Path $frontendPath -Parent)).Path + [System.IO.Path]::DirectorySeparatorChar + (Split-Path $frontendPath -Leaf), $frontendEnv, $utf8NoBom)

Write-Host "Generated runtime env files:"
Write-Host "  $backendPath"
Write-Host "  $frontendPath"
Write-Host ""
Write-Host "Copy to EC2:"
Write-Host "  backend.env -> /opt/authclaw/.env"
Write-Host "  frontend.env.production -> /opt/authclaw/frontend/.env.production"
Write-Host ""
Write-Host "Testing mode note:"
Write-Host "  SKIP_DOMAIN_VERIFICATION=true because this direct EC2 deployment has no DNS."
Write-Host "  Change it to false when you add real DNS/domain verification."
Write-Host "  SMTP defaults target SendGrid: host=smtp.sendgrid.net, username=apikey."
if ($UseLocalPostgres) {
    Write-Host "  DATABASE_URL targets local PostgreSQL on the EC2 instance."
}
