# TerraApp - dev environment startup script
# Run this once per Windows session to start all services

$ErrorActionPreference = "Continue"
$pgBin = "$env:USERPROFILE\scoop\apps\postgresql\current\bin"
$pgData = "$env:USERPROFILE\scoop\apps\postgresql\current\data"
$root = $PSScriptRoot

Write-Host "=== TerraApp Dev Start ===" -ForegroundColor Cyan

# 1. PostgreSQL
Write-Host "`n[1/5] Starting PostgreSQL..." -ForegroundColor Yellow
$pgStatus = & "$pgBin\pg_ctl.exe" status -D $pgData 2>&1
if ($pgStatus -match "server is running") {
    Write-Host "  PostgreSQL already running" -ForegroundColor Green
} else {
    & "$pgBin\pg_ctl.exe" start -D $pgData -l "$pgData\postgres.log" -w | Out-Null
    Write-Host "  PostgreSQL started" -ForegroundColor Green
}

# 2. Redis
Write-Host "[2/5] Starting Redis..." -ForegroundColor Yellow
$redisProc = Get-Process redis-server -ErrorAction SilentlyContinue
if ($redisProc) {
    Write-Host "  Redis already running (PID $($redisProc.Id))" -ForegroundColor Green
} else {
    Start-Process -FilePath "redis-server" -WindowStyle Hidden
    Start-Sleep -Seconds 1
    Write-Host "  Redis started" -ForegroundColor Green
}

# 3. Backend (FastAPI)
Write-Host "[3/5] Starting Backend (FastAPI on :8000)..." -ForegroundColor Yellow
$uvicorn = "$root\backend\.venv\Scripts\uvicorn.exe"
if (-not (Test-Path $uvicorn)) {
    Write-Host "  ERROR: .venv not found. Run: cd backend; python -m venv .venv; .venv\Scripts\pip install -r requirements.txt" -ForegroundColor Red
} else {
    Start-Process -FilePath $uvicorn `
        -ArgumentList "app.main:app","--host","0.0.0.0","--port","8000","--reload" `
        -WorkingDirectory "$root\backend" `
        -WindowStyle Minimized
    Write-Host "  Backend started (minimized window)" -ForegroundColor Green
}

# 4. Web AdminPanel (Vite on :3000)
Write-Host "[4/5] Starting Web AdminPanel (Vite on :3000)..." -ForegroundColor Yellow
$viteJs = "$root\web\node_modules\vite\bin\vite.js"
if (-not (Test-Path $viteJs)) {
    Write-Host "  ERROR: node_modules not found. Run: cd web; npm install" -ForegroundColor Red
} else {
    Start-Process -FilePath "node" `
        -ArgumentList $viteJs,"--port","3000" `
        -WorkingDirectory "$root\web" `
        -WindowStyle Minimized
    Write-Host "  Web AdminPanel started (minimized window)" -ForegroundColor Green
}

# 5. Expo (Metro + web preview on :8081)
Write-Host "[5/5] Starting Expo mobile (:8081)..." -ForegroundColor Yellow
$mobilePkg = "$root\mobile\package.json"
if (-not (Test-Path $mobilePkg)) {
    Write-Host "  SKIP: mobile/package.json not found" -ForegroundColor Yellow
} elseif (-not (Test-Path "$root\mobile\node_modules")) {
    Write-Host "  SKIP: run: cd mobile; npm install" -ForegroundColor Yellow
} else {
    Start-Process -FilePath "cmd.exe" `
        -ArgumentList '/k', "cd /d `"$root\mobile`" && npx expo start --port 8081" `
        -WorkingDirectory "$root\mobile"
    Write-Host "  Expo started in separate CMD window (http://localhost:8081)" -ForegroundColor Green
}

# Wait and check
Start-Sleep -Seconds 5
Write-Host "`n=== Health Check ===" -ForegroundColor Cyan
try { 
    $h = Invoke-RestMethod http://localhost:8000/health
    Write-Host "  Backend:      http://localhost:8000  -> $($h.status)" -ForegroundColor Green
} catch { 
    Write-Host "  Backend:      http://localhost:8000  -> NOT READY" -ForegroundColor Red 
}
try { 
    Invoke-WebRequest http://localhost:3000 -UseBasicParsing -TimeoutSec 3 | Out-Null
    Write-Host "  AdminPanel:   http://localhost:3000  -> OK" -ForegroundColor Green
} catch { 
    Write-Host "  AdminPanel:   http://localhost:3000  -> starting..." -ForegroundColor Yellow 
}
try {
    Invoke-WebRequest http://localhost:8081 -UseBasicParsing -TimeoutSec 4 | Out-Null
    Write-Host "  Expo (web):   http://localhost:8081  -> OK" -ForegroundColor Green
} catch {
    Write-Host "  Expo (web):   http://localhost:8081  -> open Expo window / wait for Metro" -ForegroundColor Yellow
}

Write-Host "`nAPI Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "AdminPanel: http://localhost:3000" -ForegroundColor Cyan
Write-Host "Expo app:   http://localhost:8081 (after Metro starts)" -ForegroundColor Cyan
Write-Host "Login:      admin / admin123" -ForegroundColor Cyan
Write-Host ""
