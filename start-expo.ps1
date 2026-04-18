$env:REACT_NATIVE_PACKAGER_HOSTNAME = "192.168.137.1"
$env:EXPO_PUBLIC_API_URL = "http://192.168.137.1:8000/api/v1"

Set-Location "C:\proekt-i\terra_app\mobile"

Write-Host "Starting Expo..." -ForegroundColor Cyan

# Start expo process with redirected stdin so we can answer the login prompt
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "cmd.exe"
$psi.Arguments = '/c npx expo start --lan --port 8082'
$psi.UseShellExecute = $false
$psi.RedirectStandardInput = $true
$psi.WorkingDirectory = "C:\proekt-i\terra_app\mobile"

$proc = [System.Diagnostics.Process]::Start($psi)
Write-Host "PID: $($proc.Id) - Waiting 18s for login prompt..." -ForegroundColor Yellow

Start-Sleep -Seconds 18

# Down arrow = select "Proceed anonymously", then Enter
$proc.StandardInput.Write([char]27 + "[B")  # ESC[B = down arrow
$proc.StandardInput.Flush()
Start-Sleep -Milliseconds 200
$proc.StandardInput.WriteLine("")
$proc.StandardInput.Flush()

Write-Host "Selected 'Proceed anonymously'" -ForegroundColor Green
Write-Host "Waiting 15s for Metro to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

# Pre-warm the bundle so iPhone loads instantly
Write-Host "Pre-warming iOS bundle..." -ForegroundColor Yellow
$bundleUrl = "http://192.168.137.1:8082/index.bundle?platform=ios&dev=true&hot=false&lazy=true&transform.engine=hermes&transform.bytecode=1&transform.routerRoot=app&unstable_transformProfile=hermes-stable"
try {
    $start = Get-Date
    $r = Invoke-WebRequest $bundleUrl -UseBasicParsing -TimeoutSec 120
    $sec = [math]::Round(((Get-Date)-$start).TotalSeconds, 1)
    $mb = [math]::Round($r.RawContentLength/1MB, 1)
    Write-Host "Bundle ready in ${sec}s (${mb}MB) - iPhone can now scan QR!" -ForegroundColor Green
} catch {
    Write-Host "Bundle pre-warm failed: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "QR: exp://192.168.137.1:8082" -ForegroundColor Cyan
Write-Host "Admin: http://localhost:3000" -ForegroundColor Cyan

$proc.WaitForExit()
