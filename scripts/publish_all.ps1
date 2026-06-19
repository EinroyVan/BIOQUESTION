#Requires -Version 5.1
<#
.SYNOPSIS
  Verify gh auth and push both BIOQUESTION + BioReader repos.
#>
$Gh = "C:\Program Files\GitHub CLI\gh.exe"
if (-not (Test-Path $Gh)) {
    Write-Error "Install GitHub CLI first: winget install GitHub.cli"
}

Write-Host "=== GitHub CLI auth status ===" -ForegroundColor Cyan
if ($env:GH_TOKEN) {
    Write-Host "Using GH_TOKEN from environment." -ForegroundColor Cyan
} else {
    & $Gh auth status
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "Login not saved. Run this first:" -ForegroundColor Yellow
        Write-Host "  E:\BIOQUESTION\scripts\auth_github.ps1" -ForegroundColor White
        Write-Host "Or set: `$env:GH_TOKEN = 'your-token'" -ForegroundColor White
        exit 1
    }
}

Write-Host ""
Write-Host "=== Pushing BIOQUESTION ===" -ForegroundColor Cyan
& "E:\BIOQUESTION\scripts\push_bioquestion.ps1"

Write-Host ""
Write-Host "=== Pushing BioReader ===" -ForegroundColor Cyan
& "C:\PaperReader\scripts\push_bioreader.ps1"

Write-Host ""
Write-Host "All done." -ForegroundColor Green
