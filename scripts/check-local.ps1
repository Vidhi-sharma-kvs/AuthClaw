param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"

function Test-Http {
    param(
        [string]$Name,
        [string]$Url
    )
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 10
        Write-Host "$Name OK ($($response.StatusCode)): $Url"
        return $true
    } catch {
        Write-Host "$Name FAILED: $Url"
        Write-Host "  $($_.Exception.Message)"
        return $false
    }
}

$backendPortOpen = (Test-NetConnection -ComputerName 127.0.0.1 -Port $BackendPort -WarningAction SilentlyContinue).TcpTestSucceeded
$frontendPortOpen = (Test-NetConnection -ComputerName 127.0.0.1 -Port $FrontendPort -WarningAction SilentlyContinue).TcpTestSucceeded

if (!$backendPortOpen) {
    throw "Backend port $BackendPort is not listening."
}
if (!$frontendPortOpen) {
    throw "Frontend port $FrontendPort is not listening."
}

$backendOk = Test-Http -Name "Backend health" -Url "http://127.0.0.1:$BackendPort/health/ready"
$frontendOk = Test-Http -Name "Frontend" -Url "http://127.0.0.1:$FrontendPort"

if (!$backendOk -or !$frontendOk) {
    throw "Local runtime check failed."
}
