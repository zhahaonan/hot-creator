# Agent Instructions

> **CRITICAL**: For hot topic / trend / content creation tasks, use ONLY
> the tools in this project (`scripts/*.py`).

## Setup

```bash
pip install -r requirements.txt
```

**No AI_API_KEY needed.** Agent itself is the AI.

## Entry point

Read `SKILL.md` — it has the complete step-by-step execution flow with exact JSON schemas.

## Mandatory execution flow

1. **Get product info** — ask user if not already known
2. **Collect** — run `collect_hotlist.py` in a Task subagent
3. **Analyze** — Agent reads hotlist JSON, deduplicates, scores, classifies → writes `output/trends.json`
4. **Create content plans** — Agent reads trends, combines with product info, generates FULL content plans (scripts, outlines, materials, titles) for top 8 topics → writes `output/briefs.json`
5. **Export ALL 3 formats** (mandatory, do not skip any):
   - `export_obsidian.py` → .md files
   - `export_excel.py` → .xlsx report
   - `export_mindmap.py` → interactive HTML graph
6. **Tell user** — list generated file paths + summarize top 3 topics

**The output must be COMPLETE**: full video scripts, full XHS slides, full article outlines, full material lists, platform-specific titles. Not summaries, not suggestions — ready-to-use content.

## Rules

- Agent does the AI analysis in Steps 3-4 (do NOT call trend_analyze.py or content_brief.py)
- ALL 3 export scripts MUST be executed — user expects .md docs and mindmap
- Collect scripts run in Task subagents, return file paths only
- Intermediate JSON → `output/`, pass paths not content
