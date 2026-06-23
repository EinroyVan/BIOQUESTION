#Requires -Version 5.1
<#
.SYNOPSIS
  Fix gh "not logged in" on Windows when Credential Manager fails to save the token.
  Stores token in ~/.config/gh/ instead (use --insecure-storage).
#>
$ErrorActionPreference = "Stop"

$Gh = "C:\Program Files\GitHub CLI\gh.exe"
if (-not (Test-Path $Gh)) {
    throw "Install GitHub CLI: winget install GitHub.cli"
}

$PublishScript = Join-Path (Split-Path -Parent $PSScriptRoot) "scripts\publish_all.ps1"

function Test-GhLoggedIn {
    $out = & $Gh auth status 2>&1 | Out-String
    return ($LASTEXITCODE -eq 0) -and ($out -notmatch "not logged in")
}

Write-Host "GitHub CLI: $Gh" -ForegroundColor Cyan
Write-Host ""

if (Test-GhLoggedIn) {
    Write-Host "Already logged in:" -ForegroundColor Green
    & $Gh auth status
    exit 0
}

Write-Host "No saved GitHub token found (login did not complete or Credential Manager failed)." -ForegroundColor Yellow
Write-Host ""
Write-Host "Starting login with --insecure-storage (saves token to user profile)..." -ForegroundColor Cyan
Write-Host "Steps:" -ForegroundColor White
Write-Host "  1. Copy the one-time code shown below"
Write-Host "  2. Press Enter to open https://github.com/login/device"
Write-Host "  3. Paste the code and authorize"
Write-Host "  4. Wait until this window says 'Authentication complete'"
Write-Host ""

& $Gh auth login --hostname github.com --git-protocol https --web --insecure-storage

Write-Host ""
if (Test-GhLoggedIn) {
    Write-Host "SUCCESS - GitHub CLI is now authenticated:" -ForegroundColor Green
    & $Gh auth status
    & $Gh auth setup-git
    Write-Host ""
    Write-Host "Next, run: $PublishScript" -ForegroundColor Cyan
} else {
    Write-Host "FAILED - still not logged in." -ForegroundColor Red
    Write-Host ""
    Write-Host "Alternative: use a Personal Access Token (PAT)" -ForegroundColor Yellow
    Write-Host "  1. Open https://github.com/settings/tokens"
    Write-Host "  2. Generate token (classic) with 'repo' scope"
    Write-Host "  3. In PowerShell run:"
    Write-Host '     $env:GH_TOKEN = "paste-token-here"'
    Write-Host "     & '$Gh' auth setup-git"
    Write-Host "     $PublishScript"
    exit 1
}
