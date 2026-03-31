#!/usr/bin/env python3
"""
export_obsidian — Generate Obsidian vault notes from content brief data.
Creates a Dashboard + individual Topic notes with YAML frontmatter and wiki links.
Enhanced with: auto bi-directional linking, cross-day historical references,
and weekly digest generation.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from _common import (
    base_argparser, handle_schema, read_json_input, write_json_output,
    fail, today_str, OUTPUT_DIR
)

SCHEMA = {
    "name": "export_obsidian",
    "description": "Generate Obsidian vault: Dashboard + Topics (by category) + Copywriting (by platform) + weekly digest.",
    "input": {
        "type": "object",
        "properties": {
            "briefed_trends": {"type": "array", "description": "Output from content_brief"}
        },
        "required": ["briefed_trends"]
    },
    "output": {
        "type": "object",
        "properties": {
            "dashboard": {"type": "string", "description": "Path to Dashboard .md file"},
            "topics": {"type": "array", "items": {"type": "string"}, "description": "Paths to topic notes (Topics/{category}/*.md)"},
            "copywriting": {"type": "array", "items": {"type": "string"}, "description": "Paths to platform drafts (Copywriting/{platform}/*.md)"},
            "weekly_digest": {"type": "string", "description": "Path to weekly digest (if generated)"}
        }
    },
    "examples": {
        "cli": "python scripts/export_obsidian.py -i briefs.json --vault ~/ObsidianVault",
        "cli_no_copy": "python scripts/export_obsidian.py -i briefs.json --vault . --no-copywriting"
    },
    "errors": {
        "no_data": "无 briefed_trends → 先运行 content_brief",
        "vault_not_found": "--vault 路径不存在 → 检查 Obsidian vault 路径"
    }
}


def safe_filename(name: str) -> str:
    """Sanitize string for use as filename."""
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = name.strip().replace('\n', ' ')
    return name[:80] if len(name) > 80 else name


def load_knowledge_base() -> dict:
    """Load knowledge base for cross-day references."""
    kb_path = OUTPUT_DIR / "knowledge_base.json"
    if kb_path.exists():
        with open(kb_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"topics": {}, "themes": {}, "daily_snapshots": {}}


def build_related_section(topic_name: str, kb: dict, today_topics: list[str], date: str) -> list[str]:
    """Build cross-reference sections: same-day links + historical related topics."""
    lines = []

    same_day = [t for t in today_topics if t != topic_name]
    if same_day:
        lines.append("## 相关话题（今日）")
        for t in same_day:
            lines.append(f"- [[{safe_filename(t)}|{t}]]")
        lines.append("")

    kb_topic = kb.get("topics", {}).get(topic_name, {})
    related = kb_topic.get("related_topics", [])
    historical = [r for r in related if r not in today_topics]

    if historical:
        lines.append("## 相关历史热点")
        for r in historical[:5]:
            r_data = kb.get("topics", {}).get(r, {})
            first = r_data.get("first_seen", "")
            peak = r_data.get("peak_score", 0)
            days = len(r_data.get("appearances", []))
            lines.append(f"- **{r}** — 首次出现 {first}，峰值 {peak}分，持续 {days} 天")
        lines.append("")

    appearances = kb_topic.get("appearances", [])
    if len(appearances) >= 2:
        lines.append("## 热度趋势")
        lines.append("| 日期 | 热度 | 趋势方向 |")
        lines.append("|------|------|----------|")
        direction_map = {"rising": "↑上升", "peak": "●顶峰", "declining": "↓下降", "emerging": "★萌芽"}
        for a in appearances[-7:]:
            d = direction_map.get(a.get("direction", ""), a.get("direction", ""))
            lines.append(f"| {a['date']} | {a['score']} | {d} |")
        lines.append("")

    return lines


def build_topic_note(trend: dict, date: str, kb: dict = None, today_topics: list[str] = None) -> str:
    """Build a single topic markdown note."""
    brief = trend.get("brief", {})
    topic = trend.get("topic", "Unknown")
    score = trend.get("score", 0)
    direction = trend.get("direction", "")
    category = trend.get("category", "")
    platforms = trend.get("platforms", [])
    summary = trend.get("summary", "")

    direction_map = {"rising": "上升", "peak": "顶峰", "declining": "下降", "emerging": "萌芽"}
    direction_cn = direction_map.get(direction, direction)

    lines = [
        "---",
        f"date: {date}",
        f"score: {score}",
        f"trend: {direction}",
        f"category: {category}",
        f"platforms: [{', '.join(platforms)}]",
        f"tags: [{category}, 热点, 内容创作]",
        "---",
        "",
        f"# {topic}",
        "",
        "## 趋势概况",
        f"- 热度：{score}/100 | 趋势：{direction_cn}",
        f"- 覆盖平台：{', '.join(platforms)}",
        f"- 概要：{summary}",
        "",
    ]

    if isinstance(brief, dict) and "error" not in brief:
        angles = brief.get("angles", [])
        if angles:
            lines.append("## 创作角度")
            for a in angles:
                name = a.get("name", "")
                desc = a.get("description", "")
                plat = a.get("best_platform", "")
                appeal = a.get("appeal", "")
                lines.append(f"### {name}")
                lines.append(f"- {desc}")
                lines.append(f"- 适合平台：{plat} | 吸引力：{appeal}")
                lines.append("")

        outlines = brief.get("outlines", {})
        if outlines:
            lines.append("## 内容大纲")

            sv = outlines.get("short_video", {})
            if sv:
                lines.append("### 短视频版（60秒）")
                lines.append(f"1. **开头hook**: {sv.get('hook', '')}")
                beats = sv.get("beats", sv.get("points", []))
                for j, pt in enumerate(beats, 2):
                    if isinstance(pt, dict):
                        lines.append(f"{j}. {pt.get('content', '')} *({pt.get('visual', '')})*")
                    else:
                        lines.append(f"{j}. {pt}")
                if sv.get("climax"):
                    lines.append(f"- **高潮点**: {sv['climax']}")
                lines.append(f"- **CTA**: {sv.get('cta', '')}")
                if sv.get("bgm_style"):
                    lines.append(f"- **BGM**: {sv['bgm_style']}")
                lines.append("")

            xhs = outlines.get("xiaohongshu", {})
            if xhs:
                lines.append("### 小红书图文版")
                lines.append(f"**封面标题**: {xhs.get('cover_title', '')}")
                if xhs.get("cover_subtitle"):
                    lines.append(f"**副标题**: {xhs['cover_subtitle']}")
                slides = xhs.get("slides", xhs.get("key_points", []))
                for i, pt in enumerate(slides, 1):
                    lines.append(f"{i}. {pt}")
                if xhs.get("body_structure"):
                    lines.append(f"\n**结构**: {xhs['body_structure']}")
                all_tags = (
                    xhs.get("hashtags", []) +
                    xhs.get("hashtags_main", []) +
                    xhs.get("hashtags_traffic", []) +
                    xhs.get("hashtags_longtail", [])
                )
                if all_tags:
                    lines.append(f"\n{' '.join(all_tags)}")
                lines.append("")

            article = outlines.get("article", {})
            if article:
                lines.append("### 公众号长文版")
                lines.append(f"**标题**: {article.get('title', '')}")
                intro = article.get("intro", article.get("intro_strategy", ""))
                lines.append(f"\n> {intro}")
                for sec in article.get("sections", []):
                    if isinstance(sec, dict):
                        lines.append(f"#### {sec.get('heading', '')}")
                        lines.append(f"- 核心论点: {sec.get('core_point', '')}")
                        lines.append(f"- 论据方向: {sec.get('evidence', '')}")
                    else:
                        lines.append(f"- {sec}")
                conclusion = article.get("conclusion", article.get("conclusion_strategy", ""))
                lines.append(f"\n**结语**: {conclusion}")
                lines.append("")

        titles = brief.get("titles", {})
        if titles:
            lines.append("## 标题建议")
            platform_names = {
                "douyin": "抖音", "xiaohongshu": "小红书",
                "gongzhonghao": "公众号", "zhihu": "知乎", "bilibili": "B站"
            }
            for key, val in titles.items():
                pname = platform_names.get(key, key)
                if isinstance(val, list):
                    for t in val:
                        lines.append(f"- **[{pname}]** {t}")
                else:
                    lines.append(f"- **[{pname}]** {val}")
            lines.append("")

        materials = brief.get("materials", [])
        if materials:
            lines.append("## 关键素材")
            if isinstance(materials, dict):
                for category, items in materials.items():
                    lines.append(f"### {category}")
                    if isinstance(items, list):
                        for m in items:
                            lines.append(f"- {m}")
                    else:
                        lines.append(f"- {items}")
                    lines.append("")
            elif isinstance(materials, list):
                for m in materials:
                    lines.append(f"- {m}")
                lines.append("")

        benchmarks = brief.get("benchmarks", [])
        if benchmarks:
            lines.append("## 对标案例")
            for b in benchmarks:
                who = b.get("author_type", "") or b.get("brand", "") or b.get("creator_type", "")
                what = b.get("content_desc", "") or b.get("topic", "")
                why = b.get("reason", "") or b.get("why_viral", "")
                label = f"{who}"
                if what:
                    label += f" · {what}"
                lines.append(
                    f"- **[{b.get('platform', '')}]** {label} — "
                    f"{b.get('metrics', '')} ({why})"
                )
            lines.append("")

        rec = brief.get("recommendation", {})
        if rec:
            lines.append("## 推荐发布")
            lines.append(f"- 最佳形式：{rec.get('best_format', '')}")
            lines.append(f"- 最佳时间：{rec.get('best_time', '')}")
            priority = rec.get("platform_priority", [])
            if priority:
                lines.append(f"- 平台优先级：{' > '.join(priority)}")
            lines.append("")

    if kb and today_topics:
        related_lines = build_related_section(topic, kb, today_topics, date)
        lines.extend(related_lines)

    return "\n".join(lines)


def build_dashboard(trends: list[dict], date: str, kb: dict = None) -> str:
    """Build the Dashboard markdown note with weekly trend summary."""
    hot_count = sum(1 for t in trends if t.get("score", 0) >= 70)
    emerging_count = sum(
        1 for t in trends
        if t.get("is_emerging") or t.get("direction") == "emerging"
    )

    lines = [
        "---",
        f"date: {date}",
        "type: trend-dashboard",
        f"total_topics: {len(trends)}",
        f"hot_count: {hot_count}",
        f"emerging_count: {emerging_count}",
        "---",
        "",
        f"# {date} 热点情报",
        "",
        f"> 共扫描 {len(trends)} 个热点话题，{hot_count} 个正在火，{emerging_count} 个即将火",
        "",
        "## 趋势总览",
        "",
        "| 排名 | 话题 | 热度 | 趋势 | 类别 | 覆盖平台 |",
        "|------|------|------|------|------|----------|",
    ]

    direction_map = {"rising": "↑上升", "peak": "●顶峰", "declining": "↓下降", "emerging": "★萌芽"}

    for i, t in enumerate(trends, 1):
        topic = t.get("topic", "")
        category = t.get("category", "其他")
        safe_topic = safe_filename(topic)
        safe_cat = safe_filename(category)
        direction = direction_map.get(t.get("direction", ""), t.get("direction", ""))
        platforms_str = ", ".join(t.get("platforms", []))
        lines.append(
            f"| {i} | [[Topics/{safe_cat}/{safe_topic}\\|{topic}]] | {t.get('score', 0)} | "
            f"{direction} | {category} | {platforms_str} |"
        )

    lines.append("")
    lines.append("## 分类统计")
    lines.append("")

    categories = {}
    for t in trends:
        cat = t.get("category", "其他")
        categories[cat] = categories.get(cat, 0) + 1
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        lines.append(f"- **{cat}**: {count} 个话题")

    lines.append("")

    if kb:
        snapshots = kb.get("daily_snapshots", {})
        recent_dates = sorted(snapshots.keys(), reverse=True)[:7]
        if len(recent_dates) >= 2:
            lines.append("## 本周趋势")
            lines.append("")
            lines.append("| 日期 | 话题数 | 正在火 | 即将火 |")
            lines.append("|------|--------|--------|--------|")
            for d in reversed(recent_dates):
                s = snapshots[d]
                lines.append(f"| {d} | {s.get('topic_count', 0)} | {s.get('hot', 0)} | {s.get('emerging', 0)} |")
            lines.append("")

        persistent = []
        for name, data in kb.get("topics", {}).items():
            apps = data.get("appearances", [])
            if len(apps) >= 2:
                persistent.append({
                    "topic": name,
                    "days": len(apps),
                    "peak": data.get("peak_score", 0),
                    "first": data.get("first_seen", ""),
                })
        if persistent:
            persistent.sort(key=lambda x: (-x["days"], -x["peak"]))
            lines.append("## 持续热点")
            lines.append("")
            for p in persistent[:8]:
                lines.append(f"- **{p['topic']}** — 持续 {p['days']} 天，峰值 {p['peak']}分（首次 {p['first']}）")
            lines.append("")

    return "\n".join(lines)


def build_weekly_digest(kb: dict, date: str) -> str:
    """Generate weekly digest note summarizing the past 7 days."""
    snapshots = kb.get("daily_snapshots", {})
    topics_db = kb.get("topics", {})
    themes_db = kb.get("themes", {})

    sorted_dates = sorted(snapshots.keys(), reverse=True)
    week_dates = sorted_dates[:7]
    if not week_dates:
        return ""

    week_start = min(week_dates)
    week_end = max(week_dates)

    week_topics = set()
    for d in week_dates:
        week_topics.update(snapshots[d].get("topics", []))

    total_hot = sum(snapshots[d].get("hot", 0) for d in week_dates)
    total_emerging = sum(snapshots[d].get("emerging", 0) for d in week_dates)

    persistent = []
    for name in week_topics:
        data = topics_db.get(name, {})
        apps = [a for a in data.get("appearances", []) if a.get("date") in set(week_dates)]
        if len(apps) >= 2:
            persistent.append({"topic": name, "days": len(apps), "peak": data.get("peak_score", 0)})
    persistent.sort(key=lambda x: (-x["days"], -x["peak"]))

    cat_dist = {}
    for name in week_topics:
        cat = topics_db.get(name, {}).get("category", "其他")
        cat_dist[cat] = cat_dist.get(cat, 0) + 1

    top_themes = sorted(
        [(t, d) for t, d in themes_db.items()],
        key=lambda x: -x[1].get("frequency", 0)
    )[:5]

    lines = [
        "---",
        f"date: {date}",
        "type: weekly-digest",
        f"week_range: {week_start} ~ {week_end}",
        f"total_topics: {len(week_topics)}",
        "---",
        "",
        f"# 周报 · {week_start} ~ {week_end}",
        "",
        f"> 本周共追踪 **{len(week_topics)}** 个热点话题，"
        f"累计 **{total_hot}** 次正在火，**{total_emerging}** 次即将火",
        "",
        "## 每日概览",
        "",
        "| 日期 | 话题数 | 正在火 | 即将火 |",
        "|------|--------|--------|--------|",
    ]

    for d in sorted(week_dates):
        s = snapshots[d]
        lines.append(f"| [[{d}/_Dashboard\\|{d}]] | {s.get('topic_count', 0)} | {s.get('hot', 0)} | {s.get('emerging', 0)} |")

    lines.append("")

    if persistent:
        lines.append("## 持续热点（多日出现）")
        lines.append("")
        for p in persistent[:10]:
            lines.append(f"- **{p['topic']}** — 持续 {p['days']} 天，峰值 {p['peak']}分")
        lines.append("")

    lines.append("## 分类分布")
    lines.append("")
    for cat, count in sorted(cat_dist.items(), key=lambda x: -x[1]):
        lines.append(f"- **{cat}**: {count} 个话题")
    lines.append("")

    if top_themes:
        lines.append("## 热门主题")
        lines.append("")
        for theme, data in top_themes:
            lines.append(f"- **{theme}** — 出现 {data.get('frequency', 0)} 次，涉及 {len(data.get('topic_ids', []))} 个话题")
        lines.append("")

    return "\n".join(lines)


def build_copywriting_note(trend: dict, platform_key: str, platform_name: str, date: str) -> str:
    """Build a platform-specific copywriting draft from brief outlines."""
    brief = trend.get("brief", {})
    if not isinstance(brief, dict) or "error" in brief:
        return ""

    topic = trend.get("topic", "")
    outlines = brief.get("outlines", {})
    titles = brief.get("titles", {})
    rec = brief.get("recommendation", {})

    lines = [
        "---",
        f"date: {date}",
        f"topic: {topic}",
        f"platform: {platform_name}",
        f"type: copywriting-draft",
        "---",
        "",
    ]

    platform_titles = titles.get(platform_key, [])
    if isinstance(platform_titles, str):
        platform_titles = [platform_titles]

    if platform_key == "douyin":
        lines.append(f"# 抖音短视频 · {topic}")
        lines.append("")
        sv = outlines.get("short_video", {})
        if not sv:
            return ""
        if platform_titles:
            lines.append("## 标题备选")
            for t in platform_titles:
                lines.append(f"- {t}")
            lines.append("")
        lines.append("## 脚本")
        lines.append(f"**Hook（前3秒）**: {sv.get('hook', '')}")
        lines.append("")
        beats = sv.get("beats", sv.get("points", []))
        for i, pt in enumerate(beats, 1):
            if isinstance(pt, dict):
                lines.append(f"**节拍{i}**: {pt.get('content', '')}")
                if pt.get("visual"):
                    lines.append(f"  画面：{pt['visual']}")
            else:
                lines.append(f"**节拍{i}**: {pt}")
        lines.append("")
        if sv.get("climax"):
            lines.append(f"**高潮点**: {sv['climax']}")
        lines.append(f"**CTA**: {sv.get('cta', '')}")
        if sv.get("bgm_style"):
            lines.append(f"**BGM风格**: {sv['bgm_style']}")
        if sv.get("duration"):
            lines.append(f"**建议时长**: {sv['duration']}")

    elif platform_key == "xiaohongshu":
        lines.append(f"# 小红书图文 · {topic}")
        lines.append("")
        xhs = outlines.get("xiaohongshu", {})
        if not xhs:
            return ""
        lines.append(f"## 封面")
        lines.append(f"**大字标题**: {xhs.get('cover_title', '')}")
        if xhs.get("cover_subtitle"):
            lines.append(f"**副标题**: {xhs['cover_subtitle']}")
        lines.append("")
        if platform_titles:
            lines.append("## 标题备选")
            for t in platform_titles:
                lines.append(f"- {t}")
            lines.append("")
        slides = xhs.get("slides", xhs.get("key_points", []))
        if slides:
            lines.append("## 图片内容")
            for i, pt in enumerate(slides, 1):
                lines.append(f"**第{i}张**: {pt}")
            lines.append("")
        body = xhs.get("body_structure", "")
        if body:
            lines.append("")
            lines.append("## 正文节奏")
            lines.append(body)
        lines.append("")
        all_tags = (
            xhs.get("hashtags", []) +
            xhs.get("hashtags_main", []) +
            xhs.get("hashtags_traffic", []) +
            xhs.get("hashtags_longtail", [])
        )
        if all_tags:
            lines.append("## 话题标签")
            lines.append(" ".join(all_tags))

    elif platform_key == "gongzhonghao":
        lines.append(f"# 公众号长文 · {topic}")
        lines.append("")
        article = outlines.get("article", {})
        if not article:
            return ""
        lines.append(f"**标题**: {article.get('title', '')}")
        if article.get("subtitle"):
            lines.append(f"**副标题**: {article['subtitle']}")
        lines.append("")
        if platform_titles:
            lines.append("## 标题备选")
            for t in platform_titles:
                lines.append(f"- {t}")
            lines.append("")
        intro = article.get("intro", article.get("intro_strategy", ""))
        if intro:
            lines.append("## 引言")
            lines.append(f"> {intro}")
            lines.append("")
        sections = article.get("sections", [])
        if sections:
            lines.append("## 正文框架")
            for sec in sections:
                if isinstance(sec, dict):
                    lines.append(f"### {sec.get('heading', '')}")
                    lines.append(f"- 核心论点: {sec.get('core_point', '')}")
                    lines.append(f"- 论据方向: {sec.get('evidence', '')}")
                    if sec.get("words"):
                        lines.append(f"- 建议字数: {sec['words']}字")
                    lines.append("")
                else:
                    lines.append(f"- {sec}")
        conclusion = article.get("conclusion", article.get("conclusion_strategy", ""))
        if conclusion:
            lines.append("## 结语")
            lines.append(conclusion)
            lines.append("")
        img_suggestions = article.get("image_suggestions", [])
        if img_suggestions:
            lines.append("## 配图建议")
            for img in img_suggestions:
                lines.append(f"- {img}")
    else:
        title_list = platform_titles
        if not title_list:
            return ""
        lines.append(f"# {platform_name} · {topic}")
        lines.append("")
        lines.append("## 标题备选")
        for t in title_list:
            lines.append(f"- {t}")

    lines.append("")
    lines.append(f"---")
    lines.append(f"*来源话题: [[Topics/{safe_filename(trend.get('category', '其他'))}/{safe_filename(topic)}|{topic}]]*")

    return "\n".join(lines)


PLATFORM_MAP = {
    "douyin": "抖音",
    "xiaohongshu": "小红书",
    "gongzhonghao": "公众号",
    "zhihu": "知乎",
    "bilibili": "B站",
}


def main():
    parser = base_argparser("Generate Obsidian vault notes")
    parser.add_argument("--vault", "-v", help="Obsidian vault root path")
    parser.add_argument("--no-copywriting", action="store_true",
                        help="Skip copywriting draft generation")
    args = parser.parse_args()
    handle_schema(args, SCHEMA)

    input_data = read_json_input(args)
    trends = input_data.get("briefed_trends", [])

    if not trends:
        fail("No briefed_trends provided. Pipe output from content_brief.")

    vault_root = Path(args.vault) if args.vault else Path(".")
    date = today_str()
    output_dir = vault_root / "HotCreator" / date
    topics_dir = output_dir / "Topics"
    copy_dir = output_dir / "Copywriting"

    kb = load_knowledge_base()
    today_topics = [t.get("topic", "") for t in trends]

    dashboard_content = build_dashboard(trends, date, kb=kb)
    dashboard_path = output_dir / "_Dashboard.md"
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text(dashboard_content, encoding="utf-8")

    topic_paths = []
    copywriting_paths = []

    for trend in trends:
        topic = trend.get("topic", "Unknown")
        category = trend.get("category", "其他")
        filename = safe_filename(topic) + ".md"

        cat_dir = topics_dir / safe_filename(category)
        cat_dir.mkdir(parents=True, exist_ok=True)

        note_content = build_topic_note(trend, date, kb=kb, today_topics=today_topics)
        note_path = cat_dir / filename
        note_path.write_text(note_content, encoding="utf-8")
        topic_paths.append(str(note_path))

        if not args.no_copywriting:
            brief = trend.get("brief", {})
            if isinstance(brief, dict) and "error" not in brief:
                for pkey, pname in PLATFORM_MAP.items():
                    draft = build_copywriting_note(trend, pkey, pname, date)
                    if draft:
                        plat_dir = copy_dir / pname
                        plat_dir.mkdir(parents=True, exist_ok=True)
                        draft_path = plat_dir / (safe_filename(topic) + ".md")
                        draft_path.write_text(draft, encoding="utf-8")
                        copywriting_paths.append(str(draft_path))

    # Weekly digest
    weekly_path = None
    if len(kb.get("daily_snapshots", {})) >= 2:
        digest = build_weekly_digest(kb, date)
        if digest:
            weekly_path = vault_root / "HotCreator" / "_WeeklyDigest.md"
            weekly_path.write_text(digest, encoding="utf-8")
            print(f"[export_obsidian] Weekly digest: {weekly_path}", file=sys.stderr)

    print(f"[export_obsidian] Dashboard: {dashboard_path}", file=sys.stderr)
    print(f"[export_obsidian] Topics: {len(topic_paths)} notes (by category)", file=sys.stderr)
    if copywriting_paths:
        print(f"[export_obsidian] Copywriting: {len(copywriting_paths)} drafts (by platform)", file=sys.stderr)

    result = {
        "dashboard": str(dashboard_path),
        "topics": topic_paths,
    }
    if copywriting_paths:
        result["copywriting"] = copywriting_paths
    if weekly_path:
        result["weekly_digest"] = str(weekly_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
