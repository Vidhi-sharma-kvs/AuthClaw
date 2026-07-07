param(
    [int[]]$Ports = @(8000, 9000, 5173, 5174, 5175)
)

$ErrorActionPreference = "Stop"

foreach ($port in $Ports) {
    $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
        if ($connection.OwningProcess) {
            Write-Host "Stopping process $($connection.OwningProcess) on port $port"
            Stop-Process -Id $connection.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}
