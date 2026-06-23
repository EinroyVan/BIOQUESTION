#Requires -Version 5.1
<#
.SYNOPSIS
  Push Questioner to https://github.com/EinroyVan/Questioner
#>
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
# Git requires forward slashes in safe.directory on Windows (backslashes break -c and cause exit 128).
$SafeDir = "safe.directory=" + ($RepoRoot -replace '\\', '/')

function Get-GhExe {
    $candidates = @(
        (Join-Path $env:ProgramFiles "GitHub CLI\gh.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "GitHub CLI\gh.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\GitHub CLI\gh.exe")
    )
    foreach ($path in $candidates) {
        if (Test-Path $path) { return $path }
    }
    $cmd = Get-Command gh -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "GitHub CLI not found. Install: winget install GitHub.cli"
}

function Test-GhAuth {
    param([string]$GhExe)
    if ($env:GH_TOKEN) { return $true }
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        $output = & $GhExe auth status 2>&1 | Out-String
        return ($LASTEXITCODE -eq 0) -and ($output -notmatch "not logged in")
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Invoke-RepoGit {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GitArgs)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        & git -c $SafeDir @GitArgs
        if ($LASTEXITCODE -ne 0) {
            throw "git $($GitArgs -join ' ') failed (exit $LASTEXITCODE)"
        }
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Test-GhRepo {
    param([string]$GhExe, [string]$Name)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        & $GhExe repo view $Name *> $null
        return ($LASTEXITCODE -eq 0)
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Invoke-Gh {
    param([string]$GhExe, [Parameter(ValueFromRemainingArguments = $true)][string[]]$GhArgs)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        $output = & $GhExe @GhArgs 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) {
            $cmd = "gh $($GhArgs -join ' ')"
            if ($output.Trim()) {
                throw "$cmd failed (exit $LASTEXITCODE): $($output.Trim())"
            }
            throw "$cmd failed (exit $LASTEXITCODE)"
        }
        return $output
    } finally {
        $ErrorActionPreference = $prev
    }
}

$Gh = Get-GhExe
Write-Host "Using GitHub CLI: $Gh" -ForegroundColor Cyan
if ($env:GH_TOKEN) {
    Write-Host "Using GH_TOKEN from environment." -ForegroundColor Cyan
}

$AuthScript = Join-Path $PSScriptRoot "auth_github.ps1"
if (-not (Test-GhAuth -GhExe $Gh)) {
    Write-Host ""
    Write-Host "Not authenticated. Run: $AuthScript" -ForegroundColor Yellow
    Write-Host "Or set: `$env:GH_TOKEN = 'your-token'" -ForegroundColor Yellow
    throw "GitHub authentication required."
}

if (-not (Test-Path ".git")) {
    Invoke-RepoGit init -b main
}

Invoke-RepoGit add -A
$status = Invoke-RepoGit status --porcelain
if ($status) {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        & git -c $SafeDir -c user.name=EinroyVan -c user.email=EinroyVan@users.noreply.github.com `
            commit -m "Add GitHub publish scripts and fix push workflow"
        if ($LASTEXITCODE -ne 0) {
            throw "git commit failed (exit $LASTEXITCODE)"
        }
    } finally {
        $ErrorActionPreference = $prev
    }
}

$remote = "https://github.com/EinroyVan/Questioner.git"
$repoName = "EinroyVan/Questioner"
$repoDesc = "Questioner — natural-science literature extract, quiz, and grade (Streamlit + multi-LLM)"

if (-not (Test-GhRepo -GhExe $Gh -Name $repoName)) {
    Write-Host "Creating repository $repoName ..." -ForegroundColor Cyan
    Invoke-Gh $Gh repo create $repoName --public --description $repoDesc | Out-Null
} else {
    Write-Host "Repository $repoName already exists." -ForegroundColor Cyan
    Invoke-Gh $Gh repo edit $repoName --description $repoDesc | Out-Null
}

$remotes = Invoke-RepoGit remote
if (-not ($remotes | Select-String "^origin$")) {
    Invoke-RepoGit remote add origin $remote
} else {
    Invoke-RepoGit remote set-url origin $remote
}

$prev = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
& $Gh auth setup-git *> $null
$ErrorActionPreference = $prev

Write-Host "Pushing to origin main ..." -ForegroundColor Cyan
Invoke-RepoGit push -u origin main

if (-not (Test-GhRepo -GhExe $Gh -Name $repoName)) {
    throw "Push finished but https://github.com/$repoName is still not visible. Check token has 'repo' scope."
}

Write-Host ""
Write-Host "Done: https://github.com/$repoName" -ForegroundColor Green
