"""
hot-creator shared utilities.
JSON I/O, time helpers, platform mapping, error handling, CLI framework.
Input validation, structured errors, version reporting.
"""

import sys
import json
import argparse
import os
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

VERSION = "3.0.0"
SKILL_ROOT = Path(__file__).resolve().parent.parent

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

PLATFORMS = {
    "weibo":              {"name": "微博",       "type": "hotlist"},
    "douyin":             {"name": "抖音",       "type": "hotlist"},
    "zhihu":              {"name": "知乎",       "type": "hotlist"},
    "baidu":              {"name": "百度",       "type": "hotlist"},
    "toutiao":            {"name": "头条",       "type": "hotlist"},
    "bilibili-hot-search":{"name": "B站",       "type": "hotlist"},
    "36kr":               {"name": "36氪",      "type": "hotlist"},
    "ithome":             {"name": "IT之家",    "type": "hotlist"},
    "thepaper":           {"name": "澎湃新闻",  "type": "hotlist"},
    "cls-telegraph":      {"name": "财联社电报", "type": "hotlist"},
    "xiaohongshu":        {"name": "小红书",     "type": "social"},
    "douyin_realtime":    {"name": "抖音实时",   "type": "social"},
    "weibo_rising":       {"name": "微博上升",   "type": "social"},
}

NEWSNOW_API = "https://newsnow.busiyi.world/api/s"
CDP_PROXY_PORT = int(os.environ.get("CDP_PROXY_PORT", "3456"))
CDP_PROXY_BASE = f"http://127.0.0.1:{CDP_PROXY_PORT}"

OUTPUT_DIR = SKILL_ROOT / "output"


def platform_name(platform_id: str) -> str:
    entry = PLATFORMS.get(platform_id)
    return entry["name"] if entry else platform_id


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
        print(text)


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
        return "Ensure Chrome remote debugging is enabled and run: node scripts/cdp/check.mjs"
    if "timeout" in msg:
        return "Network timeout. Check connectivity or try a single platform first."
    if "json" in msg and ("parse" in msg or "decode" in msg):
        return "AI response was not valid JSON. Try again or switch model."
    return ""
