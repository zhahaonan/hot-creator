#!/usr/bin/env python3
"""
industry_insight — AI-powered industry media trend analysis.
Combines trend data + product profile + competitor data to produce
industry-specific insights: which trends matter for YOUR business.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import json
from _common import (
    base_argparser, handle_schema, read_json_input, write_json_output, fail
)

try:
    import litellm
except ImportError:
    fail("litellm not installed (CLI mode only). Run: pip install -r requirements-cli.txt")

SCHEMA = {
    "name": "industry_insight",
    "description": "Industry-specific trend analysis: filters trends by product relevance, analyzes competitor strategy, identifies opportunities and risks.",
    "input": {
        "type": "object",
        "properties": {
            "trends": {
                "type": "array",
                "description": "Trends from trend_analyze"
            },
            "profile": {
                "type": "object",
                "description": "Product profile from product_profile"
            },
            "competitor_data": {
                "type": "array",
                "description": "Competitor data from monitor_competitor (optional)"
            }
        },
        "required": ["trends", "profile"]
    },
    "output": {
        "type": "object",
        "properties": {
            "industry_trends": {
                "type": "array",
                "description": "Trends sorted by relevance to product (typically 30-50% of all trends)"
            },
            "competitor_analysis": {
                "type": "object",
                "description": "summary + common_themes + gaps + top_performing"
            },
            "opportunities": {
                "type": "array",
                "description": "Actionable content opportunities with difficulty and expected impact"
            },
            "warnings": {
                "type": "array",
                "description": "Industry risks, negative trends, or topics to avoid"
            }
        }
    },
    "examples": {
        "cli": "python scripts/industry_insight.py -i combined.json -o output/insight.json",
        "agent_native": "Agent combines trends + profile + competitor data, applies industry analysis reasoning"
    },
    "errors": {
        "no_profile": "缺少产品画像 → 先运行 product_profile",
        "no_trends": "缺少趋势数据 → 先运行 trend_analyze"
    }
}

SYSTEM_PROMPT = """你是一个资深的行业分析师和内容策略顾问。你擅长从全网热点中筛选出与特定行业/产品真正相关的趋势，并结合竞品动态给出精准的内容策略建议。

你的分析必须基于提供的数据，不编造数据或案例。"""

USER_PROMPT_TEMPLATE = """## 任务

基于以下数据，输出行业视角的媒体趋势洞察报告。

## 产品画像

{profile_json}

## 当前全网热点趋势

{trends_json}

## 竞品内容动态

{competitor_json}

## 请输出

返回严格 JSON 格式（不要 markdown 代码块包裹）：

{{
  "industry_trends": [
    {{
      "topic": "与该行业/产品相关的热点话题",
      "relevance_score": 90,
      "relevance_reason": "为什么和这个产品相关（一句话）",
      "original_score": 85,
      "direction": "rising",
      "category": "科技",
      "action": "建议的内容动作（追热点/蹭话题/深度解读/避险）",
      "urgency": "高/中/低"
    }}
  ],
  "competitor_analysis": {{
    "summary": "竞品内容策略总结（2-3句话）",
    "common_themes": ["竞品普遍在做的内容方向"],
    "gaps": ["竞品没做但有机会的方向"],
    "top_performing": ["竞品表现最好的内容类型/话题"]
  }},
  "opportunities": [
    {{
      "title": "内容机会名称",
      "description": "具体描述",
      "related_trend": "关联的热点话题",
      "difficulty": "高/中/低",
      "expected_impact": "高/中/低",
      "suggested_platforms": ["小红书", "公众号"]
    }}
  ],
  "warnings": [
    {{
      "title": "风险/负面趋势",
      "description": "具体描述",
      "suggestion": "应对建议"
    }}
  ]
}}

