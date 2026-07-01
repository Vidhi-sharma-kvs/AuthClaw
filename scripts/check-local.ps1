param(
    [int]$BackendPort = 8000,
    [int]$GatewayPort = 9000,
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

function Test-CorsPreflight {
    param(
        [string]$Name,
        [string]$Url,
        [string]$Origin
    )
    try {
        $headers = @{
            Origin = $Origin
            "Access-Control-Request-Method" = "POST"
            "Access-Control-Request-Headers" = "content-type,authorization,x-api-key"
        }
        $response = Invoke-WebRequest -Method Options -Uri $Url -Headers $headers -UseBasicParsing -TimeoutSec 10
        $allowedOrigin = $response.Headers["Access-Control-Allow-Origin"]
        if ($response.StatusCode -notin @(200, 204) -or $allowedOrigin -ne $Origin) {
            throw "$Name preflight returned status $($response.StatusCode) and origin '$allowedOrigin'."
        }
        Write-Host "$Name preflight OK ($($response.StatusCode)): $Url"
        return $true
    } catch {
        Write-Host "$Name preflight FAILED: $Url"
        Write-Host "  $($_.Exception.Message)"
        return $false
    }
}

function Wait-Port {
    param(
        [string]$Name,
        [int]$Port,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $isOpen = (Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -WarningAction SilentlyContinue).TcpTestSucceeded
        if ($isOpen) {
            Write-Host "$Name port $Port is listening."
            return $true
        }
        Start-Sleep -Milliseconds 750
    }

    Write-Host "$Name port $Port is not listening after $TimeoutSeconds seconds."
    return $false
}

$backendPortOpen = Wait-Port -Name "Backend" -Port $BackendPort
$gatewayPortOpen = Wait-Port -Name "Go gateway" -Port $GatewayPort
$frontendPortOpen = Wait-Port -Name "Frontend" -Port $FrontendPort

if (!$backendPortOpen) {
    throw "Backend port $BackendPort is not listening."
}
if (!$gatewayPortOpen) {
    throw "Go gateway port $GatewayPort is not listening."
}
if (!$frontendPortOpen) {
    throw "Frontend port $FrontendPort is not listening."
}

$backendOk = Test-Http -Name "Backend health" -Url "http://127.0.0.1:$BackendPort/health/ready"
$gatewayOk = Test-Http -Name "Go gateway health" -Url "http://127.0.0.1:$GatewayPort/health/ready"
$frontendOk = Test-Http -Name "Frontend" -Url "http://127.0.0.1:$FrontendPort"
$loginPreflightOk = Test-CorsPreflight -Name "Gateway auth/login" -Url "http://127.0.0.1:$GatewayPort/auth/login" -Origin "http://127.0.0.1:$FrontendPort"

if (!$backendOk -or !$gatewayOk -or !$frontendOk -or !$loginPreflightOk) {
    throw "Local runtime check failed."
}
