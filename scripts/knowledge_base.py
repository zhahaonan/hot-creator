#!/usr/bin/env python3
"""
knowledge_base — Cumulative knowledge store for hot-creator.
Persists topics across days, builds cross-day associations,
supports search/query, and exports graph data for visualization.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import json
import re
from pathlib import Path
from collections import defaultdict
from _common import (
    base_argparser, handle_schema, read_json_input,
    fail, today_str, OUTPUT_DIR, SKILL_ROOT
)

SCHEMA = {
    "name": "knowledge_base",
    "description": "Cumulative knowledge store: append daily trends, build cross-day associations, query history, export graph.",
    "input": {
        "type": "object",
        "properties": {
            "briefed_trends": {"type": "array", "description": "Output from content_brief (for --append)"},
            "query": {"type": "string", "description": "Search query (for --query)"},
        },
    },
    "output": {
        "type": "object",
        "properties": {
            "topics_added": {"type": "integer"},
            "topics_updated": {"type": "integer"},
            "total_topics": {"type": "integer"},
        },
    },
    "examples": {
        "cli_append": "python scripts/knowledge_base.py --append -i briefs.json",
        "cli_query": "python scripts/knowledge_base.py --query '考研'",
        "cli_stats": "python scripts/knowledge_base.py --stats",
        "cli_graph": "python scripts/knowledge_base.py --export-graph --days 7 -o graph.json",
    },
}

KB_PATH = OUTPUT_DIR / "knowledge_base.json"

THEME_KEYWORDS = {
    "社会公平": ["公平", "不公", "争议", "黑幕", "举报", "维权", "监管", "上限", "规则"],
    "年轻人焦虑": ["考研", "就业", "工资", "贷款", "负债", "内卷", "躺平", "进厂", "找工作", "PMI"],
    "信任危机": ["举报", "造谣", "泄露", "偷税", "诬告", "真相", "反转", "官方回应"],
    "技术变革": ["AI", "Claude", "源码", "编程", "开源", "泄露", "模型", "Anthropic", "Code"],
    "政策监管": ["监管", "新规", "利率", "上限", "PMI", "扩张", "政策", "制造业"],
    "情绪消费": ["吃瓜", "热搜", "粉丝", "举报", "营销号", "流量", "围观"],
    "创业/职场": ["PMI", "制造业", "就业", "工厂", "招工", "工资", "转型", "从业者"],
}


def load_kb() -> dict:
    """Load knowledge base from disk, or create empty structure."""
    if KB_PATH.exists():
        with open(KB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "version": "1.0",
        "last_updated": "",
        "topics": {},
        "themes": {},
        "daily_snapshots": {},
    }


def save_kb(kb: dict):
    """Persist knowledge base to disk."""
    KB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(KB_PATH, "w", encoding="utf-8") as f:
        json.dump(kb, f, ensure_ascii=False, indent=2)


def detect_themes(trend: dict) -> list[str]:
    """Detect thematic tags based on topic text content."""
    text = " ".join([
        trend.get("topic", ""),
        trend.get("summary", ""),
        trend.get("category", ""),
    ])
    brief = trend.get("brief", {})
    if isinstance(brief, dict) and "error" not in brief:
        for a in brief.get("angles", []):
            text += " " + a.get("name", "") + " " + a.get("description", "")

    found = []
    for theme, keywords in THEME_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            found.append(theme)
    return found


def extract_keywords(text: str) -> set[str]:
    """Extract meaningful Chinese/English keywords from text for fuzzy matching."""
    cn_words = set(re.findall(r'[\u4e00-\u9fff]{2,6}', text))
    en_words = set(w.lower() for w in re.findall(r'[A-Za-z]{3,}', text))
    stop = {"这个", "那个", "一个", "什么", "可以", "如何", "为什么", "因为", "所以",
            "但是", "而且", "或者", "已经", "正在", "没有", "不是", "就是", "the", "and", "for"}
    return (cn_words | en_words) - stop


def find_related_topics(topic_name: str, topic_data: dict, all_topics: dict) -> list[str]:
    """Find related topics via theme overlap + keyword similarity."""
    my_themes = set(topic_data.get("themes", []))
    my_keywords = extract_keywords(topic_name + " " + topic_data.get("summary", ""))
    related = []

    for other_name, other_data in all_topics.items():
        if other_name == topic_name:
            continue
        other_themes = set(other_data.get("themes", []))
        theme_overlap = len(my_themes & other_themes)

        other_kw = extract_keywords(other_name + " " + other_data.get("summary", ""))
        kw_overlap = len(my_keywords & other_kw)

        score = theme_overlap * 3 + kw_overlap
        if score >= 3:
            related.append((other_name, score))

    related.sort(key=lambda x: -x[1])
    return [r[0] for r in related[:10]]


def append_trends(kb: dict, trends: list[dict], date: str) -> dict:
    """Append today's trends to knowledge base. Returns stats."""
    added, updated = 0, 0

    for t in trends:
        topic = t.get("topic", "")
        if not topic:
            continue

        themes = detect_themes(t)
        score = t.get("score", 0)
        direction = t.get("direction", "")
        category = t.get("category", "")
        platforms = t.get("platforms", [])
        summary = t.get("summary", "")

        brief = t.get("brief", {})
        first_platform = ""
        if isinstance(brief, dict) and "error" not in brief:
            rec = brief.get("recommendation", {})
            first_platform = rec.get("first_platform", "")
            if not first_platform:
                prio = rec.get("platform_priority", [])
                first_platform = prio[0] if prio else ""

        appearance = {
            "date": date,
            "score": score,
            "direction": direction,
        }

        if topic in kb["topics"]:
            entry = kb["topics"][topic]
            existing_dates = {a["date"] for a in entry.get("appearances", [])}
            if date not in existing_dates:
                entry["appearances"].append(appearance)
            entry["last_seen"] = date
            entry["themes"] = list(set(entry.get("themes", []) + themes))
            entry["platforms"] = list(set(entry.get("platforms", []) + platforms))
            if score > entry.get("peak_score", 0):
                entry["peak_score"] = score
            updated += 1
        else:
            kb["topics"][topic] = {
                "first_seen": date,
                "last_seen": date,
                "appearances": [appearance],
                "category": category,
                "themes": themes,
                "platforms": platforms,
                "summary": summary,
                "first_platform": first_platform,
                "peak_score": score,
                "related_topics": [],
            }
            added += 1

        for theme in themes:
            if theme not in kb["themes"]:
                kb["themes"][theme] = {"topic_ids": [], "first_seen": date, "frequency": 0}
            th = kb["themes"][theme]
            if topic not in th["topic_ids"]:
                th["topic_ids"].append(topic)
            th["frequency"] += 1
            th["last_seen"] = date

    # Update cross-references after all topics are added
    for topic_name, topic_data in kb["topics"].items():
        topic_data["related_topics"] = find_related_topics(topic_name, topic_data, kb["topics"])

    # Daily snapshot
    hot = sum(1 for t in trends if t.get("score", 0) >= 70)
    emerging = sum(1 for t in trends if t.get("direction") == "emerging" or t.get("is_emerging"))
    kb["daily_snapshots"][date] = {
        "topic_count": len(trends),
        "hot": hot,
        "emerging": emerging,
        "topics": [t.get("topic", "") for t in trends],
    }

    kb["last_updated"] = date
    return {"topics_added": added, "topics_updated": updated, "total_topics": len(kb["topics"])}