注意：
- industry_trends 只保留与该产品/行业有真实关联的热点（通常是全部热点的 30-50%），按 relevance_score 降序
- relevance_score 是"与该产品的相关度"（0-100），不是热度
- opportunities 要具体到可执行的内容方向，不要泛泛的"多做内容"
- 如果没有竞品数据，competitor_analysis 写"暂无竞品数据"即可
- warnings 关注行业负面舆情、政策风险、品牌风险等"""


def call_ai(system_prompt: str, user_prompt: str, model: str, api_key: str, api_base: str = None) -> str:
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 8000,
    }
    if api_key:
        kwargs["api_key"] = api_key
    if api_base:
        kwargs["api_base"] = api_base

    response = litellm.completion(**kwargs)
    return response.choices[0].message.content.strip()


def parse_ai_response(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)


def main():
    parser = base_argparser("Industry-specific trend analysis")
    parser.add_argument("--model", help="AI model (default: env AI_MODEL)")
    parser.add_argument("--api-key", help="AI API key (default: env AI_API_KEY)")
    parser.add_argument("--api-base", help="AI API base URL (default: env AI_API_BASE)")
    parser.add_argument("--profile", help="Path to product profile JSON (alternative to embedding in input JSON)")
    parser.add_argument("--competitors", help="Path to competitor data JSON (alternative to embedding in input JSON)")
    args = parser.parse_args()
    handle_schema(args, SCHEMA)

    model = args.model or os.environ.get("AI_MODEL", "deepseek/deepseek-chat")
    api_key = args.api_key or os.environ.get("AI_API_KEY", "")
    api_base = args.api_base or os.environ.get("AI_API_BASE", "")

    if not api_key:
        fail("AI_API_KEY not set.")

    input_data = read_json_input(args)
    trends = input_data.get("trends", [])
    profile = input_data.get("profile", {})
    competitor_data = input_data.get("competitor_data", [])

    if args.profile:
        with open(args.profile, "r", encoding="utf-8") as f:
            profile_file = json.load(f)
            profile = profile_file.get("profile", profile_file)

    if args.competitors:
        with open(args.competitors, "r", encoding="utf-8") as f:
            competitor_data = json.load(f)
            if isinstance(competitor_data, dict):
                competitor_data = competitor_data.get("competitors", competitor_data.get("competitor_data", []))

    if not trends:
        fail("No trends provided.")
    if not profile:
        fail("No product profile provided. Run product_profile first.")

    print(
        f"[industry_insight] Analyzing {len(trends)} trends for "
        f"{profile.get('name', 'Unknown')} ({profile.get('industry', '')})...",
        file=sys.stderr
    )

    profile_json = json.dumps(profile, ensure_ascii=False, indent=None)

    trends_summary = []
    for t in trends:
        trends_summary.append({
            "topic": t.get("topic", ""),
            "score": t.get("score", 0),
            "direction": t.get("direction", ""),
            "category": t.get("category", ""),
            "platforms": t.get("platforms", []),
            "summary": t.get("summary", "")
        })
    trends_json = json.dumps(trends_summary, ensure_ascii=False, indent=None)

    comp_summary = []
    for c in competitor_data:
        comp_summary.append({
            "name": c.get("name", ""),
            "platform": c.get("platform", ""),
            "recent_posts": [
                {"title": p.get("title", ""), "engagement": p.get("engagement", "")}
                for p in c.get("posts", [])[:5]
            ]
        })
    competitor_json = json.dumps(comp_summary, ensure_ascii=False) if comp_summary else json.dumps("暂无竞品数据", ensure_ascii=False)

    user_prompt = (
        USER_PROMPT_TEMPLATE
        .replace("{profile_json}", profile_json)
        .replace("{trends_json}", trends_json)
        .replace("{competitor_json}", competitor_json)
    )

    try:
        response_text = call_ai(SYSTEM_PROMPT, user_prompt, model, api_key, api_base or None)
        result = parse_ai_response(response_text)
    except json.JSONDecodeError as e:
        fail(f"Failed to parse AI response: {e}")
    except Exception as e:
        fail(f"AI call failed: {e}")

    it = result.get("industry_trends", [])
    opps = result.get("opportunities", [])
    print(
        f"[industry_insight] Found {len(it)} relevant trends, {len(opps)} opportunities",
        file=sys.stderr
    )

    write_json_output(result, args)


if __name__ == "__main__":
    main()
