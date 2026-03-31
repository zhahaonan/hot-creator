#!/usr/bin/env bash
# hot-creator quick setup — works on macOS / Linux / WSL
set -e

echo "=== hot-creator setup ==="

# Prefer uv (10-100x faster than pip), fallback to pip
if command -v uv &>/dev/null; then
  echo "[*] Using uv (fast mode)"
  INSTALL="uv pip install"
elif command -v pip3 &>/dev/null; then
  INSTALL="pip3 install"
elif command -v pip &>/dev/null; then
  INSTALL="pip install"
else
  echo "[!] No pip or uv found. Install Python first."
  exit 1
fi

# Core deps only (~5 MB, 3 seconds)
echo "[1/2] Installing core dependencies..."
$INSTALL -r requirements.txt

# Config
if [ ! -f config.yaml ]; then
  echo "[2/2] Creating config from example..."
  cp config.example.yaml config.yaml
fi

echo ""
echo "=== Done! ==="
echo ""
echo "As Cursor/Claude Code Skill:"
echo '  Just ask: "帮我看看现在什么热点"'
echo ""
echo "As standalone CLI (optional, adds ~200MB):"
echo "  $INSTALL -r requirements-cli.txt"
echo "  cp .env.example .env  # add your AI_API_KEY"
echo "  python scripts/start_my_day.py"
