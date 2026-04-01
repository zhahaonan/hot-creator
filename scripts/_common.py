"""
hot-creator shared utilities.
JSON I/O, time helpers, platform mapping, error handling, CLI framework.
Input validation, structured errors, version reporting.
"""

import sys
import json
import argparse
import os
import time
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path


def _read_version_file() -> str:
    vf = Path(__file__).resolve().parent.parent / "VERSION"
    if vf.exists():
        line = vf.read_text(encoding="utf-8").strip().splitlines()[0].strip()
        if line and len(line) < 64:
            return line
    return "0.0.0"


VERSION = _read_version_file()
SKILL_ROOT = Path(__file__).resolve().parent.parent

# 上游版本文件（与仓库根目录 VERSION 同步发布）
UPSTREAM_VERSION_URL = os.environ.get(
    "HOT_CREATOR_VERSION_URL",
    "https://raw.githubusercontent.com/zhahaonan/hot-creator/main/VERSION",
)
UPSTREAM_REPO_URL = os.environ.get(
    "HOT_CREATOR_REPO_URL",
    "https://github.com/zhahaonan/hot-creator",
)
VERSION_CHECK_CACHE = SKILL_ROOT / "output" / ".version_check_cache"


def version_tuple(ver: str) -> tuple:
    """Parse semver-ish string to tuple for compare (digits only per segment)."""
    parts = []
    for seg in ver.strip().split("."):
        num = ""
        for ch in seg:
            if ch.isdigit():
                num += ch
            else:
                break
        parts.append(int(num) if num else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:4])


def upstream_is_newer(local: str, remote: str) -> bool:
    return version_tuple(remote) > version_tuple(local)


def fetch_upstream_version(timeout: float = 3.0) -> str | None:
    try:
        import requests
        r = requests.get(UPSTREAM_VERSION_URL.strip(), timeout=timeout)
        if not r.ok:
            return None
        line = r.text.strip().splitlines()[0].strip()
        if line and len(line) < 64 and line[0].isdigit():
            return line
    except Exception:
        pass
    return None


