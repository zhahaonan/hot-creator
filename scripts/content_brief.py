#!/usr/bin/env python3
"""
content_brief — AI-powered creative brief generation for content creators.
Takes trend analysis output, generates full creative briefs per topic.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import json
from pathlib import Path
from _common import (
    base_argparser, handle_schema, read_json_input, write_json_output,
    fail, SKILL_ROOT
)

try:
    import litellm
except ImportError:
    fail("litellm not installed. Run: pip install litellm")

SCHEMA = {
    "name": "content_brief",
    "description": "Generate creative briefs per trend topic. Pass --profile for product x trend mode. CLI needs AI_API_KEY; Agent-native: Agent generates briefs directly.",
    "input": {
        "type": "object",
        "properties": {
            "trends": {
                "type": "array",
                "description": "Trends from trend_analyze output",
                "items": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                        "score": {"type": "integer"},
                        "direction": {"type": "string"},
                        "category": {"type": "string"},
                        "platforms": {"type": "array"},
                        "summary": {"type": "string"}
                    },
                    "required": ["topic"]
                }
            },
            "profile": {
                "type": "object",
                "description": "Product profile (optional — enables product x trend mode with tailored content ideas)"
            }
        },
        "required": ["trends"]
    },
    "output": {
        "type": "object",
        "properties": {
            "briefed_trends": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                        "score": {"type": "integer"},
                        "brief": {"type": "object", "description": "Full creative brief — see data-contracts.md for structure"}
                    }
                }
            }
        }
    },
    "examples": {
        "cli_generic": "python scripts/content_brief.py -i trends.json --top 15 -o output/briefs.json",
        "cli_product": "python scripts/content_brief.py -i trends.json --profile profile.json --top 10 -o briefs.json",
        "agent_native": "Agent reads trends JSON + prompt-templates.md#content_brief, generates briefs in dialogue"
    },
    "errors": {
        "no_api_key": "AI_API_KEY 未设置 → Agent 原生模式不需要",
        "no_trends": "无 trends 输入 → 先运行 trend_analyze",
        "batch_error": "单个 batch AI 调用失败 → 该 batch 话题标记 error，继续处理其他 batch"
    }
}


def load_brief_prompt() -> tuple[str, str]:
    """Load content_brief prompts from reference/prompt-templates.md."""
    tmpl_path = SKILL_ROOT / "reference" / "prompt-templates.md"

    default_sys = "你是一个全平台内容策划专家，服务过大量头部创作者。你的建议实操性强，不说空话。"
    default_user = "请为以下热点话题生成完整创作简报，返回 JSON 格式。\n\n{trends_json}"

    if not tmpl_path.exists():
        return default_sys, default_user

    content = tmpl_path.read_text(encoding="utf-8")

    sys_prompt = ""
    user_prompt = ""

    in_section = False
    in_code = False
    code_lines = []
    last_heading = ""

    for line in content.split("\n"):
        if not in_code:
            if line.startswith("## ") and "content_brief" in line:
                in_section = True
                continue
            if in_section and line.startswith("## ") and "content_brief" not in line:
                break

        if in_section:
            if not in_code and "### " in line:
                last_heading = line.strip().lower()
                continue

            if line.strip().startswith("```") and not in_code:
                in_code = True
                code_lines = []
                continue
            elif line.strip().startswith("```") and in_code:
                in_code = False
                block = "\n".join(code_lines)
                if "system" in last_heading and block.strip():
                    sys_prompt = block
                elif "{trends_json}" in block:
                    user_prompt = block
                continue
            if in_code:
                code_lines.append(line)

    if not sys_prompt:
        sys_prompt = default_sys
    if not user_prompt:
        user_prompt = default_user

    return sys_prompt, user_prompt


def call_ai(system_prompt: str, user_prompt: str, model: str, api_key: str, api_base: str = None) -> str:
    """Call AI model via litellm."""
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.5,
        "max_tokens": 16000,
    }
    if api_key:
        kwargs["api_key"] = api_key
    if api_base:
        kwargs["api_base"] = api_base

    response = litellm.completion(**kwargs)
    return response.choices[0].message.content.strip()


def _try_fix_truncated_json(text: str) -> dict | None:
    """Attempt to fix truncated JSON by closing open brackets/braces."""
    import re
    for trim in range(min(200, len(text)), 0, -1):
        candidate = text[:len(text) - trim + 1]
        last_bracket = max(candidate.rfind('}'), candidate.rfind(']'))
        if last_bracket < 0:
            continue
        candidate = candidate[:last_bracket + 1]
        opens = candidate.count('{') - candidate.count('}')
        open_arr = candidate.count('[') - candidate.count(']')
        candidate += ']' * open_arr + '}' * opens
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def parse_ai_response(text: str) -> dict:
    """Parse AI response, handling markdown code fences, truncation, and various key names."""
    import re
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)

    result = None
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            try:
                result = json.loads(match.group())
            except json.JSONDecodeError:
                result = _try_fix_truncated_json(match.group())
        if result is None:
            result = _try_fix_truncated_json(cleaned)
        if result is None:
            raise json.JSONDecodeError("Cannot parse AI response after all fallbacks", cleaned, 0)

    if isinstance(result, dict) and "briefed_trends" not in result:
        for key in ("briefs", "creation_briefs", "trends", "data", "results", "content_briefs"):
            if key in result and isinstance(result[key], list):
                result["briefed_trends"] = result.pop(key)
                break
        if "briefed_trends" not in result:
            for key, val in result.items():
                if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
                    if "topic" in val[0] or "brief" in val[0]:
                        result["briefed_trends"] = result.pop(key)
                        break

    return result


PRODUCT_BRIEF_SYSTEM = """你是一个全平台内容策划专家，擅长将产品营销与热点趋势结合。你的每一条建议都必须紧密围绕用户的真实产品，不编造产品功能或特性。所有内容创意都要自然融合产品卖点和热点话题，避免生硬植入。"""

PRODUCT_BRIEF_USER = """## 任务

