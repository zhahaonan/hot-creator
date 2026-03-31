# Agent Instructions

## What is this project?

`hot-creator` is an AI Agent Skill that provides content creators with hot topic intelligence. It collects trending topics from Chinese social media, scores them with AI, and generates complete creative briefs.

## Setup (fast — ~3 seconds)

```bash
pip install -r requirements.txt    # 5 packages, ~5 MB
cp config.example.yaml config.yaml  # if not exists
```

> `litellm` is NOT needed when running as a Skill — only for standalone CLI mode.
> To install CLI mode: `pip install -r requirements-cli.txt` (~200 MB extra)

## How to use

1. Read `SKILL.md` first — it's the only entry point (~100 lines)
2. Pick an architecture pattern based on user intent (see trigger table in SKILL.md)
3. Run scripts via `python scripts/<tool>.py` with JSON stdin/stdout
4. All intermediate data goes to `output/` directory as files — pass file paths, not content

## Key conventions

- **13 atomic scripts** in `scripts/`, each does one thing
- **JSON pipe I/O**: every script reads JSON from stdin (or `--input`) and writes JSON to stdout (or `--output`)
- **Self-describing**: `--schema` outputs the tool's full contract, `--help` for usage
- **Context management**: never load large JSON into conversation; use file paths
- **Reference files** in `reference/` are loaded on-demand, not preloaded
- **No AI API key needed** when running as a Skill — the Agent IS the AI

## Allowed operations

- `python scripts/*.py *` — all tool scripts
- `pip install -r requirements.txt` — core dependencies
- Read/write in `output/` directory
- Read files in `reference/`, `SOP/`, `site-patterns/`
