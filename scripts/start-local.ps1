param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [switch]$DisableBackgroundMonitor = $true,
    [switch]$DisableRemoteEmbeddings = $true
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root "frontend"
$logs = Join-Path $root "logs"
$backendPython = Join-Path $root "venv_new\Scripts\python.exe"

if (!(Test-Path $logs)) {
    New-Item -ItemType Directory -Path $logs | Out-Null
}

if (!(Test-Path $backendPython)) {
    throw "venv_new was not found. Create it first with: py -m venv venv_new; .\venv_new\Scripts\python.exe -m pip install -r requirements.txt"
}

if (!(Test-Path (Join-Path $frontend "node_modules"))) {
    throw "frontend\node_modules was not found. Run: cd frontend; npm install"
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

Stop-PortOwner -Port $BackendPort
Stop-PortOwner -Port $FrontendPort

$env:AUTHCLAW_ENV = "development"
$env:AUTHCLAW_ALLOWED_ORIGINS = "http://127.0.0.1:$FrontendPort,http://localhost:$FrontendPort"
if ($DisableBackgroundMonitor) {
    $env:AUTHCLAW_DISABLE_BACKGROUND_MONITOR = "true"
}
if ($DisableRemoteEmbeddings) {
    $env:AUTHCLAW_DISABLE_REMOTE_EMBEDDINGS = "true"
}
if (!$env:MODEL_NAME -or $env:MODEL_NAME -eq "gemini-3.1-flash-lite") {
    $env:MODEL_NAME = "gemini-2.5-flash-lite"
}

$backendOut = Join-Path $logs "local-backend.out.log"
$backendErr = Join-Path $logs "local-backend.err.log"
$frontendOut = Join-Path $logs "local-frontend.out.log"
$frontendErr = Join-Path $logs "local-frontend.err.log"

Start-Process `
    -FilePath $backendPython `
    -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "$BackendPort") `
    -WorkingDirectory $root `
    -RedirectStandardOutput $backendOut `
    -RedirectStandardError $backendErr `
    -WindowStyle Hidden

Start-Process `
    -FilePath "npm.cmd" `
    -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "$FrontendPort") `
    -WorkingDirectory $frontend `
    -RedirectStandardOutput $frontendOut `
    -RedirectStandardError $frontendErr `
    -WindowStyle Hidden

Start-Sleep -Seconds 4

& (Join-Path $PSScriptRoot "check-local.ps1") -BackendPort $BackendPort -FrontendPort $FrontendPort

Write-Host ""
Write-Host "AuthClaw local runtime is ready:"
Write-Host "  Frontend: http://127.0.0.1:$FrontendPort"
Write-Host "  Gateway:  http://127.0.0.1:$BackendPort"
Write-Host "  Health:   http://127.0.0.1:$BackendPort/health/ready"
Write-Host ""
Write-Host "Logs:"
Write-Host "  $backendOut"
Write-Host "  $backendErr"
Write-Host "  $frontendOut"
Write-Host "  $frontendErr"
