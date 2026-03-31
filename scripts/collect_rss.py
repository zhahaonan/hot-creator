#!/usr/bin/env python3
"""
collect_rss — Fetch articles from RSS feeds.
Supports multiple feeds with configurable freshness filtering.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import time
import random
from datetime import datetime, timezone, timedelta
from _common import (
    base_argparser, handle_schema, read_json_input, write_json_output, fail
)

try:
    import feedparser
except ImportError:
    fail("feedparser not installed. Run: pip install feedparser")

SCHEMA = {
    "name": "collect_rss",
    "description": "Fetch articles from RSS feeds with freshness filtering",
    "input": {
        "type": "object",
        "properties": {
            "feeds": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "url": {"type": "string"},
                        "max_items": {"type": "integer", "default": 20},
                        "max_age_days": {"type": "integer", "default": 3}
                    },
                    "required": ["id", "name", "url"]
                },
                "description": "List of RSS feed configs. If omitted, uses built-in defaults (36kr, HN, sspai)."
            }
        }
    },
    "output": {
        "type": "object",
        "properties": {
            "source": {"type": "string", "const": "rss"},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "platform": {"type": "string"},
                        "platform_id": {"type": "string"},
                        "url": {"type": "string"},
                        "published_at": {"type": "string"},
                        "summary": {"type": "string"}
                    }
                }
            },
            "errors": {"type": "array", "items": {"type": "string"}}
        }
    },
    "examples": {
        "cli_default": "python scripts/collect_rss.py -o output/rss.json",
        "cli_custom": "python scripts/collect_rss.py --feeds-json my-feeds.json -o rss.json"
    },
    "errors": {
        "feed_parse_error": "RSS 解析失败 → 检查 feed URL 是否有效",
        "network_error": "网络请求失败 → 记入 errors 数组继续处理其他 feed"
    }
}

DEFAULT_FEEDS = [
    {"id": "36kr",     "name": "36氪",         "url": "https://36kr.com/feed"},
    {"id": "hn",       "name": "Hacker News",   "url": "https://hnrss.org/frontpage"},
    {"id": "sspai",    "name": "少数派",        "url": "https://sspai.com/feed"},
]


def parse_pub_date(entry) -> str:
    """Extract publication date as ISO string."""
    for field in ("published_parsed", "updated_parsed"):
        t = getattr(entry, field, None) or entry.get(field)
        if t:
            try:
                dt = datetime(*t[:6], tzinfo=timezone.utc)
                return dt.isoformat()
            except Exception:
                continue
    for field in ("published", "updated"):
        val = getattr(entry, field, None) or entry.get(field)
        if val:
            return str(val)
    return ""


def is_fresh(pub_str: str, max_age_days: int) -> bool:
    """Check if article is within max_age_days."""
    if max_age_days <= 0 or not pub_str:
        return True
    try:
        pub_dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        return pub_dt >= cutoff
    except Exception:
        return True


def fetch_feed(feed_config: dict) -> list[dict]:
    """Fetch and parse a single RSS feed."""
    url = feed_config["url"]
    name = feed_config["name"]
    feed_id = feed_config["id"]
    max_items = feed_config.get("max_items", 20)
    max_age_days = feed_config.get("max_age_days", 3)

    parsed = feedparser.parse(url)

    if parsed.bozo and not parsed.entries:
        raise RuntimeError(f"Failed to parse feed: {parsed.bozo_exception}")

    items = []
    for entry in parsed.entries:
        if max_items > 0 and len(items) >= max_items:
            break

        title = (entry.get("title") or "").strip()
        if not title:
            continue

        pub_date = parse_pub_date(entry)
        if not is_fresh(pub_date, max_age_days):
            continue

        summary = (entry.get("summary") or entry.get("description") or "").strip()
        if len(summary) > 300:
            summary = summary[:300] + "..."

        items.append({
            "title": title,
            "platform": name,
            "platform_id": feed_id,
            "url": entry.get("link", ""),
            "published_at": pub_date,
            "summary": summary
        })

    return items


def main():
    parser = base_argparser("Fetch articles from RSS feeds")
    parser.add_argument("--feeds-json", help="JSON file with feeds config")
    args = parser.parse_args()
    handle_schema(args, SCHEMA)

    input_data = read_json_input(args)

    if args.feeds_json:
        import json
        with open(args.feeds_json, "r", encoding="utf-8") as f:
            feeds = json.load(f)
        if isinstance(feeds, dict):
            feeds = feeds.get("feeds", [])
    elif "feeds" in input_data:
        feeds = input_data["feeds"]
    else:
        feeds = DEFAULT_FEEDS

    all_items = []
    errors = []

    for feed_config in feeds:
        try:
            items = fetch_feed(feed_config)
            all_items.extend(items)
            print(
                f'[collect_rss] {feed_config["name"]}: {len(items)} items',
                file=sys.stderr
            )
        except Exception as e:
            msg = f'{feed_config["name"]}: {e}'
            errors.append(msg)
            print(f"[collect_rss] ERROR {msg}", file=sys.stderr)

        delay = random.uniform(0.5, 1.5)
        time.sleep(delay)

    result = {
        "source": "rss",
        "items": all_items,
        "errors": errors
    }

    write_json_output(result, args)


if __name__ == "__main__":
    main()
