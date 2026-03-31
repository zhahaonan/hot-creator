#!/usr/bin/env python3
"""
monitor_competitor — Monitor competitor content on social media via CDP browser.
Scrapes competitor accounts on Xiaohongshu, WeChat Official Accounts, Douyin, etc.
Extracts recent posts, engagement signals, and content themes.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import json
import time
import requests
from pathlib import Path
from _common import (
    base_argparser, handle_schema, read_json_input, write_json_output,
    fail, CDP_PROXY_BASE, SKILL_ROOT
)

SCHEMA = {
    "name": "monitor_competitor",
    "description": "Monitor competitor content on social platforms via CDP browser. Requires CDP proxy.",
    "input": {
        "type": "object",
        "properties": {
            "competitors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Competitor name"},
                        "platform": {
                            "type": "string",
                            "enum": ["xiaohongshu", "wechat_mp", "douyin", "weibo"],
                            "description": "Platform to monitor"
                        },
                        "account_url": {
                            "type": "string",
                            "description": "Direct URL to competitor's profile (optional, improves accuracy)"
                        },
                        "search_keyword": {
                            "type": "string",
                            "description": "Keyword to search (defaults to competitor name)"
                        }
                    },
                    "required": ["name", "platform"]
                },
                "description": "List of competitors to monitor"
            },
            "max_posts": {
                "type": "integer",
                "default": 10,
                "description": "Max recent posts to extract per competitor"
            }
        },
        "required": ["competitors"]
    },
    "output": {
        "type": "object",
        "properties": {
            "competitor_data": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "platform": {"type": "string"},
                        "posts": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "content_preview": {"type": "string"},
                                    "url": {"type": "string"},
                                    "engagement": {"type": "string"},
                                    "date": {"type": "string"}
                                }
                            }
                        },
                        "themes": {"type": "array", "items": {"type": "string"}},
                        "content_frequency": {"type": "string"}
                    }
                }
            },
            "errors": {"type": "array", "items": {"type": "string"}}
        }
    },
    "prerequisites": ["CDP Proxy running", "Chrome remote debugging enabled"],
    "examples": {
        "cli": "echo '{\"competitors\":[{\"name\":\"竞品A\",\"platform\":\"xiaohongshu\"}]}' | python scripts/monitor_competitor.py -o comp.json"
    },
    "errors": {
        "cdp_not_available": "CDP Proxy 未启动",
        "unsupported_platform": "平台不支持 → 目前支持 xiaohongshu/wechat_mp/douyin/weibo",
        "scrape_failed": "页面抓取失败 → 可能触发反爬，增加间隔重试"
    }
}


def ensure_cdp() -> bool:
    try:
        resp = requests.get(f"{CDP_PROXY_BASE}/health", timeout=3)
        return resp.json().get("status") == "ok"
    except Exception:
        pass

    import subprocess
    check_script = SKILL_ROOT / "scripts" / "cdp" / "check.mjs"
    if not check_script.exists():
        return False
    try:
        result = subprocess.run(
            ["node", str(check_script)],
            capture_output=True, text=True, timeout=30
        )
        return "proxy: ready" in result.stdout
    except Exception:
        return False


def cdp_new_tab(url: str) -> str | None:
    try:
        resp = requests.get(f"{CDP_PROXY_BASE}/new", params={"url": url}, timeout=20)
        return resp.json().get("targetId")
    except Exception:
        return None


def cdp_eval(target_id: str, js_code: str) -> dict | None:
    try:
        resp = requests.post(
            f"{CDP_PROXY_BASE}/eval",
            params={"target": target_id},
            data=js_code.encode("utf-8"),
            timeout=15
        )
        return resp.json()
    except Exception:
        return None


def cdp_scroll(target_id: str, direction: str = "bottom"):
    try:
        requests.get(
            f"{CDP_PROXY_BASE}/scroll",
            params={"target": target_id, "direction": direction},
            timeout=10
        )
    except Exception:
        pass


def cdp_close(target_id: str):
    try:
        requests.get(f"{CDP_PROXY_BASE}/close", params={"target": target_id}, timeout=5)
    except Exception:
        pass


def monitor_xiaohongshu(competitor: dict, max_posts: int) -> dict:
    """Monitor a competitor on Xiaohongshu."""
    name = competitor["name"]
    url = competitor.get("account_url", "")
    keyword = competitor.get("search_keyword", name)

    if not url:
        url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&type=1"

    target_id = cdp_new_tab(url)
    if not target_id:
        raise RuntimeError(f"Failed to open page for {name}")

    try:
        time.sleep(3)
        cdp_scroll(target_id, "bottom")
        time.sleep(1)

        result = cdp_eval(target_id, f"""
            JSON.stringify((() => {{
                const posts = [];
                const noteItems = document.querySelectorAll('[class*="note-item"], [class*="feeds-page"] section, [class*="search-result"] [class*="note"]');
                noteItems.forEach((el, i) => {{
                    if (i >= {max_posts}) return;
                    const titleEl = el.querySelector('[class*="title"], h3, [class*="desc"]');
                    const linkEl = el.querySelector('a[href*="/explore/"], a[href*="/discovery/item/"]');
                    const likeEl = el.querySelector('[class*="like"], [class*="count"]');
                    posts.push({{
                        title: titleEl?.textContent?.trim() || '',
                        url: linkEl?.href || el.querySelector('a')?.href || '',
                        engagement: likeEl?.textContent?.trim() || '',
                    }});
                }});
                return posts.filter(p => p.title);
            }})())
        """)

        posts = []
        if result and "value" in result:
            raw = json.loads(result["value"]) if isinstance(result["value"], str) else result["value"]
            for p in raw:
                posts.append({
                    "title": p.get("title", ""),
                    "content_preview": "",
                    "url": p.get("url", ""),
                    "engagement": p.get("engagement", ""),
                    "date": ""
                })

        return {
            "name": name,
            "platform": "小红书",
            "posts": posts,
            "themes": [],
            "content_frequency": ""
        }
    finally:
        cdp_close(target_id)


def monitor_wechat_mp(competitor: dict, max_posts: int) -> dict:
    """Monitor a competitor's WeChat Official Account via Sogou search."""
    name = competitor["name"]
    keyword = competitor.get("search_keyword", name)
    url = f"https://weixin.sogou.com/weixin?type=1&s_from=input&query={keyword}"

    target_id = cdp_new_tab(url)
    if not target_id:
        raise RuntimeError(f"Failed to open Sogou for {name}")

    try:
        time.sleep(3)

        result = cdp_eval(target_id, f"""
            JSON.stringify((() => {{
                const items = [];
                // Sogou WeChat search results
                const results = document.querySelectorAll('.news-list li, .news-box li, [class*="result"] li');
                results.forEach((el, i) => {{
                    if (i >= {max_posts}) return;
                    const titleEl = el.querySelector('h3 a, .txt-box h3 a, [class*="title"] a');
                    const descEl = el.querySelector('.txt-info, p, [class*="desc"]');
                    const timeEl = el.querySelector('.s2, [class*="time"], [class*="date"]');
                    if (titleEl) {{
                        items.push({{
                            title: titleEl.textContent?.trim() || '',
                            url: titleEl.href || '',
                            content_preview: descEl?.textContent?.trim()?.substring(0, 200) || '',
                            date: timeEl?.textContent?.trim() || '',
                        }});
                    }}
                }});
                // Also try account page articles if we landed on one
                document.querySelectorAll('.weui_media_box, [class*="article"]').forEach((el, i) => {{
                    if (i >= {max_posts}) return;
                    const titleEl = el.querySelector('h4, [class*="title"]');
                    const descEl = el.querySelector('p, [class*="desc"]');
                    if (titleEl && !items.find(x => x.title === titleEl.textContent?.trim())) {{
                        items.push({{
                            title: titleEl.textContent?.trim() || '',
                            url: el.querySelector('a')?.href || '',
                            content_preview: descEl?.textContent?.trim()?.substring(0, 200) || '',
                            date: '',
                        }});
                    }}
                }});
                return items;
            }})())
        """)

        posts = []
        if result and "value" in result:
            raw = json.loads(result["value"]) if isinstance(result["value"], str) else result["value"]
            for p in raw:
                posts.append({
                    "title": p.get("title", ""),
                    "content_preview": p.get("content_preview", ""),
                    "url": p.get("url", ""),
                    "engagement": "",
                    "date": p.get("date", "")
                })

        return {
            "name": name,
            "platform": "微信公众号",
            "posts": posts,
            "themes": [],
            "content_frequency": ""
        }
    finally:
        cdp_close(target_id)


