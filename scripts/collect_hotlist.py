#!/usr/bin/env python3
"""
collect_hotlist — Fetch trending topics from public hotlist APIs.
Supports multiple platforms (Weibo, Douyin, Zhihu, Baidu, etc.).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import requests
import time
import random
from _common import (
    base_argparser, handle_schema, read_json_input, write_json_output,
    fail, NEWSNOW_API, PLATFORMS, platform_name, retry_request
)

SCHEMA = {
    "name": "collect_hotlist",
    "description": "Fetch trending topics from NewsNow API. Supports hotlist (热门) and realtime (实时) types.",
    "input": {
        "type": "object",
        "properties": {
            "platforms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Platform IDs to fetch. Defaults to all hotlist-type platforms.",
                "examples": [["weibo", "douyin", "zhihu"], ["baidu", "toutiao", "hupu"]]
            },
            "type": {
                "type": "string",
                "enum": ["hotlist", "realtime", "all"],
                "description": "Filter by type: hotlist=热门榜单, realtime=实时新闻流, all=both. Default: hotlist",
                "default": "hotlist"
            },
            "proxy_url": {
                "type": "string",
                "description": "HTTP proxy URL (optional)",
                "default": ""
            }
        }
    },
    "output": {
        "type": "object",
        "properties": {
            "source": {"type": "string", "const": "hotlist"},
            "collected_at": {"type": "string", "description": "ISO 8601 采集时间（北京时间）"},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "platform": {"type": "string"},
                        "platform_id": {"type": "string"},
                        "rank": {"type": "integer"},
                        "url": {"type": "string"},
                        "heat": {"type": "string"},
                        "platform_updated_at": {"type": "string", "description": "平台数据更新时间 ISO 8601"},
                        "source_type": {"type": "string", "enum": ["hotlist", "realtime"]},
                        "snippet": {"type": "string", "description": "摘要/正文片段（上游提供时才有，如知乎 hover）"},
                        "item_id": {"type": "string", "description": "平台侧条目 id"},
                        "published_at": {"type": "string", "description": "条目发布时间（原文或毫秒时间戳转 ISO）"},
                        "mobile_url": {"type": "string", "description": "移动端链接（若有）"}
                    }
                }
            },
            "errors": {"type": "array", "items": {"type": "string"}}
        }
    },
    "examples": {
        "cli_hotlist": "python scripts/collect_hotlist.py --platforms weibo,douyin -o output/hotlist.json",
        "cli_realtime": "python scripts/collect_hotlist.py --type realtime -o output/realtime.json",
        "cli_all": "python scripts/collect_hotlist.py --type all -o output/all.json",
        "cli_minimal": "python scripts/collect_hotlist.py --platforms weibo --pretty"
    },
    "errors": {
        "network_timeout": "API 请求超时 → 检查网络或使用 --proxy",
        "invalid_platform": "不支持的平台 ID → 用 --schema 查看支持列表",
        "api_error": "API 返回错误 → 该平台 API 可能暂时不可用，会记入 errors 数组继续处理其他平台"
    }
}


def _platforms_by_type(type_filter: str) -> list[str]:
    """Get platform IDs by type filter."""
    if type_filter == "all":
        return [pid for pid, info in PLATFORMS.items() if info["type"] in ("hotlist", "realtime")]
    return [pid for pid, info in PLATFORMS.items() if info["type"] == type_filter]


DEFAULT_HOTLIST_PLATFORMS = _platforms_by_type("hotlist")


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://newsnow.busiyi.world/",
}


def _ms_to_iso(ms_timestamp) -> str:
    """Convert millisecond Unix timestamp to ISO 8601 string (Beijing time)."""
    if not ms_timestamp:
        return ""
    try:
        from datetime import datetime, timezone, timedelta
        dt = datetime.fromtimestamp(int(ms_timestamp) / 1000, tz=timezone(timedelta(hours=8)))
        return dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    except Exception:
        return ""


def _extract_snippet(item: dict) -> str:
    """Long text from NewsNow item (platform-dependent: e.g. Zhihu extra.hover)."""
    extra = item.get("extra")
    if not isinstance(extra, dict):
        extra = {}
    for key in ("hover", "desc", "summary", "description", "content", "intro", "abstract"):
        v = extra.get(key) or item.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    info = extra.get("info")
    if isinstance(info, str) and len(info.strip()) > 30:
        return info.strip()
    return ""


def _extract_published_at(item: dict) -> str:
    """Item-level time from pubDate string or extra.date ms timestamp."""
    pd = item.get("pubDate") or item.get("pub_date") or item.get("date")
    if isinstance(pd, str) and pd.strip():
        return pd.strip()
    extra = item.get("extra")
    if isinstance(extra, dict) and extra.get("date") is not None:
        iso = _ms_to_iso(extra.get("date"))
        if iso:
            return iso
    return ""


def fetch_platform(platform_id: str, proxy_url: str = "", timeout: int = 15) -> list[dict]:
    """Fetch hotlist items for a single platform."""
    url = f"{NEWSNOW_API}?id={platform_id}&latest"
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

    resp = requests.get(url, timeout=timeout, proxies=proxies, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()

    platform_updated = _ms_to_iso(data.get("updatedTime"))
    source_type = PLATFORMS.get(platform_id, {}).get("type", "hotlist")

    items = data.get("items") or data.get("data") or []
    if isinstance(items, dict):
        items = items.get("items", [])

    results = []
    for i, item in enumerate(items):
        title = item.get("title", "").strip()
        if not title:
            continue
        extra = item.get("extra") or {}
        if not isinstance(extra, dict):
            extra = {}
        heat_val = extra.get("热度", extra.get("hot", ""))
        if not heat_val and isinstance(extra.get("info"), str):
            # 如「265 万热度」类短标签保留在 heat；长文 hover 已进 snippet
            info_s = extra.get("info", "").strip()
            if info_s and len(info_s) < 80:
                heat_val = info_s
        snippet = _extract_snippet(item)
        iid = item.get("id")
        item_id = str(iid).strip() if iid is not None and str(iid).strip() else ""
        pub = _extract_published_at(item)
        page_url = item.get("url") or ""
        mob = item.get("mobileUrl") or ""
        results.append({
            "title": title,
            "platform": platform_name(platform_id),
            "platform_id": platform_id,
            "rank": i + 1,
            "url": page_url or mob,
            "heat": str(heat_val) if heat_val else "",
            "platform_updated_at": platform_updated,
            "source_type": source_type,
            "snippet": snippet,
            "item_id": item_id,
            "published_at": pub,
            "mobile_url": mob if mob and mob != page_url else "",
        })

    return results


def main():
    parser = base_argparser("Fetch trending topics from NewsNow API (hotlist + realtime)")
    parser.add_argument(
        "--platforms", "-p",
        help="Comma-separated platform IDs (overrides --type filter)"
    )
    parser.add_argument(
        "--type", "-t", dest="source_type", default="hotlist",
        choices=["hotlist", "realtime", "all"],
        help="Filter platforms by type: hotlist=热门榜单, realtime=实时新闻, all=both (default: hotlist)"
    )
    parser.add_argument("--proxy", help="HTTP proxy URL")
    args = parser.parse_args()
    handle_schema(args, SCHEMA)

    input_data = read_json_input(args)

    if args.platforms:
        platforms = [p.strip() for p in args.platforms.split(",")]
    elif "platforms" in input_data:
        platforms = input_data["platforms"]
    else:
        type_filter = input_data.get("type", args.source_type)
        platforms = _platforms_by_type(type_filter)

    proxy_url = args.proxy or input_data.get("proxy_url", "")

    from datetime import datetime, timezone, timedelta
    collected_at = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%dT%H:%M:%S+08:00")

    all_items = []
    errors = []

    for platform_id in platforms:
        try:
            items = retry_request(
                lambda pid=platform_id: fetch_platform(pid, proxy_url),
                max_retries=3,
                backoff=1.0,
                on_fail=f"{platform_name(platform_id)} fetch failed after retries",
            )
            all_items.extend(items)
            print(f"[collect_hotlist] {platform_name(platform_id)}: {len(items)} items", file=sys.stderr)
        except Exception as e:
            msg = f"{platform_name(platform_id)}: {e}"
            errors.append(msg)
            print(f"[collect_hotlist] ERROR {msg}", file=sys.stderr)

        delay = random.uniform(0.3, 1.0)
        time.sleep(delay)

    result = {
        "source": "hotlist",
        "collected_at": collected_at,
        "items": all_items,
        "errors": errors
    }

    write_json_output(result, args)


if __name__ == "__main__":
    main()
