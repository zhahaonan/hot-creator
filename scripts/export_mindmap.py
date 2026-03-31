#!/usr/bin/env python3
"""
export_mindmap — Generate interactive HTML graph visualization (Obsidian-style).
Force-directed network graph with topic nodes, theme connections, and platform strategy.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import json
from pathlib import Path
from collections import defaultdict
from _common import (
    base_argparser, handle_schema, read_json_input, write_json_output,
    fail, today_str, OUTPUT_DIR
)

SCHEMA = {
    "name": "export_mindmap",
    "description": "Generate interactive HTML graph (D3 force-directed) with thematic connections and combo opportunities.",
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
            "file": {"type": "string", "description": "Path to generated .html graph file"}
        }
    },
    "examples": {
        "cli": "python scripts/export_mindmap.py -i briefs.json -o output/mindmap.html"
    },
    "errors": {
        "no_data": "无 briefed_trends → 先运行 content_brief"
    }
}

DIRECTION_MAP = {"rising": "↑上升", "peak": "●顶峰", "declining": "↓下降", "emerging": "★萌芽"}

THEME_KEYWORDS = {
    "社会公平": ["公平", "不公", "争议", "黑幕", "举报", "维权", "监管", "上限", "规则"],
    "年轻人焦虑": ["考研", "就业", "工资", "贷款", "负债", "内卷", "躺平", "进厂", "找工作", "PMI"],
    "信任危机": ["举报", "造谣", "泄露", "偷税", "诬告", "真相", "反转", "官方回应"],
    "技术变革": ["AI", "Claude", "源码", "编程", "开源", "泄露", "模型", "Anthropic", "Code"],
    "政策监管": ["监管", "新规", "利率", "上限", "PMI", "扩张", "政策", "制造业"],
    "情绪消费": ["吃瓜", "热搜", "粉丝", "举报", "营销号", "流量", "围观"],
    "创业/职场": ["PMI", "制造业", "就业", "工厂", "招工", "工资", "转型", "从业者"],
}

CATEGORY_COLORS = {
    "教育": "#e74c3c",
    "娱乐": "#e67e22",
    "科技": "#3498db",
    "财经": "#2ecc71",
    "社会": "#9b59b6",
    "政治": "#1abc9c",
    "体育": "#f39c12",
    "健康": "#e91e63",
    "其他": "#95a5a6",
}

THEME_COLORS = {
    "社会公平": "#ff6b6b",
    "年轻人焦虑": "#ffa502",
    "信任危机": "#ff4757",
    "技术变革": "#1e90ff",
    "政策监管": "#2ed573",
    "情绪消费": "#ff6348",
    "创业/职场": "#ffa502",
}


def detect_themes(trend: dict) -> list[str]:
    """Detect thematic tags for a trend based on topic, summary, and brief content."""
    text = " ".join([
        trend.get("topic", ""),
        trend.get("summary", ""),
        trend.get("category", ""),
    ])
    brief = trend.get("brief", {})
    if isinstance(brief, dict) and "error" not in brief:
        for a in brief.get("angles", []):
            text += " " + a.get("name", "") + " " + a.get("description", "")
        mats = brief.get("materials", {})
        if isinstance(mats, dict):
            for trigger in mats.get("emotion_triggers", []):
                text += " " + trigger

    found = []
    for theme, keywords in THEME_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            found.append(theme)
    return found


def find_connections(trends: list[dict]) -> list[dict]:
    """Find thematic connections between topics."""
    topic_themes = {}
    for t in trends:
        topic_themes[t.get("topic", "")] = detect_themes(t)

    theme_to_topics = defaultdict(list)
    for topic, themes in topic_themes.items():
        for theme in themes:
            theme_to_topics[theme].append(topic)

    connections = []
    for theme, topics in sorted(theme_to_topics.items(), key=lambda x: -len(x[1])):
        if len(topics) >= 2:
            connections.append({"theme": theme, "topics": topics})
    return connections


def find_combos(trends: list[dict], connections: list[dict]) -> list[dict]:
    """Generate content combination ideas from connected topics."""
    combos = []
    seen_pairs = set()

    for conn in connections:
        topics = conn["topics"]
        theme = conn["theme"]
        for i in range(len(topics)):
            for j in range(i + 1, len(topics)):
                pair = tuple(sorted([topics[i], topics[j]]))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)

                t1_short = topics[i][:12] + ("..." if len(topics[i]) > 12 else "")
                t2_short = topics[j][:12] + ("..." if len(topics[j]) > 12 else "")

                combos.append({
                    "topics": [topics[i], topics[j]],
                    "theme": theme,
                    "label": f"{t1_short} × {t2_short}",
                    "idea": _combo_idea(topics[i], topics[j], theme),
                })

    return combos[:8]


def _combo_idea(t1: str, t2: str, theme: str) -> str:
    """Generate a short combo content idea."""
    ideas = {
        "社会公平": "从制度公平角度串联两个事件，做系列内容",
        "年轻人焦虑": "以年轻人视角贯穿，引发强烈共鸣",
        "信任危机": "围绕'我们该相信什么'做深度专题",
        "技术变革": "技术浪潮下的机遇与隐患，做科普+观点",
        "政策监管": "政策组合拳解读，对普通人的影响汇总",
        "情绪消费": "反思舆论操控，做媒介素养内容",
        "创业/职场": "经济数据+就业现实，做职场规划指南",
    }
    return ideas.get(theme, "跨话题视角组合，提供独特内容角度")


def build_platform_strategy(trends: list[dict]) -> dict:
    """Aggregate platform strategy across all topics."""
    platform_count = defaultdict(int)
    platform_topics = defaultdict(list)

    for t in trends:
        brief = t.get("brief", {})
        if not isinstance(brief, dict) or "error" in brief:
            continue
        rec = brief.get("recommendation", {})
        priority = rec.get("platform_priority", [])
        for i, p in enumerate(priority):
            platform_count[p] += len(priority) - i
            if t.get("topic", "") not in platform_topics[p]:
                platform_topics[p].append(t.get("topic", "")[:15])

    sorted_platforms = sorted(platform_count.items(), key=lambda x: -x[1])
    return {
        "ranking": sorted_platforms,
        "topics_by_platform": dict(platform_topics),
    }


def classify_trends(trends: list[dict]) -> dict:
    """Classify trends into groups with NO duplication."""
    seen = set()
    hot, emerging, moderate = [], [], []

    sorted_trends = sorted(trends, key=lambda t: -t.get("score", 0))

    for t in sorted_trends:
        tid = t.get("topic", "")
        if tid in seen:
            continue

        is_emerging = t.get("direction") == "emerging" or t.get("is_emerging")
        is_hot = t.get("score", 0) >= 70

        if is_hot and not is_emerging:
            hot.append(t)
        elif is_emerging:
            emerging.append(t)
        elif t.get("score", 0) >= 40:
            moderate.append(t)
        seen.add(tid)

    return {"hot": hot, "emerging": emerging, "moderate": moderate}


def build_graph_data(trends: list[dict], date: str) -> dict:
    """Build D3 force-graph data: nodes + links."""
    groups = classify_trends(trends)
    all_unique = groups["hot"] + groups["emerging"] + groups["moderate"]

    connections = find_connections(all_unique)
    combos = find_combos(all_unique, connections)
    platform_strat = build_platform_strategy(all_unique)

    nodes = []
    links = []
    node_ids = set()

    # --- Topic nodes ---
    for t in all_unique:
        topic = t.get("topic", "")
        if topic in node_ids:
            continue
        node_ids.add(topic)

        score = t.get("score", 0)
        category = t.get("category", "其他")
        direction = t.get("direction", "")
        platforms = t.get("platforms", [])
        themes = detect_themes(t)
        summary = t.get("summary", "")

        is_hot = t in groups["hot"]
        is_emerging = t in groups["emerging"]
        group = "hot" if is_hot else ("emerging" if is_emerging else "moderate")

        brief = t.get("brief", {})
        angles = []
        first_platform = ""
        trending_window = ""
        if isinstance(brief, dict) and "error" not in brief:
            for a in brief.get("angles", [])[:3]:
                angles.append({
                    "name": a.get("name", ""),
                    "platform": a.get("best_platform", ""),
                    "appeal": a.get("appeal", ""),
                })
            rec = brief.get("recommendation", {})
            first_platform = rec.get("first_platform", "")
            if not first_platform:
                prio = rec.get("platform_priority", [])
                first_platform = prio[0] if prio else ""
            trending_window = rec.get("trending_window", rec.get("best_time", ""))

        nodes.append({
            "id": topic,
            "type": "topic",
            "group": group,
            "score": score,
            "category": category,
            "color": CATEGORY_COLORS.get(category, "#95a5a6"),
            "direction": DIRECTION_MAP.get(direction, ""),
            "platforms": platforms,
            "themes": themes[:3],
            "summary": summary,
            "angles": angles,
            "first_platform": first_platform,
            "trending_window": trending_window,
            "radius": max(12, min(35, score * 0.35)),
        })

    # --- Theme nodes (connectors) ---
    for conn in connections:
        theme = conn["theme"]
        if theme not in node_ids:
            node_ids.add(theme)
            nodes.append({
                "id": theme,
                "type": "theme",
                "color": THEME_COLORS.get(theme, "#aaa"),
                "radius": 8,
                "topic_count": len(conn["topics"]),
            })

        for topic in conn["topics"]:
            if topic in node_ids:
                links.append({
                    "source": topic,
                    "target": theme,
                    "type": "theme",
                })

    # --- Platform nodes ---
    for plat, weight in platform_strat["ranking"][:6]:
        if plat not in node_ids:
            node_ids.add(plat)
            nodes.append({
                "id": plat,
                "type": "platform",
                "color": "#7c8db5",
                "radius": 6,
                "weight": weight,
            })

        for topic in platform_strat["topics_by_platform"].get(plat, []):
            full_topic = None
            for t in all_unique:
                if t.get("topic", "")[:15] == topic:
                    full_topic = t.get("topic", "")
                    break
            if full_topic and full_topic in node_ids:
                links.append({
                    "source": full_topic,
                    "target": plat,
                    "type": "platform",
                })

    return {
        "nodes": nodes,
        "links": links,
        "combos": combos,
        "date": date,
        "stats": {
            "hot": len(groups["hot"]),
            "emerging": len(groups["emerging"]),
            "moderate": len(groups["moderate"]),
            "total": len(all_unique),
        },
    }


def wrap_html(graph_data: dict, date: str) -> str:
    """Generate standalone HTML with D3 force-directed graph (Obsidian-style)."""
    data_json = json.dumps(graph_data, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{date} 热点趋势图谱 - HotCreator</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{
  width: 100vw; height: 100vh; overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
  background: #1a1a2e;
  color: #e0e0e0;
}}
#graph {{ width: 100%; height: 100%; }}

.title-bar {{
  position: fixed; top: 16px; left: 20px; z-index: 100;
  font-size: 15px; color: #fff; background: rgba(26,26,46,0.85);
  padding: 10px 18px; border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.08);
  backdrop-filter: blur(12px);
  font-weight: 600;
  letter-spacing: 0.5px;
}}
.title-bar .sub {{ font-size: 11px; color: #888; font-weight: 400; margin-top: 3px; }}

.toolbar {{
  position: fixed; top: 16px; right: 20px; z-index: 100;
  display: flex; gap: 6px;
}}
.toolbar button {{
  padding: 7px 14px; border: 1px solid rgba(255,255,255,0.1); border-radius: 8px;
  background: rgba(26,26,46,0.85); color: #ccc; cursor: pointer; font-size: 12px;
  backdrop-filter: blur(12px); transition: all 0.2s;
}}
.toolbar button:hover {{ background: rgba(60,60,100,0.9); color: #fff; border-color: rgba(255,255,255,0.2); }}
.toolbar button.active {{ background: rgba(100,100,200,0.4); color: #fff; border-color: rgba(130,130,255,0.4); }}

.legend {{
  position: fixed; bottom: 20px; left: 20px; z-index: 100;
  background: rgba(26,26,46,0.85); padding: 14px 18px; border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.08);
  backdrop-filter: blur(12px); font-size: 11px; color: #999;
  line-height: 2;
}}
.legend-item {{ display: flex; align-items: center; gap: 8px; }}
.legend-dot {{
  width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0;
}}

.detail-panel {{
  position: fixed; top: 80px; right: 20px; z-index: 100;
  width: 340px; max-height: calc(100vh - 120px);
  background: rgba(26,26,46,0.92); border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.1);
  backdrop-filter: blur(16px);
  padding: 20px; overflow-y: auto;
  display: none; transition: all 0.3s;
}}
.detail-panel.show {{ display: block; }}
.detail-panel .close-btn {{
  position: absolute; top: 10px; right: 14px;
  background: none; border: none; color: #888; font-size: 18px; cursor: pointer;
}}
.detail-panel .close-btn:hover {{ color: #fff; }}
.detail-panel h3 {{
  font-size: 16px; color: #fff; margin-bottom: 8px; padding-right: 24px; line-height: 1.4;
}}
.detail-panel .meta {{ font-size: 12px; color: #888; margin-bottom: 12px; }}
.detail-panel .meta span {{ margin-right: 10px; }}
.detail-panel .score-badge {{
  display: inline-block; padding: 2px 10px; border-radius: 12px;
  font-size: 13px; font-weight: 600; margin-bottom: 10px;
}}
.detail-panel .summary {{ font-size: 13px; color: #bbb; line-height: 1.6; margin-bottom: 14px; }}
.detail-panel .section-title {{ font-size: 12px; color: #7c8db5; margin: 12px 0 6px; font-weight: 600; }}
.detail-panel .angle-item {{
  padding: 8px 10px; margin-bottom: 6px; border-radius: 8px;
  background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06);
}}
.detail-panel .angle-name {{ font-size: 13px; color: #ddd; }}
.detail-panel .angle-meta {{ font-size: 11px; color: #888; margin-top: 3px; }}
.detail-panel .theme-tag {{
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-size: 11px; margin-right: 4px; margin-bottom: 4px;
  background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1);
}}
.detail-panel .rec {{ font-size: 12px; color: #aaa; margin-top: 10px; padding: 8px; border-radius: 6px; background: rgba(255,255,255,0.03); }}

.combo-panel {{
  position: fixed; bottom: 20px; right: 20px; z-index: 100;
  width: 320px; max-height: 240px;
  background: rgba(26,26,46,0.85); border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.08);
  backdrop-filter: blur(12px);
  padding: 14px; overflow-y: auto;
  display: none;
}}
.combo-panel.show {{ display: block; }}
.combo-panel h4 {{ font-size: 13px; color: #fff; margin-bottom: 8px; }}
.combo-item {{
  padding: 6px 8px; margin-bottom: 4px; border-radius: 6px;
  font-size: 11px; color: #bbb; background: rgba(255,255,255,0.04);
}}
.combo-item strong {{ color: #ddd; }}

.detail-panel::-webkit-scrollbar, .combo-panel::-webkit-scrollbar {{ width: 4px; }}
.detail-panel::-webkit-scrollbar-thumb, .combo-panel::-webkit-scrollbar-thumb {{
  background: rgba(255,255,255,0.15); border-radius: 2px;
}}

@keyframes pulse {{
  0%, 100% {{ r: attr(r); opacity: 1; }}
  50% {{ opacity: 0.6; }}
}}
</style>
<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
</head>
<body>
<div class="title-bar">
  🔥 HotCreator · {date} 热点趋势图谱
  <div class="sub" id="stats"></div>
</div>

<div class="toolbar">
  <button onclick="resetView()">📐 重置视图</button>
  <button id="btnTopic" class="active" onclick="toggleFilter('topic')">话题</button>
  <button id="btnTheme" class="active" onclick="toggleFilter('theme')">主题</button>
  <button id="btnPlatform" onclick="toggleFilter('platform')">平台</button>
  <button onclick="toggleCombos()">💡 组合机会</button>
</div>

<div class="legend" id="legend"></div>

<div class="detail-panel" id="detail">
  <button class="close-btn" onclick="closeDetail()">&times;</button>
  <div id="detailContent"></div>
</div>

<div class="combo-panel" id="comboPanel">
  <h4>💡 组合创作机会</h4>
  <div id="comboList"></div>
</div>

<svg id="graph"></svg>

<script>
const DATA = {data_json};

const width = window.innerWidth;
const height = window.innerHeight;

const svg = d3.select("#graph")
  .attr("width", width)
  .attr("height", height);

const defs = svg.append("defs");
const glow = defs.append("filter").attr("id", "glow");
glow.append("feGaussianBlur").attr("stdDeviation", "3").attr("result", "coloredBlur");
const feMerge = glow.append("feMerge");
feMerge.append("feMergeNode").attr("in", "coloredBlur");
feMerge.append("feMergeNode").attr("in", "SourceGraphic");

const container = svg.append("g");
const linkGroup = container.append("g").attr("class", "links");
const nodeGroup = container.append("g").attr("class", "nodes");
const labelGroup = container.append("g").attr("class", "labels");

const zoom = d3.zoom()
  .scaleExtent([0.2, 5])
  .on("zoom", (e) => container.attr("transform", e.transform));
svg.call(zoom);

const visibleTypes = new Set(["topic", "theme"]);

const simulation = d3.forceSimulation()
  .force("link", d3.forceLink().id(d => d.id).distance(d => {{
    if (d.type === "platform") return 160;
    if (d.type === "theme") return 120;
    return 140;
  }}).strength(d => d.type === "theme" ? 0.3 : 0.15))
  .force("charge", d3.forceManyBody().strength(d => {{
    if (d.type === "topic") return -400;
    if (d.type === "theme") return -150;
    return -80;
  }}))
  .force("center", d3.forceCenter(width / 2, height / 2))
  .force("collision", d3.forceCollide().radius(d => (d.radius || 8) + 15))
  .force("x", d3.forceX(width / 2).strength(0.03))
  .force("y", d3.forceY(height / 2).strength(0.03));

let allNodes = DATA.nodes;
let allLinks = DATA.links;
let linkElements, nodeElements, labelElements;

function getVisibleData() {{
  const nodes = allNodes.filter(n => visibleTypes.has(n.type));
  const nodeIds = new Set(nodes.map(n => n.id));
  const links = allLinks.filter(l => {{
    const src = typeof l.source === "object" ? l.source.id : l.source;
    const tgt = typeof l.target === "object" ? l.target.id : l.target;
    return nodeIds.has(src) && nodeIds.has(tgt);
  }});
  return {{ nodes, links }};
}}

function render() {{
  const {{ nodes, links }} = getVisibleData();

  linkElements = linkGroup.selectAll("line").data(links, d => {{
    const s = typeof d.source === "object" ? d.source.id : d.source;
    const t = typeof d.target === "object" ? d.target.id : d.target;
    return s + "-" + t;
  }});
  linkElements.exit().transition().duration(300).attr("opacity", 0).remove();
  linkElements = linkElements.enter().append("line")
    .attr("stroke", d => {{
      if (d.is_historical) return "rgba(180,180,255,0.1)";
      if (d.type === "related") return "rgba(255,200,100,0.15)";
      return d.type === "theme" ? "rgba(130,130,255,0.2)" : "rgba(120,140,180,0.12)";
    }})
    .attr("stroke-width", d => d.type === "theme" ? 1.5 : 1)
    .attr("stroke-dasharray", d => (d.is_historical || d.type === "related") ? "4,3" : "none")
    .attr("opacity", 0)
    .merge(linkElements)
    .transition().duration(500).attr("opacity", 1)
    .selection();

  nodeElements = nodeGroup.selectAll("circle").data(nodes, d => d.id);
  nodeElements.exit().transition().duration(300).attr("r", 0).remove();
  const nodeEnter = nodeElements.enter().append("circle")
    .attr("r", 0)
    .attr("fill", d => d.color || "#666")
    .attr("stroke", d => d.type === "topic" ? "rgba(255,255,255,0.15)" : "none")
    .attr("stroke-width", d => d.type === "topic" ? 2 : 0)
    .attr("cursor", "pointer")
    .attr("filter", d => d.type === "topic" && d.group === "hot" ? "url(#glow)" : null)
    .call(d3.drag()
      .on("start", dragStart)
      .on("drag", dragging)
      .on("end", dragEnd))
    .on("mouseover", onHover)
    .on("mouseout", onHoverOut)
    .on("click", onClick);
  nodeElements = nodeEnter.merge(nodeElements);
  nodeElements.transition().duration(500)
    .attr("r", d => d.radius || 8)
    .attr("fill", d => d.color || "#666")
    .attr("opacity", d => d.is_today === false ? (d.opacity || 0.4) : 1);

  labelElements = labelGroup.selectAll("text").data(nodes, d => d.id);
  labelElements.exit().transition().duration(300).attr("opacity", 0).remove();
  const labelEnter = labelElements.enter().append("text")
    .attr("text-anchor", "middle")
    .attr("dy", d => (d.radius || 8) + 14)
    .attr("fill", d => {{
      if (d.type === "topic") return "rgba(255,255,255,0.85)";
      if (d.type === "theme") return d.color || "rgba(200,200,255,0.6)";
      return "rgba(150,170,200,0.5)";
    }})
    .attr("font-size", d => {{
      if (d.type === "topic") return "12px";
      if (d.type === "theme") return "11px";
      return "10px";
    }})
    .attr("font-weight", d => d.type === "topic" ? "500" : "400")
    .attr("pointer-events", "none")
    .attr("opacity", 0)
    .text(d => {{
      if (d.type === "topic") return d.id.length > 14 ? d.id.slice(0, 14) + "…" : d.id;
      return d.id;
    }});
  labelElements = labelEnter.merge(labelElements);
  labelElements.transition().duration(500).attr("opacity", 1);

  simulation.nodes(nodes).on("tick", ticked);
  simulation.force("link").links(links);
  simulation.alpha(0.8).restart();
}}

function ticked() {{
  linkGroup.selectAll("line")
    .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
    .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
  nodeGroup.selectAll("circle")
    .attr("cx", d => d.x).attr("cy", d => d.y);
  labelGroup.selectAll("text")
    .attr("x", d => d.x).attr("y", d => d.y);
}}

function dragStart(event, d) {{
  if (!event.active) simulation.alphaTarget(0.3).restart();
  d.fx = d.x; d.fy = d.y;
}}
function dragging(event, d) {{ d.fx = event.x; d.fy = event.y; }}
function dragEnd(event, d) {{
  if (!event.active) simulation.alphaTarget(0);
  d.fx = null; d.fy = null;
}}

let highlightedNode = null;

function onHover(event, d) {{
  highlightedNode = d.id;
  const connected = new Set();
  connected.add(d.id);
  allLinks.forEach(l => {{
    const s = typeof l.source === "object" ? l.source.id : l.source;
    const t = typeof l.target === "object" ? l.target.id : l.target;
    if (s === d.id) connected.add(t);
    if (t === d.id) connected.add(s);
  }});

  nodeGroup.selectAll("circle").transition().duration(200)
    .attr("opacity", n => connected.has(n.id) ? 1 : 0.08);
  labelGroup.selectAll("text").transition().duration(200)
    .attr("opacity", n => connected.has(n.id) ? 1 : 0.05);
  linkGroup.selectAll("line").transition().duration(200)
    .attr("opacity", l => {{
      const s = typeof l.source === "object" ? l.source.id : l.source;
      const t = typeof l.target === "object" ? l.target.id : l.target;
      return (s === d.id || t === d.id) ? 0.7 : 0.03;
    }})
    .attr("stroke-width", l => {{
      const s = typeof l.source === "object" ? l.source.id : l.source;
      const t = typeof l.target === "object" ? l.target.id : l.target;
      return (s === d.id || t === d.id) ? 2.5 : 1;
    }})
    .attr("stroke", l => {{
      const s = typeof l.source === "object" ? l.source.id : l.source;
      const t = typeof l.target === "object" ? l.target.id : l.target;
      return (s === d.id || t === d.id) ? (d.color || "rgba(130,130,255,0.6)") : "rgba(130,130,255,0.1)";
    }});
}}

function onHoverOut(event, d) {{
  highlightedNode = null;
  nodeGroup.selectAll("circle").transition().duration(300).attr("opacity", 1);
  labelGroup.selectAll("text").transition().duration(300).attr("opacity", 1);
  linkGroup.selectAll("line").transition().duration(300)
    .attr("opacity", 1)
    .attr("stroke-width", l => l.type === "theme" ? 1.5 : 1)
    .attr("stroke", l => l.type === "theme" ? "rgba(130,130,255,0.2)" : "rgba(120,140,180,0.12)");
}}

function onClick(event, d) {{
  if (d.type !== "topic") return;
  const panel = document.getElementById("detail");
  const content = document.getElementById("detailContent");

  const appealBadge = a => a === "高" ? "🔴" : a === "中" ? "🟡" : "⚪";
  const groupLabel = {{ hot: "🔥 正在火", emerging: "⭐ 即将火", moderate: "👀 值得关注" }};

  let html = `
    <div class="score-badge" style="background:${{d.color}}33;color:${{d.color}}">${{d.score}}分 · ${{groupLabel[d.group] || ""}}</div>
    <h3>${{d.id}}</h3>
    <div class="meta">
      <span>${{d.direction}}</span>
      <span>${{d.category}}</span>
      <span>${{d.platforms?.join(" · ") || ""}}</span>
    </div>
    <div class="summary">${{d.summary || ""}}</div>
  `;

  if (d.themes?.length) {{
    html += `<div style="margin-bottom:10px">`;
    d.themes.forEach(t => {{ html += `<span class="theme-tag">${{t}}</span>`; }});
    html += `</div>`;
  }}

  if (d.angles?.length) {{
    html += `<div class="section-title">🎯 创作角度</div>`;
    d.angles.forEach(a => {{
      html += `<div class="angle-item">
        <div class="angle-name">${{appealBadge(a.appeal)}} ${{a.name}}</div>
        <div class="angle-meta">→ ${{a.platform}}</div>
      </div>`;
    }});
  }}

  if (d.first_platform) {{
    html += `<div class="rec">🚀 首发 <strong>${{d.first_platform}}</strong>`;
    if (d.trending_window) html += ` · ${{d.trending_window}}`;
    html += `</div>`;
  }}

  content.innerHTML = html;
  panel.classList.add("show");
}}

function closeDetail() {{ document.getElementById("detail").classList.remove("show"); }}

function toggleFilter(type) {{
  const btn = document.getElementById("btn" + type.charAt(0).toUpperCase() + type.slice(1));
  if (visibleTypes.has(type)) {{
    if (type === "topic") return;
    visibleTypes.delete(type);
    btn.classList.remove("active");
  }} else {{
    visibleTypes.add(type);
    btn.classList.add("active");
  }}
  render();
}}

function toggleCombos() {{
  const panel = document.getElementById("comboPanel");
  panel.classList.toggle("show");
}}

function resetView() {{
  svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity);
  simulation.alpha(0.5).restart();
}}

// --- Init ---
let statsText = `${{DATA.stats.total}} 个话题 · ${{DATA.stats.hot}} 正在火 · ${{DATA.stats.emerging}} 即将火 · ${{DATA.stats.moderate}} 值得关注`;
if (DATA.cumulative && DATA.stats.kb_topics) {{
  statsText += ` · 知识库 ${{DATA.stats.kb_topics}} 个历史话题`;
}}
document.getElementById("stats").textContent = statsText;

const categories = [...new Set(allNodes.filter(n => n.type === "topic").map(n => n.category))];
let legendHtml = categories.map(c =>
  `<div class="legend-item"><div class="legend-dot" style="background:${{CATEGORY_COLORS[c] || '#95a5a6'}}"></div>${{c}}</div>`
).join("");
legendHtml += `<div class="legend-item" style="margin-top:6px"><div class="legend-dot" style="background:rgba(130,130,255,0.5)"></div>主题关联</div>`;
legendHtml += `<div class="legend-item"><div class="legend-dot" style="background:#7c8db5"></div>平台</div>`;
document.getElementById("legend").innerHTML = legendHtml;

const CATEGORY_COLORS = ${{json.dumps(CATEGORY_COLORS, ensure_ascii=False)}};

const comboList = document.getElementById("comboList");
DATA.combos.forEach(c => {{
  comboList.innerHTML += `<div class="combo-item"><strong>${{c.label}}</strong><br>💡 ${{c.idea}}</div>`;
}});

render();

// Pulse animation for persistent topics (multi-day)
function animatePersistent() {{
  nodeGroup.selectAll("circle")
    .filter(d => d.is_persistent || d.days > 1)
    .each(function(d) {{
      const node = d3.select(this);
      const r = d.radius || 8;
      (function pulse() {{
        node.transition().duration(1500).attr("r", r * 1.15)
          .transition().duration(1500).attr("r", r)
          .on("end", pulse);
      }})();
    }});
}}
setTimeout(animatePersistent, 2000);

window.addEventListener("resize", () => {{
  const w = window.innerWidth, h = window.innerHeight;
  svg.attr("width", w).attr("height", h);
  simulation.force("center", d3.forceCenter(w / 2, h / 2));
  simulation.alpha(0.3).restart();
}});
</script>
</body>
</html>"""


