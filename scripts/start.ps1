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

if ($AdminPassword) {
    $env:ADMIN_PASSWORD = $AdminPassword
}

if ($WebrootPath) {
    $resolvedWebroot = Resolve-Path $WebrootPath
    $env:WEBROOT_PATH = $resolvedWebroot.Path
}

$env:HOST = $BindAddress
$env:PORT = $Port

Write-Host "Starting development server on http://$BindAddress`:$Port" -ForegroundColor Green
& $venvPython app.py
