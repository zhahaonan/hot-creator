# hot-creator setup — Windows PowerShell
$ErrorActionPreference = "Stop"

Write-Host "=== hot-creator setup ===" -ForegroundColor Cyan

$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) {
    Write-Host "[*] Using uv (fast mode)" -ForegroundColor Green
    $install = "uv pip install"
} else {
    $install = "pip install"
}

Write-Host "[1/2] Installing dependencies..."
Invoke-Expression "$install -r requirements.txt"

if (-not (Test-Path "config.yaml")) {
    Write-Host "[2/2] Creating config..."
    Copy-Item "config.example.yaml" "config.yaml"
}

Write-Host ""
Write-Host "=== Done! ===" -ForegroundColor Cyan
Write-Host 'Set AI_API_KEY env var, then ask your Agent:'
Write-Host '  "帮我看看现在什么热点"'