def load_kb_graph(days: int = 0) -> dict:
    """Load graph data from knowledge base for cumulative mode."""
    kb_path = OUTPUT_DIR / "knowledge_base.json"
    if not kb_path.exists():
        return {"nodes": [], "links": []}

    sys.path.insert(0, str(Path(__file__).parent))
    from knowledge_base import load_kb, export_graph_data
    kb = load_kb()
    return export_graph_data(kb, days=days)


def merge_graph_data(today_data: dict, kb_data: dict) -> dict:
    """Merge today's detailed graph with KB cumulative graph, deduplicating."""
    today_ids = {n["id"] for n in today_data["nodes"]}
    merged_nodes = list(today_data["nodes"])
    merged_links = list(today_data["links"])

    for node in kb_data.get("nodes", []):
        if node["id"] not in today_ids:
            node["is_today"] = False
            node["opacity"] = 0.4
            merged_nodes.append(node)
            today_ids.add(node["id"])

    seen_links = {
        (
            (l["source"]["id"] if isinstance(l["source"], dict) else l["source"]),
            (l["target"]["id"] if isinstance(l["target"], dict) else l["target"]),
        )
        for l in merged_links
    }
    for link in kb_data.get("links", []):
        src = link["source"]["id"] if isinstance(link["source"], dict) else link["source"]
        tgt = link["target"]["id"] if isinstance(link["target"], dict) else link["target"]
        if (src, tgt) not in seen_links and src in today_ids and tgt in today_ids:
            link["is_historical"] = True
            merged_links.append(link)
            seen_links.add((src, tgt))

    today_data["nodes"] = merged_nodes
    today_data["links"] = merged_links
    today_data["cumulative"] = True
    today_data["stats"]["kb_topics"] = kb_data.get("meta", {}).get("total_topics", 0)
    return today_data


def main():
    parser = base_argparser("Generate graph visualization")
    parser.add_argument("--cumulative", action="store_true",
                        help="Include historical topics from knowledge base")
    parser.add_argument("--days", type=int, default=0,
                        help="Rolling window in days for cumulative mode (0 = all)")
    args = parser.parse_args()
    handle_schema(args, SCHEMA)

    input_data = read_json_input(args)
    trends = input_data.get("briefed_trends", [])

    if not trends:
        fail("No briefed_trends provided. Pipe output from content_brief.")

    date = today_str()
    output_path = args.output or f"hot-creator-mindmap-{date}.html"
    if output_path.endswith(".md"):
        output_path = output_path[:-3] + ".html"

    graph_data = build_graph_data(trends, date)

    if args.cumulative:
        kb_graph = load_kb_graph(days=args.days)
        graph_data = merge_graph_data(graph_data, kb_graph)
        mode_label = f"累积 {args.days}天" if args.days > 0 else "全量累积"
        print(f"[export_mindmap] Cumulative mode: {mode_label}", file=sys.stderr)

    html_content = wrap_html(graph_data, date)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"[export_mindmap] Saved to {output_path}", file=sys.stderr)
    print(json.dumps({"file": str(output_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