def monitor_douyin(competitor: dict, max_posts: int) -> dict:
    """Monitor a competitor on Douyin."""
    name = competitor["name"]
    url = competitor.get("account_url", "")
    keyword = competitor.get("search_keyword", name)

    if not url:
        url = f"https://www.douyin.com/search/{keyword}?type=user"

    target_id = cdp_new_tab(url)
    if not target_id:
        raise RuntimeError(f"Failed to open Douyin for {name}")

    try:
        time.sleep(3)

        result = cdp_eval(target_id, f"""
            JSON.stringify((() => {{
                const items = [];
                document.querySelectorAll('[class*="video-card"], [class*="search-result-card"]').forEach((el, i) => {{
                    if (i >= {max_posts}) return;
                    const titleEl = el.querySelector('[class*="title"], [class*="desc"], span');
                    const likeEl = el.querySelector('[class*="like"], [class*="count"]');
                    items.push({{
                        title: titleEl?.textContent?.trim() || '',
                        url: el.querySelector('a')?.href || '',
                        engagement: likeEl?.textContent?.trim() || '',
                    }});
                }});
                return items.filter(p => p.title);
            }})())
        """)

        posts = []
        if result and "value" in result:
            raw = json.loads(result["value"]) if isinstance(result["value"], str) else result["value"]
            for p in raw:
                posts.append({
                    "title": p.get("title", ""),
                    "content_preview": "",
                    "url": p.get("url", ""),
                    "engagement": p.get("engagement", ""),
                    "date": ""
                })

        return {
            "name": name,
            "platform": "抖音",
            "posts": posts,
            "themes": [],
            "content_frequency": ""
        }
    finally:
        cdp_close(target_id)


