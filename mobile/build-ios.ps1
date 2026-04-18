# TerraApp — iOS build via EAS (Expo Application Services)
# Требуется: аккаунт https://expo.dev и (для .ipa на устройство) участие в Apple Developer Program.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== EAS iOS build ===" -ForegroundColor Cyan

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "npm not found. Install Node.js first." -ForegroundColor Red
    exit 1
}

$npxEas = "npx --yes eas-cli@latest"
$who = & cmd /c "$npxEas whoami 2>&1"
if ($LASTEXITCODE -ne 0 -or "$who" -match "Not logged in") {
    Write-Host "Not logged in to Expo. Run first:" -ForegroundColor Yellow
    Write-Host "  cd mobile" -ForegroundColor White
    Write-Host "  npx eas-cli@latest login" -ForegroundColor White
    Write-Host "Then link the project (once):" -ForegroundColor Yellow
    Write-Host "  npx eas-cli@latest init" -ForegroundColor White
    Write-Host "Then run this script again, or:" -ForegroundColor Yellow
    Write-Host "  npm run build:ios          # production (device / TestFlight — нужны Apple credentials)" -ForegroundColor White
    Write-Host "  npm run build:ios:sim      # только iOS Simulator (.tar.gz)" -ForegroundColor White
    exit 1
}

Write-Host "Logged in as: $who" -ForegroundColor Green

# If app.json has no projectId, eas init is required (interactive).
$appJson = Get-Content -Raw -Path ".\app.json" | ConvertFrom-Json
$easProjectId = $null
if ($appJson.expo.extra -and $appJson.expo.extra.eas) {
    $easProjectId = $appJson.expo.extra.eas.projectId
}
if (-not $easProjectId) {
    Write-Host "No eas.projectId in app.json. Run: npx eas-cli@latest init" -ForegroundColor Yellow
    exit 1
}

$profile = $args[0]
if (-not $profile) { $profile = "production" }
Write-Host "Starting EAS build with profile: $profile" -ForegroundColor Cyan
& cmd /c "npx --yes eas-cli@latest build --platform ios --profile $profile --non-interactive"
exit $LASTEXITCODE
