# Launch Expo in a real interactive window and auto-answer the login prompt
$env:REACT_NATIVE_PACKAGER_HOSTNAME = "192.168.137.1"
$env:EXPO_PUBLIC_API_URL = "http://192.168.137.1:8000/api/v1"

Set-Location "C:\proekt-i\terra_app\mobile"

# Start Expo in a new visible cmd window with real TTY
$proc = Start-Process -FilePath "cmd.exe" `
    -ArgumentList '/k', "set REACT_NATIVE_PACKAGER_HOSTNAME=192.168.137.1 && set EXPO_PUBLIC_API_URL=http://192.168.137.1:8000/api/v1 && npx expo start --lan --port 8082" `
    -WorkingDirectory "C:\proekt-i\terra_app\mobile" `
    -PassThru

Write-Host "Expo started (PID: $($proc.Id))" -ForegroundColor Cyan
Write-Host "Waiting 20s for login prompt..." -ForegroundColor Yellow
Start-Sleep -Seconds 20

# Use WScript.Shell to send Down+Enter to select "Proceed anonymously"
$wsh = New-Object -ComObject WScript.Shell
$activated = $wsh.AppActivate($proc.Id)
Write-Host "Window activated: $activated"
Start-Sleep -Milliseconds 500
$wsh.SendKeys("{DOWN}")
Start-Sleep -Milliseconds 300
$wsh.SendKeys("{ENTER}")

Write-Host "Sent: Proceed anonymously" -ForegroundColor Green
Write-Host "Waiting 20s for Metro..." -ForegroundColor Yellow
Start-Sleep -Seconds 20

# Pre-warm bundle
Write-Host "Pre-warming bundle..." -ForegroundColor Yellow
$bundleUrl = "http://192.168.137.1:8082/index.bundle?platform=ios&dev=true&hot=false&lazy=true&transform.engine=hermes&transform.bytecode=1&transform.routerRoot=app&unstable_transformProfile=hermes-stable"
try {
    $s = Get-Date
    $r = Invoke-WebRequest $bundleUrl -UseBasicParsing -TimeoutSec 120
    $sec = [math]::Round(((Get-Date)-$s).TotalSeconds, 1)
    $mb = [math]::Round($r.RawContentLength/1MB, 1)
    Write-Host "READY in ${sec}s (${mb}MB) - SCAN QR NOW!" -ForegroundColor Green
} catch {
    Write-Host "Pre-warm failed: $_" -ForegroundColor Red
}