def query_kb(kb: dict, query: str) -> list[dict]:
    """Search knowledge base by keyword."""
    results = []
    q = query.lower()
    for topic_name, data in kb["topics"].items():
        text = (topic_name + " " + data.get("summary", "") + " " +
                " ".join(data.get("themes", [])) + " " + data.get("category", ""))
        if q in text.lower():
            results.append({
                "topic": topic_name,
                "score": data.get("peak_score", 0),
                "category": data.get("category", ""),
                "first_seen": data.get("first_seen", ""),
                "last_seen": data.get("last_seen", ""),
                "appearances": len(data.get("appearances", [])),
                "themes": data.get("themes", []),
                "related": data.get("related_topics", [])[:5],
            })
    results.sort(key=lambda x: (-x["appearances"], -x["score"]))
    return results


def get_stats(kb: dict) -> dict:
    """Generate knowledge base statistics."""
    topics = kb.get("topics", {})
    themes = kb.get("themes", {})
    snapshots = kb.get("daily_snapshots", {})

    persistent = [
        {"topic": name, "days": len(d.get("appearances", [])), "peak": d.get("peak_score", 0)}
        for name, d in topics.items()
        if len(d.get("appearances", [])) >= 2
    ]
    persistent.sort(key=lambda x: (-x["days"], -x["peak"]))

    top_themes = sorted(themes.items(), key=lambda x: -x[1].get("frequency", 0))[:10]

    category_dist = defaultdict(int)
    for d in topics.values():
        category_dist[d.get("category", "其他")] += 1

    return {
        "total_topics": len(topics),
        "total_themes": len(themes),
        "total_days": len(snapshots),
        "persistent_topics": persistent[:10],
        "top_themes": [{"theme": t, "frequency": d["frequency"], "topics": len(d["topic_ids"])} for t, d in top_themes],
        "category_distribution": dict(category_dist),
        "date_range": {
            "from": min(snapshots.keys()) if snapshots else "",
            "to": max(snapshots.keys()) if snapshots else "",
        },
    }


