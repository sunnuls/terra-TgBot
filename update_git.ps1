# Helper script to stage, commit, pull (rebase) and push in one go.
param(
    [string]$Message = "Auto update $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $repoRoot) {
    $repoRoot = '.'
}

function Invoke-Git {
    param(
        [Parameter(Mandatory=$true)]
        [string[]]$Args
    )

    & git @Args
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Args -join ' ') failed with exit code $LASTEXITCODE"
    }
}

Push-Location $repoRoot
try {
    $status = & git status --porcelain=v1
    if ($LASTEXITCODE -ne 0) {
        throw "git status failed with exit code $LASTEXITCODE"
    }
    if (-not $status) {
        Write-Host "No local changes to commit. Skipping push."
        exit 0
    }

    Invoke-Git -Args @('add','-A')
    Invoke-Git -Args @('commit','-m', $Message)
    Invoke-Git -Args @('pull','--rebase')
    Invoke-Git -Args @('push')

    Write-Host "Repository updated on remote."
}
finally {
    Pop-Location
}

