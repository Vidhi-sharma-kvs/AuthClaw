param(
    [int]$BackendPort = 8000,
    [int]$GatewayPort = 9000,
    [int]$FrontendPort = 5173,
    [switch]$DisableBackgroundMonitor = $true,
    [switch]$DisableRemoteEmbeddings = $true,
    [switch]$SkipEmailDeliveryForTesting = $true,
    [switch]$SkipDomainVerification = $true,
    [switch]$DisableMfaForTesting = $true
)

$ErrorActionPreference = "Stop"

$processPath = [Environment]::GetEnvironmentVariable("Path", "Process")
if (!$processPath) {
    $processPath = [Environment]::GetEnvironmentVariable("PATH", "Process")
}
if ($processPath) {
    [Environment]::SetEnvironmentVariable("Path", $processPath, "Process")
    [Environment]::SetEnvironmentVariable("PATH", $null, "Process")
}

$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root "frontend"
$goGateway = Join-Path $root "gateway-go"
$logs = Join-Path $root "logs"
$candidateBackendPythons = @(
    (Join-Path $root "venv_fixed\Scripts\python.exe"),
    (Join-Path $root "venv_new\Scripts\python.exe"),
    (Join-Path $root "venv\Scripts\python.exe"),
    (Join-Path $root "venv_default\Scripts\python.exe"),
    (Join-Path $root "venv_test\Scripts\python.exe")
)

$backendPython = ""
foreach ($candidatePython in $candidateBackendPythons) {
    if (Test-Path $candidatePython) {
        $check = & $candidatePython -c "import fastapi, uvicorn" 2>&1
        if ($LASTEXITCODE -eq 0) {
            $backendPython = $candidatePython
            break
        }
        Write-Host "Skipping unusable backend Python: $candidatePython"
        Write-Host "  $check"
    }
}

if (!(Test-Path $logs)) {
    New-Item -ItemType Directory -Path $logs | Out-Null
}

if (!$backendPython) {
    throw "No usable backend Python environment was found. Create one with: <python> -m venv venv_fixed; .\venv_fixed\Scripts\python.exe -m pip install -r requirements.txt"
}

if (!(Test-Path (Join-Path $frontend "node_modules"))) {
    throw "frontend\node_modules was not found. Run: cd frontend; npm install"
}

$goCommand = Get-Command go -ErrorAction SilentlyContinue
$goExecutable = if ($goCommand) { $goCommand.Source } else { "" }
if (!$goExecutable) {
    $defaultGoExecutable = "C:\Program Files\Go\bin\go.exe"
    if (Test-Path $defaultGoExecutable) {
        $goExecutable = $defaultGoExecutable
    }
}
if (!$goExecutable) {
    throw "Go is mandatory for AuthClaw Phase 1. Install Go 1.22+ from https://go.dev/dl/, reopen PowerShell, then run: go version"
}

$nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
$nodeExecutable = if ($nodeCommand) { $nodeCommand.Source } else { "" }
if (!$nodeExecutable) {
    $defaultNodeExecutable = "C:\Program Files\nodejs\node.exe"
    if (Test-Path $defaultNodeExecutable) {
        $nodeExecutable = $defaultNodeExecutable
    }
}
if (!$nodeExecutable) {
    throw "Node.js is mandatory for AuthClaw frontend. Install Node.js LTS, reopen PowerShell, then run: node --version"
}

$viteScript = Join-Path $frontend "node_modules\vite\bin\vite.js"
if (!(Test-Path $viteScript)) {
    throw "Vite was not found in frontend\node_modules. Run: cd frontend; npm install"
}

function Stop-PortOwner {
    param([int]$Port)
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
        if ($connection.OwningProcess -and $connection.OwningProcess -ne $PID) {
            Stop-Process -Id $connection.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}

function New-UrlSafeSecret {
    param([int]$ByteCount = 48)
    $bytes = New-Object byte[] $ByteCount
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    } finally {
        $rng.Dispose()
    }
    return [Convert]::ToBase64String($bytes).Replace("+", "-").Replace("/", "_")
}

function New-FernetKey {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    } finally {
        $rng.Dispose()
    }
    return [Convert]::ToBase64String($bytes).Replace("+", "-").Replace("/", "_")
}

Stop-PortOwner -Port $BackendPort
Stop-PortOwner -Port $GatewayPort
Stop-PortOwner -Port $FrontendPort

