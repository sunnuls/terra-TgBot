$bundleUrl = "http://192.168.1.20:8082/index.bundle?platform=ios&dev=true&hot=false&lazy=true&transform.engine=hermes&transform.bytecode=1&transform.routerRoot=app&unstable_transformProfile=hermes-stable"

Write-Host "Bundle warmer started. Press Ctrl+C to stop." -ForegroundColor Cyan

while ($true) {
    try {
        $s = Get-Date
        $r = Invoke-WebRequest $bundleUrl -UseBasicParsing -TimeoutSec 60 -ErrorAction Stop
        $sec = [math]::Round(((Get-Date)-$s).TotalSeconds, 1)
        $mb  = [math]::Round($r.RawContentLength / 1MB, 1)
        Write-Host "[$((Get-Date).ToString('HH:mm:ss'))] Bundle warm OK: ${mb}MB in ${sec}s" -ForegroundColor Green
    } catch {
        Write-Host "[$((Get-Date).ToString('HH:mm:ss'))] Metro not ready, retrying..." -ForegroundColor Yellow
    }
    Start-Sleep -Seconds 30
}
