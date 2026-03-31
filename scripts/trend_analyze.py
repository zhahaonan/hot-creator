#!/usr/bin/env python3
"""
trend_analyze — AI-powered trend scoring, classification, and deduplication.
Takes merged hotlist/RSS/social data, outputs scored & categorized trends.
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
    "name": "trend_analyze",
    "description": "AI trend scoring, classification, and cross-platform deduplication. CLI mode needs AI_API_KEY; Agent-native mode: Agent does analysis directly.",
    "input": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "description": "Merged items from all collect tools (title + platform + rank minimum)",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "platform": {"type": "string"},
                        "rank": {"type": "integer"}
                    },
                    "required": ["title", "platform"]
                }
            }
        },
        "required": ["items"]
    },
    "output": {
        "type": "object",
        "properties": {
            "trends": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                        "score": {"type": "integer", "minimum": 0, "maximum": 100},
                        "direction": {"type": "string", "enum": ["rising", "peak", "declining", "emerging"]},
                        "category": {"type": "string"},
                        "platforms": {"type": "array", "items": {"type": "string"}},
                        "platform_count": {"type": "integer"},
                        "summary": {"type": "string"},
                        "is_emerging": {"type": "boolean"}
                    }
                }
            }
        }
    },
    "examples": {
        "cli": "python scripts/trend_analyze.py -i merged.json -o output/trends.json",
        "agent_native": "Agent reads merged.json, applies prompt-templates.md#trend_analyze rules, outputs trends JSON"
    },
    "errors": {
        "no_api_key": "AI_API_KEY 未设置 → Agent 原生模式不需要，CLI 需要 .env 配置",
        "ai_parse_error": "AI 返回非 JSON → 重试或换模型",
        "empty_input": "无 items → 先运行 collect_* 采集数据"
    }
}


def load_prompt_template() -> tuple[str, str]:
    """Load system and user prompts from reference/prompt-templates.md."""
    tmpl_path = SKILL_ROOT / "reference" / "prompt-templates.md"
    if not tmpl_path.exists():
        return (
            "你是一个资深的全网媒体趋势分析师。",
            "请分析以下热点数据，输出 JSON 格式的趋势评分结果。\n\n{items_json}"
        )

    content = tmpl_path.read_text(encoding="utf-8")

    sys_prompt = ""
    user_prompt = ""

    in_section = False
    in_code = False
    code_lines = []
    last_heading = ""

    for line in content.split("\n"):
        if not in_code:
            if line.startswith("## ") and "trend_analyze" in line:
                in_section = True
                continue
            if in_section and line.startswith("## ") and "trend_analyze" not in line:
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
                elif "{items_json}" in block:
                    user_prompt = block
                continue
            if in_code:
                code_lines.append(line)

    if not sys_prompt:
        sys_prompt = "你是一个资深的全网媒体趋势分析师，擅长从海量信息中识别真正有价值的热点趋势。"
    if not user_prompt:
        user_prompt = "请分析以下热点数据并输出JSON趋势评分。\n\n{items_json}"

    return sys_prompt, user_prompt


def call_ai(system_prompt: str, user_prompt: str, model: str, api_key: str, api_base: str = None) -> str:
    """Call AI model via litellm."""
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
    """Parse AI response, handling possible markdown code fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]  # remove opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)

    return json.loads(cleaned)


def main():
    parser = base_argparser("AI trend scoring and classification")
    parser.add_argument("--model", help="AI model (default: env AI_MODEL or deepseek/deepseek-chat)")
    parser.add_argument("--api-key", help="AI API key (default: env AI_API_KEY)")
    parser.add_argument("--api-base", help="AI API base URL (default: env AI_API_BASE)")
    args = parser.parse_args()
    handle_schema(args, SCHEMA)

    model = args.model or os.environ.get("AI_MODEL", "deepseek/deepseek-chat")
    api_key = args.api_key or os.environ.get("AI_API_KEY", "")
    api_base = args.api_base or os.environ.get("AI_API_BASE", "")

    if not api_key:
        fail("AI_API_KEY not set. Export it or pass --api-key.")

    input_data = read_json_input(args)
    items = input_data.get("items", [])

    if not items:
        fail("No items provided. Pipe output from collect tools.")

    print(f"[trend_analyze] Analyzing {len(items)} items with {model}...", file=sys.stderr)

    sys_prompt, user_template = load_prompt_template()

    items_summary = []
    for item in items:
        entry = {
            "title": item.get("title", ""),
            "platform": item.get("platform", ""),
            "rank": item.get("rank", 0),
        }
        if item.get("heat"):
            entry["heat"] = item["heat"]
        items_summary.append(entry)

    items_json = json.dumps(items_summary, ensure_ascii=False, indent=None)
    user_prompt = user_template.replace("{items_json}", items_json)

    try:
        response_text = call_ai(sys_prompt, user_prompt, model, api_key, api_base or None)
        result = parse_ai_response(response_text)
    except json.JSONDecodeError as e:
        fail(f"Failed to parse AI response as JSON: {e}")
    except Exception as e:
        fail(f"AI call failed: {e}")

    if "trends" not in result:
        result = {"trends": result if isinstance(result, list) else []}

    result["trends"].sort(key=lambda t: t.get("score", 0), reverse=True)

    print(f"[trend_analyze] Found {len(result['trends'])} trends", file=sys.stderr)

    write_json_output(result, args)


if __name__ == "__main__":
    main()