def monitor_weibo(competitor: dict, max_posts: int) -> dict:
    """Monitor a competitor on Weibo."""
    name = competitor["name"]
    keyword = competitor.get("search_keyword", name)
    url = f"https://s.weibo.com/weibo?q={keyword}&typeall=1&suball=1"

    target_id = cdp_new_tab(url)
    if not target_id:
        raise RuntimeError(f"Failed to open Weibo for {name}")

    try:
        time.sleep(3)

        result = cdp_eval(target_id, f"""
            JSON.stringify((() => {{
                const items = [];
                document.querySelectorAll('[action-type="feed_list_item"], .card-wrap').forEach((el, i) => {{
                    if (i >= {max_posts}) return;
                    const textEl = el.querySelector('[class*="txt"], p[node-type="feed_list_content"]');
                    const likeEl = el.querySelector('[action-type="fl_like"] em, [class*="like"] span');
                    const timeEl = el.querySelector('.from a, [class*="time"]');
                    items.push({{
                        title: textEl?.textContent?.trim()?.substring(0, 100) || '',
                        url: timeEl?.href || '',
                        engagement: likeEl?.textContent?.trim() || '',
                        date: timeEl?.textContent?.trim() || '',
                    }});
                }});
                return items.filter(p => p.title);
            }})())
        """)

        posts = []
        if result and "value" in result:
            raw = json.loads(result["value"]) if isinstance(result["value"], str) else result["value"]
            for p in raw:
                posts.append({
                    "title": p.get("title", ""),
                    "content_preview": "",
                    "url": p.get("url", ""),
                    "engagement": p.get("engagement", ""),
                    "date": p.get("date", "")
                })

        return {
            "name": name,
            "platform": "微博",
            "posts": posts,
            "themes": [],
            "content_frequency": ""
        }
    finally:
        cdp_close(target_id)


PLATFORM_SCRAPERS = {
    "xiaohongshu": monitor_xiaohongshu,
    "wechat_mp": monitor_wechat_mp,
    "douyin": monitor_douyin,
    "weibo": monitor_weibo,
}


def main():
    parser = base_argparser("Monitor competitor content on social platforms")
    parser.add_argument("--max-posts", type=int, default=10, help="Max posts per competitor")
    args = parser.parse_args()
    handle_schema(args, SCHEMA)

    input_data = read_json_input(args)
    competitors = input_data.get("competitors", [])
    max_posts = args.max_posts or input_data.get("max_posts", 10)

    if not competitors:
        fail("No competitors provided. Provide JSON with 'competitors' array.")

    if not ensure_cdp():
        fail(
            "CDP Proxy not available. Ensure Chrome remote debugging is enabled "
            "and Node.js 22+ is installed."
        )

    all_data = []
    errors = []

    for comp in competitors:
        name = comp.get("name", "Unknown")
        platform = comp.get("platform", "")
        scraper = PLATFORM_SCRAPERS.get(platform)

        if not scraper:
            errors.append(f"Unsupported platform '{platform}' for {name}")
            continue

        try:
            data = scraper(comp, max_posts)
            all_data.append(data)
            post_count = len(data.get("posts", []))
            print(f"[monitor_competitor] {name} ({platform}): {post_count} posts", file=sys.stderr)
        except Exception as e:
            msg = f"{name} ({platform}): {e}"
            errors.append(msg)
            print(f"[monitor_competitor] ERROR {msg}", file=sys.stderr)

        time.sleep(2)

    result = {
        "competitor_data": all_data,
        "errors": errors
    }

    write_json_output(result, args)


if __name__ == "__main__":
    main()