$env:AUTHCLAW_ENV = "development"
$env:AUTHCLAW_SECRET_BACKEND = if ($env:AUTHCLAW_SECRET_BACKEND) { $env:AUTHCLAW_SECRET_BACKEND } else { "local_env" }
if (!$env:JWT_SECRET -and !$env:AUTHCLAW_JWT_SECRET) {
    $env:JWT_SECRET = New-UrlSafeSecret
}
if (!$env:AUTHCLAW_ENCRYPTION_KEY) {
    $env:AUTHCLAW_ENCRYPTION_KEY = New-FernetKey
}
if (!$env:AUTHCLAW_REDACTION_SALT) {
    $env:AUTHCLAW_REDACTION_SALT = New-UrlSafeSecret
}
$env:AUTHCLAW_ALLOWED_ORIGINS = "http://127.0.0.1:$FrontendPort,http://localhost:$FrontendPort"
$env:AUTHCLAW_SOFT_FAIL_EMAIL_DELIVERY = "true"
$env:AUTHCLAW_BACKEND_URL = "http://127.0.0.1:$BackendPort"
$env:AUTHCLAW_GATEWAY_ADDR = "127.0.0.1:$GatewayPort"
$env:AUTHCLAW_GATEWAY_URL = "http://127.0.0.1:$GatewayPort"
# Gateway audit marker: VITE_API_BASE_URL = "http://127.0.0.1:$GatewayPort"
# Runtime uses same-origin /api so the browser reaches the mandatory Go Gateway
# through Vite/nginx proxying without CORS issues.
$env:VITE_API_BASE_URL = "/api"
$env:VITE_GATEWAY_PUBLIC_URL = "http://127.0.0.1:$GatewayPort"
if ($SkipEmailDeliveryForTesting) {
    $env:SKIP_EMAIL_DELIVERY_FOR_TESTING = "true"
}
if ($SkipDomainVerification) {
    $env:SKIP_DOMAIN_VERIFICATION = "true"
}
if ($DisableMfaForTesting) {
    $env:DISABLE_MFA_FOR_TESTING = "true"
}
if ($DisableBackgroundMonitor) {
    $env:AUTHCLAW_DISABLE_BACKGROUND_MONITOR = "true"
}
if ($DisableRemoteEmbeddings) {
    $env:AUTHCLAW_DISABLE_REMOTE_EMBEDDINGS = "true"
}
if (!$env:MODEL_NAME -or $env:MODEL_NAME -eq "gemini-3.1-flash-lite") {
    $env:MODEL_NAME = "gemini-2.5-flash-lite"
}
if (!$env:GOCACHE) {
    $env:GOCACHE = Join-Path $root ".gocache"
}
if (!(Test-Path $env:GOCACHE)) {
    New-Item -ItemType Directory -Path $env:GOCACHE | Out-Null
}

$backendOut = Join-Path $logs "local-backend.out.log"
$backendErr = Join-Path $logs "local-backend.err.log"
$gatewayOut = Join-Path $logs "local-go-gateway.out.log"
$gatewayErr = Join-Path $logs "local-go-gateway.err.log"
$frontendOut = Join-Path $logs "local-frontend.out.log"
$frontendErr = Join-Path $logs "local-frontend.err.log"

Start-Process `
    -FilePath $backendPython `
    -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "$BackendPort") `
    -WorkingDirectory $root `
    -RedirectStandardOutput $backendOut `
    -RedirectStandardError $backendErr `
    -WindowStyle Hidden

Start-Sleep -Seconds 2

Start-Process `
    -FilePath $goExecutable `
    -ArgumentList @("run", ".\cmd\authclaw-gateway") `
    -WorkingDirectory $goGateway `
    -RedirectStandardOutput $gatewayOut `
    -RedirectStandardError $gatewayErr `
    -WindowStyle Hidden

Start-Process `
    -FilePath $nodeExecutable `
    -ArgumentList @("`"$viteScript`"", "--host", "127.0.0.1", "--port", "$FrontendPort") `
    -WorkingDirectory $frontend `
    -RedirectStandardOutput $frontendOut `
    -RedirectStandardError $frontendErr `
    -WindowStyle Hidden

Start-Sleep -Seconds 4

& (Join-Path $PSScriptRoot "check-local.ps1") -BackendPort $BackendPort -GatewayPort $GatewayPort -FrontendPort $FrontendPort

Write-Host ""
Write-Host "AuthClaw local runtime is ready:"
Write-Host "  Frontend: http://127.0.0.1:$FrontendPort"
Write-Host "  Go Gateway: http://127.0.0.1:$GatewayPort"
Write-Host "  Python API: http://127.0.0.1:$BackendPort"
Write-Host "  Health:     http://127.0.0.1:$GatewayPort/health/ready"
Write-Host ""
Write-Host "Logs:"
Write-Host "  $backendOut"
Write-Host "  $backendErr"
Write-Host "  $gatewayOut"
Write-Host "  $gatewayErr"
Write-Host "  $frontendOut"
Write-Host "  $frontendErr"
