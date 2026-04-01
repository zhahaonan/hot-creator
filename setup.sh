#!/usr/bin/env bash
# hot-creator setup — macOS / Linux / WSL
set -e

echo "=== hot-creator setup ==="

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

echo "[1/2] Installing dependencies..."
$INSTALL -r requirements.txt

if [ ! -f config.yaml ]; then
  echo "[2/2] Creating config..."
  cp config.example.yaml config.yaml
fi

echo ""
echo "=== Done! ==="
echo "Set AI_API_KEY env var, then ask your Agent:"
echo '  "帮我看看现在什么热点"'