基于以下产品信息和热点趋势，为每个热点生成"产品 x 热点"的深度内容方案。

## 我的产品

{profile_json}

## 热点趋势

{trends_json}

## 输出要求

为每个热点话题输出以下内容，必须与产品深度结合：

1. **产品结合点**：这个热点如何与我的产品产生关联（必须真实、自然，不能硬蹭）
2. **创作角度** (3-5个)：每个角度都要融入产品，说明产品在这个角度中扮演的角色
3. **内容大纲**：短视频/图文/长文 大纲中要自然植入产品
4. **标题建议** (5个)：可以含产品名或暗示产品，适配各平台
5. **关键素材**：产品相关的可引用事实 + 热点相关素材
6. **对标案例**：类似"品牌蹭热点"的成功案例
7. **风险提示**：这个热点和产品结合有什么需要注意的（比如敏感话题不要蹭）

返回严格 JSON（不要 markdown 代码块）：

{{
  "briefed_trends": [
    {{
      "topic": "热点话题",
      "score": 95,
      "direction": "rising",
      "category": "科技",
      "platforms": ["微博"],
      "summary": "概要",
      "product_relevance": "high/medium/low",
      "brief": {{
        "product_tie_in": "产品与热点的结合点描述",
        "angles": [
          {{
            "name": "角度名称",
            "description": "切入点描述（含产品角色）",
            "product_role": "产品在此角度中的定位",
            "best_platform": "抖音",
            "appeal": "高"
          }}
        ],
        "outlines": {{
          "short_video": {{
            "hook": "开头hook（可含产品）",
            "points": ["内容点（融合产品）"],
            "cta": "引导关注/购买/了解"
          }},
          "xiaohongshu": {{
            "cover_title": "封面标题",
            "key_points": ["要点"],
            "hashtags": ["#话题"]
          }},
          "article": {{
            "title": "标题",
            "intro": "引言",
            "sections": ["章节"],
            "conclusion": "结语（含产品）"
          }}
        }},
        "materials": ["素材"],
        "titles": {{
          "douyin": "抖音标题",
          "xiaohongshu": "小红书标题",
          "gongzhonghao": "公众号标题",
          "zhihu": "知乎标题",
          "bilibili": "B站标题"
        }},
        "benchmarks": [
          {{
            "platform": "平台",
            "brand": "品牌名",
            "topic": "蹭的热点",
            "metrics": "数据",
            "reason": "成功原因"
          }}
        ],
        "recommendation": {{
          "best_format": "推荐形式",
          "best_time": "最佳时间",
          "platform_priority": ["平台排序"]
        }},
        "risk_notes": "注意事项/风险提示"
      }}
    }}
  ]
}}

