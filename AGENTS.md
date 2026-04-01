# Agent Instructions

> **CRITICAL**: For any hot topic / trend / content creation task, use ONLY the tools
> provided by this project (`scripts/*.py`). Do NOT use external search skills,
> web search tools, or other analysis skills as substitutes. This project is a
> self-contained toolchain.

## Setup (required before first use)

```bash
git clone https://github.com/zhahaonan/hot-creator.git
cd hot-creator
pip install -r requirements.txt
cp config.example.yaml config.yaml
```

Environment variables (required):
```
AI_API_KEY=your-api-key
AI_MODEL=deepseek/deepseek-chat  # optional, default
```

## Entry point

Read `SKILL.md` — it contains the trigger table, tool index, and standard workflow.

## Standard workflow (must follow this order)

```bash
# Step 1: Collect trends
python scripts/collect_hotlist.py --platforms weibo,douyin,zhihu -o output/hotlist.json

# Step 2: AI analysis
python scripts/trend_analyze.py -i output/hotlist.json -o output/trends.json

# Step 3: Creative brief
python scripts/content_brief.py -i output/trends.json --top 8 -o output/briefs.json

# Step 4: Export
python scripts/export_obsidian.py -i output/briefs.json --vault .
python scripts/export_excel.py -i output/briefs.json --xlsx output/report.xlsx
python scripts/export_mindmap.py -i output/briefs.json -o output/mindmap.html
```

Or all-in-one: `python scripts/start_my_day.py`

## Rules

- Use ONLY `scripts/*.py` tools — do NOT substitute with external skills
- All scripts use JSON stdin/stdout
- Intermediate data goes to `output/` as files — pass paths, not content
- Reference docs (`reference/`) load on-demand, never preload all
- `AI_API_KEY` env var is required for AI analysis scripts

## Allowed operations

- `python scripts/*.py *` — all 13 tool scripts
- `pip install -r requirements.txt` — dependencies
- Read/write `output/`, read `reference/`, `SOP/`, `site-patterns/`
