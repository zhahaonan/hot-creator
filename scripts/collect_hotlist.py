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
    fail, NEWSNOW_API, PLATFORMS, platform_name
)

SCHEMA = {
    "name": "collect_hotlist",
    "description": "Fetch trending topics from public hotlist APIs for multiple platforms",
    "input": {
        "type": "object",
        "properties": {
            "platforms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Platform IDs to fetch. Defaults to all hotlist-type platforms.",
                "examples": [["weibo", "douyin", "zhihu"], ["baidu", "toutiao"]]
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
                        "heat": {"type": "string"}
                    }
                }
            },
            "errors": {"type": "array", "items": {"type": "string"}}
        }
    },
    "examples": {
        "cli": "python scripts/collect_hotlist.py --platforms weibo,douyin -o output/hotlist.json",
        "minimal": "python scripts/collect_hotlist.py --platforms weibo --pretty"
    },
    "errors": {
        "network_timeout": "API 请求超时 → 检查网络或使用 --proxy",
        "invalid_platform": "不支持的平台 ID → 用 --schema 查看支持列表",
        "api_error": "API 返回错误 → 该平台 API 可能暂时不可用，会记入 errors 数组继续处理其他平台"
    }
}

DEFAULT_HOTLIST_PLATFORMS = [
    pid for pid, info in PLATFORMS.items() if info["type"] == "hotlist"
]


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://newsnow.busiyi.world/",
}


def fetch_platform(platform_id: str, proxy_url: str = "", timeout: int = 15) -> list[dict]:
    """Fetch hotlist items for a single platform."""
    url = f"{NEWSNOW_API}?id={platform_id}&latest"
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

    resp = requests.get(url, timeout=timeout, proxies=proxies, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()

    items = data.get("items") or data.get("data") or []
    if isinstance(items, dict):
        items = items.get("items", [])

    results = []
    for i, item in enumerate(items):
        title = item.get("title", "").strip()
        if not title:
            continue
        results.append({
            "title": title,
            "platform": platform_name(platform_id),
            "platform_id": platform_id,
            "rank": i + 1,
            "url": item.get("url", item.get("mobileUrl", "")),
            "heat": str(item.get("extra", {}).get("热度", item.get("extra", {}).get("hot", "")))
        })

    return results


def main():
    parser = base_argparser("Fetch trending topics from public hotlist APIs")
    parser.add_argument(
        "--platforms", "-p",
        help="Comma-separated platform IDs (default: all hotlist platforms)"
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
        platforms = DEFAULT_HOTLIST_PLATFORMS

    proxy_url = args.proxy or input_data.get("proxy_url", "")

    all_items = []
    errors = []

    for platform_id in platforms:
        try:
            items = fetch_platform(platform_id, proxy_url)
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
        "items": all_items,
        "errors": errors
    }

    write_json_output(result, args)


if __name__ == "__main__":
    main()
