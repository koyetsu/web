param(
    [string]$VenvPath = ".venv",
    [string]$BindAddress = "127.0.0.1",
    [int]$Port = 5000,
    [string]$AdminPassword,
    [string]$WebrootPath,
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$candidateRoot = $scriptDir

if (-not (Test-Path (Join-Path $candidateRoot 'requirements.txt'))) {
    $parentDir = Split-Path -Parent $candidateRoot
    if ($parentDir -and (Test-Path (Join-Path $parentDir 'requirements.txt'))) {
        $candidateRoot = $parentDir
    }
}

$repoRoot = (Resolve-Path $candidateRoot).Path
Set-Location $repoRoot

if (!(Test-Path $VenvPath)) {
    Write-Host "Creating virtual environment at $VenvPath" -ForegroundColor Cyan
    python -m venv $VenvPath
}

$venvPython = Join-Path $VenvPath "Scripts/python.exe"
if (!(Test-Path $venvPython)) {
    throw "Unable to find python interpreter at $venvPython."
}

if (-not $SkipInstall) {
    Write-Host "Installing dependencies" -ForegroundColor Cyan
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r requirements.txt
} else {
    Write-Host "Skipping dependency install" -ForegroundColor Yellow
}

if ($WebrootPath) {
    if (-not (Test-Path $WebrootPath)) {
        New-Item -ItemType Directory -Path $WebrootPath -Force | Out-Null
    }
    $resolvedWebroot = (Resolve-Path $WebrootPath).Path
} else {
    $defaultWebroot = Join-Path $repoRoot 'webroot'
    if (-not (Test-Path $defaultWebroot)) {
        New-Item -ItemType Directory -Path $defaultWebroot -Force | Out-Null
    }
    $resolvedWebroot = (Resolve-Path $defaultWebroot).Path
}

$env:WEBROOT_PATH = $resolvedWebroot

$adminPasswordFile = Join-Path $resolvedWebroot 'admin_password.txt'
if (-not (Test-Path $adminPasswordFile)) {
    Set-Content -Path $adminPasswordFile -Value 'printstudio' -Encoding UTF8 -NoNewline
}

if ($AdminPassword) {
    Write-Host "Updating admin password file" -ForegroundColor Cyan
    Set-Content -Path $adminPasswordFile -Value $AdminPassword -Encoding UTF8 -NoNewline
}

$env:HOST = $BindAddress
$env:PORT = $Port

Write-Host "Starting development server on http://$BindAddress`:$Port" -ForegroundColor Green
& $venvPython app.py