关键原则：
- product_relevance 为 low 的话题也要输出，但标注让用户自行判断是否要做
- product_tie_in 必须真实，不能编造产品没有的功能
- 宁可说"这个热点与产品的直接关联较弱，建议从行业视角切入"也不要硬编"""


def process_batch(trends: list[dict], model: str, api_key: str, api_base: str = None,
                  batch_size: int = 5, profile: dict = None) -> list[dict]:
    """Process trends in batches. If profile is provided, generates product x trend briefs."""
    if profile:
        sys_prompt = PRODUCT_BRIEF_SYSTEM
        user_template = PRODUCT_BRIEF_USER
    else:
        sys_prompt, user_template = load_brief_prompt()

    all_briefed = []

    for i in range(0, len(trends), batch_size):
        batch = trends[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(trends) + batch_size - 1) // batch_size

        mode_label = "product x trend" if profile else "generic"
        print(
            f"[content_brief] Batch {batch_num}/{total_batches} "
            f"({len(batch)} topics, {mode_label})...",
            file=sys.stderr
        )

        trends_json = json.dumps(batch, ensure_ascii=False, indent=None)

        if profile:
            profile_json = json.dumps(profile, ensure_ascii=False, indent=None)
            user_prompt = (
                user_template
                .replace("{trends_json}", trends_json)
                .replace("{profile_json}", profile_json)
            )
        else:
            user_prompt = user_template.replace("{trends_json}", trends_json)

        try:
            response_text = call_ai(sys_prompt, user_prompt, model, api_key, api_base)
            result = parse_ai_response(response_text)

            briefed = result.get("briefed_trends", result if isinstance(result, list) else [])
            if isinstance(briefed, list):
                all_briefed.extend(briefed)
            else:
                all_briefed.append(briefed)
        except Exception as e:
            print(f"[content_brief] Batch {batch_num} error: {e}", file=sys.stderr)
            for trend in batch:
                all_briefed.append({
                    **trend,
                    "brief": {"error": str(e)}
                })

    return all_briefed


def main():
    parser = base_argparser("Generate creative briefs for trending topics")
    parser.add_argument("--model", help="AI model (default: env AI_MODEL or deepseek/deepseek-chat)")
    parser.add_argument("--api-key", help="AI API key (default: env AI_API_KEY)")
    parser.add_argument("--api-base", help="AI API base URL (default: env AI_API_BASE)")
    parser.add_argument("--top", type=int, default=0, help="Only process top N trends (0=all)")
    parser.add_argument("--batch-size", type=int, default=2, help="Topics per AI call (default: 2)")
    parser.add_argument("--profile", help="Path to product profile JSON (enables product x trend mode)")
    args = parser.parse_args()
    handle_schema(args, SCHEMA)

    model = args.model or os.environ.get("AI_MODEL", "deepseek/deepseek-chat")
    api_key = args.api_key or os.environ.get("AI_API_KEY", "")
    api_base = args.api_base or os.environ.get("AI_API_BASE", "")

    if not api_key:
        fail("AI_API_KEY not set. Export it or pass --api-key.")

    input_data = read_json_input(args)
    trends = input_data.get("trends", [])

    if not trends:
        fail("No trends provided. Pipe output from trend_analyze.")

    profile = input_data.get("profile", None)
    if args.profile:
        with open(args.profile, "r", encoding="utf-8") as f:
            profile_data = json.load(f)
            profile = profile_data.get("profile", profile_data)

    if args.top > 0:
        trends = trends[:args.top]

    mode = "product x trend" if profile else "generic"
    print(f"[content_brief] Mode: {mode} | {len(trends)} topics | {model}", file=sys.stderr)
    if profile:
        print(f"[content_brief] Product: {profile.get('name', 'Unknown')}", file=sys.stderr)

    briefed = process_batch(trends, model, api_key, api_base or None, args.batch_size, profile)

    result = {"briefed_trends": briefed}

    print(f"[content_brief] Generated {len(briefed)} briefs", file=sys.stderr)

    write_json_output(result, args)


if __name__ == "__main__":
    main()