def warn_if_newer_upstream(cache_hours: int = 24) -> None:
    """
    If local VERSION is older than upstream GitHub VERSION, print stderr hint.
    Cached to avoid hitting GitHub on every script run. Disable: HOT_CREATOR_SKIP_UPDATE_CHECK=1
    """
    if os.environ.get("HOT_CREATOR_SKIP_UPDATE_CHECK", "").strip():
        return
    local = VERSION
    now = time.time()
    remote = None
    try:
        VERSION_CHECK_CACHE.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    if VERSION_CHECK_CACHE.exists():
        try:
            data = json.loads(VERSION_CHECK_CACHE.read_text(encoding="utf-8"))
            checked = float(data.get("checked_at", 0))
            if now - checked < cache_hours * 3600:
                remote = data.get("remote")
        except Exception:
            pass
    if remote is None:
        remote = fetch_upstream_version()
        try:
            VERSION_CHECK_CACHE.write_text(
                json.dumps({"checked_at": now, "remote": remote}, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass
    if not remote:
        return
    if upstream_is_newer(local, remote):
        print(
            "\n[hot-creator] —— 有新版本 ——\n"
            f"  当前本地: {local}\n"
            f"  上游仓库: {remote}\n"
            f"  请在 skill 目录执行: git pull origin main\n"
            f"  或重新安装: {UPSTREAM_REPO_URL}\n"
            f"  跳过此提示: 环境变量 HOT_CREATOR_SKIP_UPDATE_CHECK=1\n"
            f"  自建镜像: 设置 HOT_CREATOR_VERSION_URL / HOT_CREATOR_REPO_URL\n",
            file=sys.stderr,
        )

# Auto-load .env file if present (for standalone CLI use)
_env_file = SKILL_ROOT / ".env"
if _env_file.exists():
    for line in _env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if key and key not in os.environ:
                os.environ[key] = value

# --- Platform registry ---
# type: "hotlist" = 热门榜单（积累热度）, "realtime" = 实时新闻流（刚发生的）, "social" = 社媒（需 web-access）
# column: 便于按领域筛选

PLATFORMS = {
    # ── 热门榜单 (hotlist) ──
    "weibo":               {"name": "微博",         "type": "hotlist",  "column": "china"},
    "douyin":              {"name": "抖音",         "type": "hotlist",  "column": "china"},
    "zhihu":               {"name": "知乎",         "type": "hotlist",  "column": "china"},
    "baidu":               {"name": "百度热搜",     "type": "hotlist",  "column": "china"},
    "toutiao":             {"name": "今日头条",     "type": "hotlist",  "column": "china"},
    "bilibili-hot-search": {"name": "B站",         "type": "hotlist",  "column": "china"},
    "thepaper":            {"name": "澎湃新闻",    "type": "hotlist",  "column": "china"},
    "hupu":                {"name": "虎扑",         "type": "hotlist",  "column": "china"},
    "tieba":               {"name": "百度贴吧",     "type": "hotlist",  "column": "china"},
    "coolapk":             {"name": "酷安",         "type": "hotlist",  "column": "tech"},
    "douban":              {"name": "豆瓣",         "type": "hotlist",  "column": "china"},
    "ifeng":               {"name": "凤凰网",       "type": "hotlist",  "column": "china"},
    "nowcoder":            {"name": "牛客",         "type": "hotlist",  "column": "china"},
    "tencent-hot":         {"name": "腾讯新闻",     "type": "hotlist",  "column": "china"},
    "freebuf":             {"name": "Freebuf",      "type": "hotlist",  "column": "tech"},
    "qqvideo-tv-hotsearch":{"name": "腾讯视频",     "type": "hotlist",  "column": "china"},
    "iqiyi-hot-ranklist":  {"name": "爱奇艺",       "type": "hotlist",  "column": "china"},
    "chongbuluo-hot":      {"name": "虫部落",       "type": "hotlist",  "column": "china"},
    "36kr-renqi":          {"name": "36氪人气榜",   "type": "hotlist",  "column": "tech"},
    "wallstreetcn-hot":    {"name": "华尔街见闻",   "type": "hotlist",  "column": "finance"},
    "cls-hot":             {"name": "财联社热门",   "type": "hotlist",  "column": "finance"},
    "xueqiu-hotstock":     {"name": "雪球",         "type": "hotlist",  "column": "finance"},
    "hackernews":          {"name": "Hacker News",  "type": "hotlist",  "column": "tech"},
    "producthunt":         {"name": "Product Hunt", "type": "hotlist",  "column": "tech"},
    "github-trending-today":{"name": "GitHub",      "type": "hotlist",  "column": "tech"},
    "sspai":               {"name": "少数派",       "type": "hotlist",  "column": "tech"},
    "juejin":              {"name": "稀土掘金",     "type": "hotlist",  "column": "tech"},
    "steam":               {"name": "Steam",        "type": "hotlist",  "column": "world"},
    # ── 实时新闻流 (realtime) ──
    "zaobao":              {"name": "联合早报",     "type": "realtime", "column": "world"},
    "wallstreetcn-quick":  {"name": "华尔街见闻快讯","type": "realtime", "column": "finance"},
    "36kr-quick":          {"name": "36氪快讯",     "type": "realtime", "column": "tech"},
    "cls-telegraph":       {"name": "财联社电报",   "type": "realtime", "column": "finance"},
    "ithome":              {"name": "IT之家",       "type": "realtime", "column": "tech"},
    "gelonghui":           {"name": "格隆汇",       "type": "realtime", "column": "finance"},
    "jin10":               {"name": "金十数据",     "type": "realtime", "column": "finance"},
    "fastbull-express":    {"name": "法布财经快讯", "type": "realtime", "column": "finance"},
    # ── 社媒（需 web-access skill）──
    "xiaohongshu":         {"name": "小红书",       "type": "social",   "column": "china"},
    "douyin_realtime":     {"name": "抖音实时",     "type": "social",   "column": "china"},
    "weibo_rising":        {"name": "微博上升",     "type": "social",   "column": "china"},
}

NEWSNOW_API = "https://newsnow.busiyi.world/api/s"

OUTPUT_DIR = SKILL_ROOT / "output"


def platform_name(platform_id: str) -> str:
    entry = PLATFORMS.get(platform_id)
    return entry["name"] if entry else platform_id


# Brief.materials: human-readable category names + atomic lines (not 一、二、三 outline blobs)
MATERIAL_CATEGORY_LABELS = {
    "data_points": "核心数据",
    "quotes": "引用金句",
    "controversies": "争议话题",
    "emotion_triggers": "情绪触点",
    "knowledge_gems": "知识增量",
    "media_hooks": "镜头 / 画面素材",
    "screenshot_lines": "封面与字幕条文案",
    "sound_bites": "口播短句（≤20字优先）",
    "sources": "信源与报道",
    "b_roll": "B-roll 建议",
}


def material_category_label(key: str) -> str:
    return MATERIAL_CATEGORY_LABELS.get(key, key.replace("_", " ").title())


def format_material_item(item) -> str:
    """One atomic fact/quote/hook; supports dict with fact/source/how_to_use."""
    if item is None:
        return ""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        fact = (
            item.get("fact")
            or item.get("content")
            or item.get("text")
            or item.get("line")
            or item.get("title")
            or ""
        )
        takeaway = item.get("takeaway") or item.get("摘要") or ""
        if not fact and takeaway:
            fact = takeaway
        source = item.get("source") or item.get("出处") or ""
        url = item.get("url") or ""
        use = item.get("how_to_use") or item.get("usage") or item.get("用于") or ""
        platform = item.get("platform") or item.get("适合平台") or ""
        bits = []
        if fact:
            bits.append(str(fact).strip())
        if url:
            bits.append(f"链接 {url}")
        elif source and str(source) not in str(fact):
            bits.append(f"来源 {source}")
        if platform:
            bits.append(f"适合 {platform}")
        if use:
            bits.append(f"用法 {use.strip()}")
        if bits:
            return " · ".join(bits)
        try:
            return json.dumps(item, ensure_ascii=False)
        except Exception:
            return str(item)
    return str(item).strip()


def retry_request(fn, max_retries: int = 3, backoff: float = 1.0, on_fail: str = ""):
    """
    Retry a callable up to max_retries times with exponential backoff.
    fn should be a zero-arg callable that may raise. Returns the result or raises.
    """
    last_err = None
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                wait = backoff * (2 ** attempt)
                print(f"[retry] Attempt {attempt+1} failed: {e}. Retrying in {wait:.1f}s...",
                      file=sys.stderr)
                time.sleep(wait)
    if on_fail:
        print(f"[retry] All {max_retries} attempts failed: {on_fail}", file=sys.stderr)
    raise last_err


def check_deps(packages: list[str]) -> list[str]:
    """
    Check if packages are importable. Returns list of missing package names.
    Does NOT auto-install — caller decides what to do.
    """
    missing = []
    for pkg in packages:
        import_name = pkg.split(">=")[0].split("==")[0].strip()
        if import_name == "pyyaml":
            import_name = "yaml"
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg)
    return missing


def ensure_deps(packages: list[str]):
    """Check deps and auto-install missing ones via pip."""
    missing = check_deps(packages)
    if not missing:
        return
    print(f"[deps] Missing: {', '.join(missing)}. Auto-installing...", file=sys.stderr)
    import subprocess
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet"] + missing,
            stdout=subprocess.DEVNULL,
        )
        print(f"[deps] Installed: {', '.join(missing)}", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        fail(f"Failed to auto-install dependencies: {e}\n"
             f"Run manually: pip install {' '.join(missing)}")


def china_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def today_str() -> str:
    return china_now().strftime("%Y-%m-%d")


def default_output_path(tool_name: str, ext: str = "json") -> str:
    """Generate default output path: output/{date}-{tool}.{ext}"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return str(OUTPUT_DIR / f"{today_str()}-{tool_name}.{ext}")


# --- JSON I/O ---

def read_json_input(args) -> dict:
    """Read JSON from --input file or stdin. Non-blocking: won't hang if stdin has no data."""
    if hasattr(args, "input") and args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            return json.load(f)
    if not sys.stdin.isatty():
        import select
        if sys.platform == "win32":
            import msvcrt
            if msvcrt.kbhit() or _stdin_has_data():
                return json.load(sys.stdin)
        else:
            ready, _, _ = select.select([sys.stdin], [], [], 0.1)
            if ready:
                return json.load(sys.stdin)
    return {}


def _stdin_has_data() -> bool:
    """Windows-compatible check for whether stdin has pending data."""
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
        if handle == -1:
            return False
        avail = wintypes.DWORD(0)
        result = kernel32.PeekNamedPipe(
            handle, None, 0, None, ctypes.byref(avail), None
        )
        return result != 0 and avail.value > 0
    except Exception:
        return False


def write_json_output(data: dict, args):
    """Write JSON to --output file or stdout."""
    indent = 2 if (hasattr(args, "pretty") and args.pretty) else None
    text = json.dumps(data, ensure_ascii=False, indent=indent)
    if hasattr(args, "output") and args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.buffer.write(text.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")


# --- CLI framework ---

def base_argparser(description: str) -> argparse.ArgumentParser:
    """Create an ArgumentParser with common flags."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--input", "-i", help="Input JSON file (default: stdin)")
    parser.add_argument("--output", "-o", help="Output JSON file (default: stdout)")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    parser.add_argument("--schema", action="store_true", help="Print tool JSON Schema and exit")
    parser.add_argument("--version", action="store_true", help="Print tool version and exit")
    return parser


def handle_schema(args, schema: dict):
    """If --schema flag is set, print schema and exit. If --version, print version."""
    if hasattr(args, "version") and args.version:
        print(json.dumps({"version": VERSION, "tool": schema.get("name", "unknown")}, ensure_ascii=False))
        sys.exit(0)
    if args.schema:
        print(json.dumps(schema, ensure_ascii=False, indent=2))
        sys.exit(0)


# --- Input validation ---

def validate_required_fields(data: dict, fields: list[str], context: str = "input") -> list[str]:
    """Check required fields exist and are non-empty. Returns list of error messages."""
    errors = []
    for field in fields:
        if field not in data:
            errors.append(f"{context}: missing required field '{field}'")
        elif data[field] is None or (isinstance(data[field], (list, dict, str)) and not data[field]):
            errors.append(f"{context}: field '{field}' is empty")
    return errors


def validate_input(data: dict, schema: dict) -> list[str]:
    """Lightweight input validation against schema. Returns list of error messages."""
    errors = []
    input_schema = schema.get("input", {})
    required = input_schema.get("required", [])
    errors.extend(validate_required_fields(data, required))

    props = input_schema.get("properties", {})
    for key, val in data.items():
        if key in props:
            expected_type = props[key].get("type")
            if expected_type == "array" and not isinstance(val, list):
                errors.append(f"'{key}' should be array, got {type(val).__name__}")
            elif expected_type == "object" and not isinstance(val, dict):
                errors.append(f"'{key}' should be object, got {type(val).__name__}")
            elif expected_type == "string" and not isinstance(val, str):
                errors.append(f"'{key}' should be string, got {type(val).__name__}")
            elif expected_type == "integer" and not isinstance(val, int):
                errors.append(f"'{key}' should be integer, got {type(val).__name__}")
    return errors


# --- Error helpers ---

def fail(message: str, code: int = 1):
    """Print structured error JSON to stderr and exit."""
    error_payload = {
        "error": message,
        "code": code,
        "hint": _error_hint(message),
    }
    print(json.dumps(error_payload, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def structured_error(tool_name: str, error: Exception, context: str = "") -> dict:
    """Build a structured error dict for inclusion in tool output."""
    return {
        "tool": tool_name,
        "error_type": type(error).__name__,
        "message": str(error),
        "context": context,
        "traceback": traceback.format_exc().split("\n")[-3] if traceback.format_exc() else "",
    }


def parse_ai_json(text: str) -> dict | list:
    """
    Robustly parse AI-generated JSON: strips markdown fences, recovers truncated
    arrays/objects, and handles common AI output quirks.
    """
    import re
    cleaned = text.strip()

    fence = re.search(r"```(?:json)?\s*\n(.*?)```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    elif cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    for suffix in ["]}", "}", "]", '"}', '"}]', '"}]}']:
        try:
            return json.loads(cleaned + suffix)
        except json.JSONDecodeError:
            continue

    bracket = cleaned.find("[")
    brace = cleaned.find("{")
    if bracket >= 0 and (brace < 0 or bracket < brace):
        start = bracket
    elif brace >= 0:
        start = brace
    else:
        raise json.JSONDecodeError("No JSON structure found in AI response", cleaned, 0)

    fragment = cleaned[start:]
    try:
        return json.loads(fragment)
    except json.JSONDecodeError:
        for suffix in ["]}", "}", "]", '"}', '"}]', '"}]}']:
            try:
                return json.loads(fragment + suffix)
            except json.JSONDecodeError:
                continue

    raise json.JSONDecodeError("Could not parse AI response as JSON", cleaned, 0)


def _error_hint(message: str) -> str:
    """Generate actionable hint based on common error patterns."""
    msg = message.lower()
    if "api_key" in msg or "api key" in msg:
        return "Set AI_API_KEY in .env or pass --api-key. Not needed in Agent-native mode."
    if "litellm" in msg:
        return "Run: pip install litellm"
    if "feedparser" in msg:
        return "Run: pip install feedparser"
    if "openpyxl" in msg:
        return "Run: pip install openpyxl"
    if "cdp" in msg or "chrome" in msg:
        return "Browser operations are handled by the web-access skill, not hot-creator."
    if "timeout" in msg:
        return "Network timeout. Check connectivity or try a single platform first."
    if "json" in msg and ("parse" in msg or "decode" in msg):
        return "AI response was not valid JSON. Try again or switch model."
    return ""
