netsh advfirewall firewall delete rule name="Expo Metro 8082" 2>$null
netsh advfirewall firewall delete rule name="Expo Metro 8081" 2>$null
netsh advfirewall firewall delete rule name="TerraApp API 8000" 2>$null
netsh advfirewall firewall add rule name="Expo Metro 8082" dir=in action=allow protocol=TCP localport=8082
netsh advfirewall firewall add rule name="Expo Metro 8081" dir=in action=allow protocol=TCP localport=8081
netsh advfirewall firewall add rule name="TerraApp API 8000" dir=in action=allow protocol=TCP localport=8000
Write-Host "Done! Ports 8081, 8082, 8000 are now open." -ForegroundColor Green
Start-Sleep -Seconds 3
