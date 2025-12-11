# Helper script to stage, commit, pull (rebase) and push in one go.
param(
    [string]$Message = "Auto update $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $repoRoot) {
    $repoRoot = '.'
}

Push-Location $repoRoot
try {
    $status = git status --porcelain=v1
    if (-not $status) {
        Write-Host "No local changes to commit. Skipping push."
        exit 0
    }

    git add -A
    git commit -m $Message
    git pull --rebase
    git push

    Write-Host "Repository updated on remote."
}
finally {
    Pop-Location
}

