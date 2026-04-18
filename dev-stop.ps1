# TerraApp - stop all dev services
$pgBin = "$env:USERPROFILE\scoop\apps\postgresql\current\bin"
$pgData = "$env:USERPROFILE\scoop\apps\postgresql\current\data"

Write-Host "=== TerraApp Dev Stop ===" -ForegroundColor Cyan

# Stop FastAPI (uvicorn)
Get-Process -Name "uvicorn" -ErrorAction SilentlyContinue | Stop-Process -Force
# Stop Vite (node processes in web dir - be careful)
Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object {
    $_.MainWindowTitle -eq "" 
} | Stop-Process -Force -ErrorAction SilentlyContinue

# Stop Redis
Get-Process -Name "redis-server" -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host "  Redis stopped" -ForegroundColor Green

# Stop PostgreSQL gracefully
& "$pgBin\pg_ctl.exe" stop -D $pgData -m fast 2>&1 | Out-Null
Write-Host "  PostgreSQL stopped" -ForegroundColor Green

Write-Host "All services stopped." -ForegroundColor Cyan