def export_graph_data(kb: dict, days: int = 0) -> dict:
    """Export graph data for visualization. If days > 0, rolling window."""
    topics = kb.get("topics", {})
    snapshots = kb.get("daily_snapshots", {})

    if days > 0 and snapshots:
        sorted_dates = sorted(snapshots.keys(), reverse=True)
        cutoff_dates = set(sorted_dates[:days])
        filtered_topics = {}
        for name, data in topics.items():
            appearances = [a for a in data.get("appearances", []) if a["date"] in cutoff_dates]
            if appearances:
                filtered_topics[name] = {**data, "appearances": appearances}
        topics = filtered_topics

    nodes = []
    links = []
    node_ids = set()

    category_colors = {
        "教育": "#e74c3c", "娱乐": "#e67e22", "科技": "#3498db",
        "财经": "#2ecc71", "社会": "#9b59b6", "政治": "#1abc9c",
        "体育": "#f39c12", "健康": "#e91e63", "其他": "#95a5a6",
    }
    theme_colors = {
        "社会公平": "#ff6b6b", "年轻人焦虑": "#ffa502", "信任危机": "#ff4757",
        "技术变革": "#1e90ff", "政策监管": "#2ed573", "情绪消费": "#ff6348",
        "创业/职场": "#ffa502",
    }

    today = today_str()

    for name, data in topics.items():
        node_ids.add(name)
        appearances = data.get("appearances", [])
        latest = appearances[-1] if appearances else {}
        is_today = latest.get("date") == today
        peak_score = data.get("peak_score", 0)

        nodes.append({
            "id": name,
            "type": "topic",
            "category": data.get("category", "其他"),
            "color": category_colors.get(data.get("category", ""), "#95a5a6"),
            "score": peak_score,
            "radius": max(12, min(35, peak_score * 0.35)),
            "is_today": is_today,
            "is_persistent": len(appearances) >= 2,
            "days": len(appearances),
            "first_seen": data.get("first_seen", ""),
            "last_seen": data.get("last_seen", ""),
            "themes": data.get("themes", [])[:3],
            "summary": data.get("summary", ""),
            "platforms": data.get("platforms", []),
            "direction": latest.get("direction", ""),
        })

    # Theme nodes and topic→theme links
    themes_used = set()
    for name, data in topics.items():
        for theme in data.get("themes", []):
            themes_used.add(theme)
            links.append({"source": name, "target": theme, "type": "theme"})

    for theme in themes_used:
        if theme not in node_ids:
            node_ids.add(theme)
            nodes.append({
                "id": theme,
                "type": "theme",
                "color": theme_colors.get(theme, "#aaa"),
                "radius": 8,
            })

    # Cross-topic related links (from KB analysis, not just shared themes)
    seen_pairs = set()
    for name, data in topics.items():
        for related in data.get("related_topics", [])[:5]:
            if related in topics:
                pair = tuple(sorted([name, related]))
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    links.append({"source": name, "target": related, "type": "related"})

    return {
        "nodes": nodes,
        "links": links,
        "meta": {
            "total_topics": len(topics),
            "total_days": len(set(a["date"] for d in topics.values() for a in d.get("appearances", []))),
            "rolling_days": days if days > 0 else "all",
        },
    }


def main():
    parser = base_argparser("Knowledge base: cumulative storage, cross-day associations, query, graph export")
    parser.add_argument("--append", action="store_true", help="Append briefed_trends to knowledge base")
    parser.add_argument("--query", "-q", type=str, help="Search knowledge base by keyword")
    parser.add_argument("--stats", action="store_true", help="Print knowledge base statistics")
    parser.add_argument("--export-graph", action="store_true", help="Export graph data for visualization")
    parser.add_argument("--days", type=int, default=0, help="Rolling window in days (0 = all)")
    args = parser.parse_args()
    handle_schema(args, SCHEMA)

    kb = load_kb()

    if args.append:
        input_data = read_json_input(args)
        trends = input_data.get("briefed_trends", [])
        if not trends:
            fail("No briefed_trends for --append. Pipe output from content_brief.")
        date = today_str()
        stats = append_trends(kb, trends, date)
        save_kb(kb)
        print(f"[knowledge_base] +{stats['topics_added']} new, ~{stats['topics_updated']} updated, "
              f"total {stats['total_topics']}", file=sys.stderr)
        print(json.dumps(stats, ensure_ascii=False))

    elif args.query:
        results = query_kb(kb, args.query)
        print(f"[knowledge_base] Found {len(results)} results for '{args.query}'", file=sys.stderr)
        print(json.dumps({"query": args.query, "results": results}, ensure_ascii=False, indent=2))

    elif args.stats:
        stats = get_stats(kb)
        print(json.dumps(stats, ensure_ascii=False, indent=2))

    elif args.export_graph:
        graph = export_graph_data(kb, days=args.days)
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(graph, f, ensure_ascii=False, indent=2)
            print(f"[knowledge_base] Graph exported to {args.output}", file=sys.stderr)
        else:
            print(json.dumps(graph, ensure_ascii=False, indent=2))

    else:
        stats = get_stats(kb)
        print(json.dumps({"status": "ok", **stats}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
