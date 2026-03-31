#!/usr/bin/env python3
"""
start_my_day — One-command orchestrator for hot-creator.
Runs the full pipeline: collect → analyze → brief → export + knowledge base update.
Equivalent to evil-read-arxiv's "start my day" trigger.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import json
import subprocess
import time
from pathlib import Path
from _common import (
    base_argparser, handle_schema, fail, today_str, OUTPUT_DIR, SKILL_ROOT
)

SCHEMA = {
    "name": "start_my_day",
    "description": "One-command orchestrator: collect → analyze → brief → export (Obsidian + Excel + Graph) + knowledge base update. Supports product mode with --profile.",
    "input": {
        "type": "object",
        "properties": {
            "profile": {"type": "string", "description": "Path to product profile JSON (enables product x trend mode)"},
            "product_text": {"type": "string", "description": "Raw product description text (auto-generates profile)"},
        },
    },
    "output": {
        "type": "object",
        "properties": {
            "steps": {"type": "array", "description": "Execution log per step"},
            "outputs": {"type": "object", "description": "Paths to all generated files"},
        },
    },
    "examples": {
        "cli_full": "python scripts/start_my_day.py",
        "cli_product": "python scripts/start_my_day.py --profile profile.json",
        "cli_product_text": "python scripts/start_my_day.py --product-text '我们是一个AI写作助手...'",
        "cli_skip": "python scripts/start_my_day.py --skip-collect -i output/briefs.json",
        "cli_graph": "python scripts/start_my_day.py --days 7",
    },
}

PYTHON = sys.executable
SCRIPTS = SKILL_ROOT / "scripts"


def load_config() -> dict:
    """Load config.yaml if available, else return defaults."""
    config_path = SKILL_ROOT / "config.yaml"
    if config_path.exists():
        try:
            # PyYAML is optional; fall back to basic parsing
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except ImportError:
            return _parse_yaml_lite(config_path)
    return {}


def _parse_yaml_lite(path: Path) -> dict:
    """Minimal YAML-like parser for config (supports flat keys + lists)."""
    config = {}
    current_section = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()
            if not line or line.startswith("#"):
                continue
            if not line.startswith(" ") and line.endswith(":"):
                current_section = line[:-1].strip()
                config[current_section] = {}
            elif ":" in line and current_section:
                key, _, val = line.strip().partition(":")
                val = val.strip().strip('"').strip("'")
                if val.startswith("[") and val.endswith("]"):
                    val = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",") if v.strip()]
                elif val.lower() in ("true", "false"):
                    val = val.lower() == "true"
                elif val.isdigit():
                    val = int(val)
                config[current_section][key.strip()] = val
    return config


def log(step: str, msg: str, level: str = "INFO"):
    """Print structured log to stderr."""
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] [{step}] {msg}", file=sys.stderr)


def run_script(script_name: str, args: list[str], step_name: str) -> tuple[bool, str]:
    """Run a Python script and return (success, output_path_or_error)."""
    cmd = [PYTHON, str(SCRIPTS / script_name)] + args
    log(step_name, f"Running: {script_name} {' '.join(args)}")
    start = time.time()

    try:
        result = subprocess.run(
            cmd, capture_output=True, timeout=300, cwd=str(SKILL_ROOT),
        )
        elapsed = time.time() - start

        stdout = result.stdout.decode("utf-8", errors="replace").strip() if result.stdout else ""
        stderr = result.stderr.decode("utf-8", errors="replace").strip() if result.stderr else ""

        if result.returncode != 0:
            err = stderr or stdout
            log(step_name, f"FAILED ({elapsed:.1f}s): {err[:200]}", "ERROR")
            return False, err[:500]

        log(step_name, f"Done ({elapsed:.1f}s)")
        return True, stdout

    except subprocess.TimeoutExpired:
        log(step_name, "TIMEOUT (300s)", "ERROR")
        return False, "Timeout after 300s"
    except Exception as e:
        log(step_name, f"Exception: {e}", "ERROR")
        return False, str(e)


def main():
    parser = base_argparser("One-command orchestrator: collect → analyze → brief → export + KB")
    parser.add_argument("--skip-collect", action="store_true",
                        help="Skip collection, use existing data (requires -i with briefs or merged data)")
    parser.add_argument("--skip-analyze", action="store_true",
                        help="Skip analysis, expect -i to contain briefed_trends")
    parser.add_argument("--days", type=int, default=7,
                        help="Rolling window for cumulative graph (default: 7)")
    parser.add_argument("--vault", "-v", type=str, default=None,
                        help="Obsidian vault path (default: from config.yaml or ./HotCreator)")
    parser.add_argument("--platforms", "-p", type=str, default=None,
                        help="Hotlist platforms, comma-separated (default: from config.yaml)")
    parser.add_argument("--profile", type=str, default=None,
                        help="Path to product profile JSON (enables product x trend mode)")
    parser.add_argument("--product-text", type=str, default=None,
                        help="Raw product description text (auto-generates profile via product_profile)")
    parser.add_argument("--no-export", action="store_true",
                        help="Skip exports, only collect+analyze+brief+KB")
    args = parser.parse_args()
    handle_schema(args, SCHEMA)

    config = load_config()
    date = today_str()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    collect_cfg = config.get("collect", {})
    analyze_cfg = config.get("analyze", {})
    graph_cfg = config.get("graph", {})
    product_cfg = config.get("product", {})
    vault_path = args.vault or config.get("vault_path", "./HotCreator")
    rolling_days = args.days or graph_cfg.get("rolling_days", 7)
    platforms = args.platforms or ",".join(collect_cfg.get("hotlist_platforms", ["weibo", "douyin", "zhihu", "baidu"]))
    top_n = analyze_cfg.get("top_n", 8)
    batch_size = analyze_cfg.get("batch_size", 2)

    steps = []
    outputs = {}

    profile_path = args.profile or product_cfg.get("default_profile", "")
    product_text = getattr(args, "product_text", None)

    log("main", f"=== HotCreator Start My Day · {date} ===")
    mode_label = "product x trend" if (profile_path or product_text) else "generic"
    log("main", f"Vault: {vault_path} | Platforms: {platforms} | Graph days: {rolling_days} | Mode: {mode_label}")

    # ========== STEP 0: Product Profile (if requested) ==========
    if product_text and not profile_path:
        profile_path = str(OUTPUT_DIR / f"{date}-profile.json")
        ok, out = run_script("product_profile.py",
                             ["--text", product_text, "-o", profile_path], "product_profile")
        steps.append({"step": "product_profile", "status": "ok" if ok else "error"})
        if not ok:
            log("main", "product_profile failed, falling back to generic mode", "WARN")
            profile_path = ""
        else:
            outputs["profile"] = profile_path

    if profile_path and Path(profile_path).exists():
        outputs["profile"] = profile_path
        log("main", f"Product profile: {profile_path}")

    # ========== STEP 1: Collect ==========
    hotlist_path = str(OUTPUT_DIR / f"{date}-hotlist.json")
    rss_path = str(OUTPUT_DIR / f"{date}-rss.json")
    merged_path = str(OUTPUT_DIR / f"{date}-merged.json")

    if args.skip_collect and args.skip_analyze:
        log("collect", "Skipped (--skip-collect --skip-analyze)")
        steps.append({"step": "collect", "status": "skipped"})
        steps.append({"step": "analyze", "status": "skipped"})
        steps.append({"step": "brief", "status": "skipped"})

        input_data = {}
        if hasattr(args, "input") and args.input:
            with open(args.input, "r", encoding="utf-8") as f:
                input_data = json.load(f)
        briefs_path = args.input or str(OUTPUT_DIR / "briefs.json")

    elif args.skip_collect:
        log("collect", "Skipped (--skip-collect)")
        steps.append({"step": "collect", "status": "skipped"})

        if not (hasattr(args, "input") and args.input):
            fail("--skip-collect requires -i with merged data or briefs.json")
        merged_path = args.input
        briefs_path = str(OUTPUT_DIR / f"{date}-briefs.json")

        # trend_analyze
        trends_path = str(OUTPUT_DIR / f"{date}-trends.json")
        ok, out = run_script("trend_analyze.py", ["-i", merged_path, "-o", trends_path], "analyze")
        steps.append({"step": "analyze", "status": "ok" if ok else "error", "detail": out[:200] if not ok else ""})
        if not ok:
            log("main", "trend_analyze failed, cannot continue", "ERROR")
            _finish(steps, outputs, success=False)
            return

        # content_brief
        brief_args = ["-i", trends_path, "-o", briefs_path, "--top", str(top_n), "--batch-size", str(batch_size)]
        if profile_path and Path(profile_path).exists():
            brief_args += ["--profile", profile_path]
        ok, out = run_script("content_brief.py", brief_args, "brief")
        steps.append({"step": "brief", "status": "ok" if ok else "error", "detail": out[:200] if not ok else ""})
        if not ok:
            log("main", "content_brief failed, cannot continue", "ERROR")
            _finish(steps, outputs, success=False)
            return

    else:
        # Full collection
        ok1, out1 = run_script("collect_hotlist.py",
                               ["-o", hotlist_path, "-p", platforms], "collect_hotlist")
        steps.append({"step": "collect_hotlist", "status": "ok" if ok1 else "error"})

        rss_ok = True
        if collect_cfg.get("rss_enabled", True):
            ok2, out2 = run_script("collect_rss.py", ["-o", rss_path], "collect_rss")
            steps.append({"step": "collect_rss", "status": "ok" if ok2 else "error"})
            rss_ok = ok2

        if not ok1:
            log("main", "Hotlist collection failed, cannot continue", "ERROR")
            _finish(steps, outputs, success=False)
            return

        # Merge items
        log("merge", "Merging collected data")
        all_items = []
        seen_titles = set()
        for fpath in [hotlist_path, rss_path]:
            if Path(fpath).exists():
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("items", []):
                    title = item.get("title", "")
                    if title and title not in seen_titles:
                        seen_titles.add(title)
                        all_items.append(item)

        merged = {"items": all_items}
        with open(merged_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False)
        log("merge", f"Merged {len(all_items)} unique items")
        steps.append({"step": "merge", "status": "ok", "count": len(all_items)})

        # trend_analyze
        trends_path = str(OUTPUT_DIR / f"{date}-trends.json")
        ok, out = run_script("trend_analyze.py", ["-i", merged_path, "-o", trends_path], "analyze")
        steps.append({"step": "analyze", "status": "ok" if ok else "error"})
        if not ok:
            log("main", "trend_analyze failed, cannot continue", "ERROR")
            _finish(steps, outputs, success=False)
            return

        # content_brief
        briefs_path = str(OUTPUT_DIR / f"{date}-briefs.json")
        brief_args = ["-i", trends_path, "-o", briefs_path, "--top", str(top_n), "--batch-size", str(batch_size)]
        if profile_path and Path(profile_path).exists():
            brief_args += ["--profile", profile_path]
        ok, out = run_script("content_brief.py", brief_args, "brief")
        steps.append({"step": "brief", "status": "ok" if ok else "error"})
        if not ok:
            log("main", "content_brief failed, cannot continue", "ERROR")
            _finish(steps, outputs, success=False)
            return

    outputs["briefs"] = briefs_path

    # ========== STEP 2: Knowledge Base Update ==========
    log("kb", "Updating knowledge base")
    ok, out = run_script("knowledge_base.py", ["--append", "-i", briefs_path], "kb")
    steps.append({"step": "knowledge_base", "status": "ok" if ok else "error"})
    outputs["knowledge_base"] = str(OUTPUT_DIR / "knowledge_base.json")

    if args.no_export:
        log("main", "Exports skipped (--no-export)")
        _finish(steps, outputs, success=True)
        return

    # ========== STEP 3: Exports ==========
    # Obsidian
    obsidian_args = ["-i", briefs_path, "--vault", vault_path]
    ok, out = run_script("export_obsidian.py", obsidian_args, "obsidian")
    steps.append({"step": "export_obsidian", "status": "ok" if ok else "error"})
    if ok:
        try:
            obsidian_result = json.loads(out)
            outputs["obsidian_dashboard"] = obsidian_result.get("dashboard", "")
            outputs["obsidian_topics"] = obsidian_result.get("topics", [])
            if obsidian_result.get("copywriting"):
                outputs["obsidian_copywriting"] = obsidian_result["copywriting"]
        except json.JSONDecodeError:
            pass

    # Excel
    excel_path = str(OUTPUT_DIR / f"hot-creator-{date}.xlsx")
    ok, out = run_script("export_excel.py", ["-i", briefs_path, "--xlsx", excel_path], "excel")
    steps.append({"step": "export_excel", "status": "ok" if ok else "error"})
    if ok:
        outputs["excel"] = excel_path

    # Mindmap (with cumulative graph support)
    mindmap_path = str(OUTPUT_DIR / f"hot-creator-mindmap-{date}.html")
    mindmap_args = ["-i", briefs_path, "-o", mindmap_path]
    if rolling_days > 0:
        mindmap_args += ["--cumulative", "--days", str(rolling_days)]
    ok, out = run_script("export_mindmap.py", mindmap_args, "mindmap")
    steps.append({"step": "export_mindmap", "status": "ok" if ok else "error"})
    if ok:
        outputs["mindmap"] = mindmap_path

    _finish(steps, outputs, success=True)


def _finish(steps: list, outputs: dict, success: bool):
    """Print final summary."""
    log("main", "=" * 50)
    ok_count = sum(1 for s in steps if s.get("status") == "ok")
    err_count = sum(1 for s in steps if s.get("status") == "error")
    skip_count = sum(1 for s in steps if s.get("status") == "skipped")

    log("main", f"Done: {ok_count} ok / {err_count} errors / {skip_count} skipped")

    if outputs:
        log("main", "Generated files:")
        for key, val in outputs.items():
            if isinstance(val, list):
                log("main", f"  {key}: {len(val)} files")
            else:
                log("main", f"  {key}: {val}")

    result = {"success": success, "steps": steps, "outputs": outputs}
    out = json.dumps(result, ensure_ascii=True, indent=2)
    sys.stdout.buffer.write(out.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")


if __name__ == "__main__":
    main()
