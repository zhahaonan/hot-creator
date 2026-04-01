#!/usr/bin/env bash
# Post-install hook for OpenClaw / AgentSkills
set -e
cd "$(dirname "$0")"

if command -v uv &>/dev/null; then
  uv pip install -r requirements.txt
elif command -v pip3 &>/dev/null; then
  pip3 install -r requirements.txt
elif command -v pip &>/dev/null; then
  pip install -r requirements.txt
fi

[ ! -f config.yaml ] && cp config.example.yaml config.yaml 2>/dev/null || true
echo "[hot-creator] Installed. Set AI_API_KEY env var, then read SKILL.md."
