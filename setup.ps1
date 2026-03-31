# hot-creator quick setup — Windows PowerShell
$ErrorActionPreference = "Stop"

Write-Host "=== hot-creator setup ===" -ForegroundColor Cyan

# Prefer uv, fallback to pip
$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) {
    Write-Host "[*] Using uv (fast mode)" -ForegroundColor Green
    $install = "uv pip install"
} else {
    $install = "pip install"
}

# Core deps only (~5 MB, 3 seconds)
Write-Host "[1/2] Installing core dependencies..."
Invoke-Expression "$install -r requirements.txt"

# Config
if (-not (Test-Path "config.yaml")) {
    Write-Host "[2/2] Creating config from example..."
    Copy-Item "config.example.yaml" "config.yaml"
}

Write-Host ""
Write-Host "=== Done! ===" -ForegroundColor Cyan
Write-Host ""
Write-Host 'As Cursor/Claude Code Skill:'
Write-Host '  Just ask: "帮我看看现在什么热点"'
Write-Host ""
Write-Host "As standalone CLI (optional, adds ~200MB):"
Write-Host "  $install -r requirements-cli.txt"
Write-Host '  cp .env.example .env  # add your AI_API_KEY'
Write-Host "  python scripts/start_my_day.py"
