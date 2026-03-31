#!/usr/bin/env python3
"""
collect_social — Fetch real-time social media trends via built-in CDP browser engine.
Targets: Xiaohongshu, Douyin, Weibo rising trends, etc.
Uses the internal CDP Proxy (scripts/cdp/proxy.mjs) to control Chrome.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import json
import subprocess
import time
import requests
from pathlib import Path
from _common import (
    base_argparser, handle_schema, read_json_input, write_json_output,
    fail, CDP_PROXY_BASE, CDP_PROXY_PORT, SKILL_ROOT, platform_name
)

SCHEMA = {
    "name": "collect_social",
    "description": "Fetch real-time social media trends via CDP browser automation. Requires Chrome + Node.js CDP proxy.",
    "input": {
        "type": "object",
        "properties": {
            "targets": {
                "type": "array",
                "items": {"type": "string", "enum": ["xiaohongshu", "douyin", "weibo_rising"]},
                "description": "Social platforms to scrape",
                "default": ["xiaohongshu", "douyin", "weibo_rising"]
            }
        }
    },
    "output": {
        "type": "object",
        "properties": {
            "source": {"type": "string", "const": "social"},
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
    "prerequisites": ["CDP Proxy running (node scripts/cdp/check.mjs)", "Chrome remote debugging enabled"],
    "examples": {
        "cli": "python scripts/collect_social.py --targets xiaohongshu,weibo_rising -o output/social.json"
    },
    "errors": {
        "cdp_not_available": "CDP Proxy 未启动 → node scripts/cdp/check.mjs",
        "chrome_not_configured": "Chrome 未开启远程调试 → chrome://inspect/#remote-debugging",
        "dom_extraction_failed": "页面 DOM 结构可能已变 → 检查 site-patterns/ 是否需要更新",
        "anti_scraping": "平台反爬触发 → 增加请求间隔或稍后重试"
    }
}


def ensure_cdp_proxy() -> bool:
    """Check if CDP proxy is running, start if not."""
    try:
        resp = requests.get(f"{CDP_PROXY_BASE}/health", timeout=3)
        data = resp.json()
        if data.get("status") == "ok":
            return True
    except Exception:
        pass

    check_script = SKILL_ROOT / "scripts" / "cdp" / "check.mjs"
    if not check_script.exists():
        return False

    try:
        result = subprocess.run(
            ["node", str(check_script)],
            capture_output=True, text=True, timeout=30
        )
        return "proxy: ready" in result.stdout
    except Exception as e:
        print(f"[collect_social] CDP check failed: {e}", file=sys.stderr)
        return False


def cdp_new_tab(url: str) -> str | None:
    """Open a new background tab and return targetId."""
    try:
        resp = requests.get(f"{CDP_PROXY_BASE}/new", params={"url": url}, timeout=20)
        data = resp.json()
        return data.get("targetId")
    except Exception as e:
        print(f"[collect_social] Failed to open tab: {e}", file=sys.stderr)
        return None


def cdp_eval(target_id: str, js_code: str) -> dict | None:
    """Execute JS in a tab and return result."""
    try:
        resp = requests.post(
            f"{CDP_PROXY_BASE}/eval",
            params={"target": target_id},
            data=js_code.encode("utf-8"),
            timeout=15
        )
        return resp.json()
    except Exception as e:
        print(f"[collect_social] Eval failed: {e}", file=sys.stderr)
        return None


def cdp_scroll(target_id: str, direction: str = "bottom"):
    """Scroll a tab."""
    try:
        requests.get(
            f"{CDP_PROXY_BASE}/scroll",
            params={"target": target_id, "direction": direction},
            timeout=10
        )
    except Exception:
        pass


def cdp_close(target_id: str):
    """Close a tab."""
    try:
        requests.get(f"{CDP_PROXY_BASE}/close", params={"target": target_id}, timeout=5)
    except Exception:
        pass


def scrape_weibo_rising() -> list[dict]:
    """Scrape Weibo hot search / rising trends."""
    target_id = cdp_new_tab("https://s.weibo.com/top/summary")
    if not target_id:
        raise RuntimeError("Failed to open Weibo page")

    try:
        time.sleep(2)
        result = cdp_eval(target_id, """
            JSON.stringify(
                [...document.querySelectorAll('#pl_top_realtimehot table tbody tr')]
                    .slice(1)
                    .map((tr, i) => ({
                        rank: i + 1,
                        title: tr.querySelector('.td-02 a')?.textContent?.trim() || '',
                        heat: tr.querySelector('.td-02 span')?.textContent?.trim() || '',
                        url: tr.querySelector('.td-02 a')?.href || '',
                        tag: tr.querySelector('.td-03 i')?.textContent?.trim() || '',
                    }))
                    .filter(item => item.title)
            )
        """)

        if not result or "value" not in result:
            raise RuntimeError("Failed to extract Weibo data from DOM")

        raw = json.loads(result["value"]) if isinstance(result["value"], str) else result["value"]
        items = []
        for entry in raw:
            items.append({
                "title": entry["title"],
                "platform": "微博上升",
                "platform_id": "weibo_rising",
                "rank": entry["rank"],
                "url": entry.get("url", ""),
                "heat": entry.get("heat", "")
            })
        return items
    finally:
        cdp_close(target_id)


def scrape_xiaohongshu() -> list[dict]:
    """Scrape Xiaohongshu trending topics."""
    target_id = cdp_new_tab("https://www.xiaohongshu.com/explore")
    if not target_id:
        raise RuntimeError("Failed to open Xiaohongshu page")

    try:
        time.sleep(3)
        cdp_scroll(target_id, "bottom")
        time.sleep(1)

        result = cdp_eval(target_id, """
            JSON.stringify((() => {
                const items = [];
                // Try multiple possible selectors for trending/hot content
                const selectors = [
                    '.hot-item', '.trending-item', '[class*="hot-list"]',
                    '[class*="trending"]', '.channel-item', '.search-hot-item'
                ];
                for (const sel of selectors) {
                    const els = document.querySelectorAll(sel);
                    if (els.length > 0) {
                        els.forEach((el, i) => {
                            const title = el.textContent?.trim();
                            if (title && title.length < 200) {
                                items.push({
                                    rank: i + 1,
                                    title: title.split('\\n')[0].trim(),
                                    url: el.querySelector('a')?.href || ''
                                });
                            }
                        });
                        break;
                    }
                }
                // Fallback: extract visible note titles from explore page
                if (items.length === 0) {
                    document.querySelectorAll('[class*="note-item"], .feeds-page .note-item, section').forEach((el, i) => {
                        const titleEl = el.querySelector('[class*="title"], h3, a');
                        const title = titleEl?.textContent?.trim();
                        if (title && title.length > 2 && title.length < 200) {
                            items.push({
                                rank: i + 1,
                                title: title,
                                url: titleEl?.closest('a')?.href || el.querySelector('a')?.href || ''
                            });
                        }
                    });
                }
                return items.slice(0, 30);
            })())
        """)

        if not result or "value" not in result:
            raise RuntimeError("Failed to extract Xiaohongshu data from DOM")

        raw = json.loads(result["value"]) if isinstance(result["value"], str) else result["value"]
        items = []
        for entry in raw:
            items.append({
                "title": entry["title"],
                "platform": "小红书",
                "platform_id": "xiaohongshu",
                "rank": entry["rank"],
                "url": entry.get("url", ""),
                "heat": ""
            })
        return items
    finally:
        cdp_close(target_id)


def scrape_douyin() -> list[dict]:
    """Scrape Douyin trending from Juliangsuantu or Douyin hot page."""
    target_id = cdp_new_tab("https://www.douyin.com/hot")
    if not target_id:
        raise RuntimeError("Failed to open Douyin page")

    try:
        time.sleep(3)

        result = cdp_eval(target_id, """
            JSON.stringify((() => {
                const items = [];
                const selectors = [
                    '[class*="hot-list"] [class*="item"]',
                    '[class*="rank-item"]',
                    '.hot-item',
                    '[class*="HotBoardList"] li',
                ];
                for (const sel of selectors) {
                    const els = document.querySelectorAll(sel);
                    if (els.length > 0) {
                        els.forEach((el, i) => {
                            const title = el.querySelector('[class*="title"], [class*="text"], span, a')?.textContent?.trim();
                            const heat = el.querySelector('[class*="heat"], [class*="count"], [class*="hot"]')?.textContent?.trim();
                            if (title && title.length > 2) {
                                items.push({
                                    rank: i + 1,
                                    title: title,
                                    heat: heat || '',
                                    url: el.querySelector('a')?.href || ''
                                });
                            }
                        });
                        break;
                    }
                }
                return items.slice(0, 50);
            })())
        """)

        if not result or "value" not in result:
            raise RuntimeError("Failed to extract Douyin data from DOM")

        raw = json.loads(result["value"]) if isinstance(result["value"], str) else result["value"]
        items = []
        for entry in raw:
            items.append({
                "title": entry["title"],
                "platform": "抖音",
                "platform_id": "douyin",
                "rank": entry["rank"],
                "url": entry.get("url", ""),
                "heat": entry.get("heat", "")
            })
        return items
    finally:
        cdp_close(target_id)


SCRAPERS = {
    "xiaohongshu": scrape_xiaohongshu,
    "douyin": scrape_douyin,
    "weibo_rising": scrape_weibo_rising,
}


def main():
    parser = base_argparser("Fetch social media trends via CDP browser")
    parser.add_argument(
        "--targets", "-t",
        help="Comma-separated target IDs (default: xiaohongshu,douyin,weibo_rising)"
    )
    args = parser.parse_args()
    handle_schema(args, SCHEMA)

    input_data = read_json_input(args)

    if args.targets:
        targets = [t.strip() for t in args.targets.split(",")]
    elif "targets" in input_data:
        targets = input_data["targets"]
    else:
        targets = list(SCRAPERS.keys())

    if not ensure_cdp_proxy():
        fail(
            "CDP Proxy not available. Ensure Chrome remote debugging is enabled "
            "(chrome://inspect/#remote-debugging) and Node.js 22+ is installed."
        )

    all_items = []
    errors = []

    for target in targets:
        scraper = SCRAPERS.get(target)
        if not scraper:
            errors.append(f"Unknown target: {target}")
            continue

        try:
            items = scraper()
            all_items.extend(items)
            print(f"[collect_social] {platform_name(target)}: {len(items)} items", file=sys.stderr)
        except Exception as e:
            msg = f"{platform_name(target)}: {e}"
            errors.append(msg)
            print(f"[collect_social] ERROR {msg}", file=sys.stderr)

        time.sleep(1)

    result = {
        "source": "social",
        "items": all_items,
        "errors": errors
    }

    write_json_output(result, args)


if __name__ == "__main__":
    main()
