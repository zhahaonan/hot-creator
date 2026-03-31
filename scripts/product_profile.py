#!/usr/bin/env python3
"""
product_profile — Parse user's product info into a structured profile.
Accepts text description (stdin/--input) or file path (--file) for PDF/MD/TXT docs.
Uses AI to extract structured product profile for downstream tools.
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
    fail("litellm not installed (CLI mode only). Run: pip install -r requirements-cli.txt")

SCHEMA = {
    "name": "product_profile",
    "description": "Parse product info (text or file) into structured profile. Agent-native: Agent extracts profile directly from user dialogue.",
    "input": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Free-text product description from user"
            },
            "file": {
                "type": "string",
                "description": "Path to product document (PDF/MD/TXT/DOCX)"
            },
            "competitors": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Known competitor names or account IDs (optional)"
            }
        }
    },
    "output": {
        "type": "object",
        "properties": {
            "profile": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "category": {"type": "string"},
                    "one_liner": {"type": "string"},
                    "target_audience": {"type": "array", "items": {"type": "string"}},
                    "usps": {"type": "array", "items": {"type": "string"}},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                    "industry": {"type": "string"},
                    "tone": {"type": "string"},
                    "competitors": {"type": "array", "items": {"type": "string"}},
                    "content_goals": {"type": "array", "items": {"type": "string"}}
                }
            }
        }
    },
    "examples": {
        "cli_text": "python scripts/product_profile.py --text '我们是一个AI写作助手...' -o profile.json",
        "cli_file": "python scripts/product_profile.py --file product.pdf --competitors '竞品A,竞品B' -o profile.json",
        "agent_native": "Agent extracts profile fields from user's product description in dialogue"
    },
    "errors": {
        "no_input": "未提供产品信息 → 用 --text 或 --file",
        "file_not_found": "文件不存在 → 检查路径",
        "pdf_parse_failed": "PDF 解析失败 → 需安装 PyMuPDF 或 PyPDF2"
    }
}

PROFILE_PROMPT_SYSTEM = """你是一个资深的品牌策略师和内容营销专家。你的任务是从用户提供的产品资料中提取结构化的产品画像，供后续内容创作使用。提取要精准、不编造信息。如果某个字段从资料中无法确定，用合理推断并标注"(推断)"。"""

PROFILE_PROMPT_USER = """请从以下产品资料中提取结构化的产品画像。

## 产品资料

{product_text}

## 输出要求

返回严格 JSON 格式（不要 markdown 代码块包裹）：

{{
  "profile": {{
    "name": "产品/品牌名称",
    "category": "产品类别（如：护肤品、SaaS工具、餐饮、教育等）",
    "one_liner": "一句话产品描述（不超过30字）",
    "target_audience": ["目标人群1", "目标人群2", "目标人群3"],
    "usps": ["核心卖点1", "核心卖点2", "核心卖点3"],
    "keywords": ["内容关键词1", "关键词2", "关键词3", "关键词4", "关键词5"],
    "industry": "所在行业",
    "tone": "品牌调性（如：专业严谨、轻松活泼、高端奢华、亲民实用等）",
    "competitors": ["竞品1", "竞品2"],
    "content_goals": ["内容营销目标1", "目标2"]
  }}
}}

注意：
- keywords 要包含用户可能搜索的词、行业术语、产品功能相关词
- target_audience 要具体（不要"所有人"），按优先级排列
- usps 提取真实的差异化卖点，不要泛泛而谈
- competitors 如果资料中未提及，根据产品类别推断2-3个主要竞品并标注(推断)
- content_goals 根据产品阶段和类型推断合理的内容营销目标"""


def read_product_file(file_path: str) -> str:
    """Read product document from file."""
    p = Path(file_path)
    if not p.exists():
        fail(f"File not found: {file_path}")

    suffix = p.suffix.lower()

    if suffix in (".txt", ".md", ".markdown"):
        return p.read_text(encoding="utf-8")

    if suffix == ".pdf":
        try:
            import subprocess
            result = subprocess.run(
                ["python", "-c", f"""
import sys
try:
    import fitz
    doc = fitz.open("{file_path}")
    text = ""
    for page in doc:
        text += page.get_text()
    print(text)
except ImportError:
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader("{file_path}")
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        print(text)
    except ImportError:
        print("PDF_PARSE_ERROR", file=sys.stderr)
        sys.exit(1)
"""],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
        return p.read_text(encoding="utf-8", errors="ignore")

    if suffix in (".docx",):
        try:
            import subprocess
            result = subprocess.run(
                ["python", "-c", f"""
from docx import Document
doc = Document("{file_path}")
text = "\\n".join(p.text for p in doc.paragraphs)
print(text)
"""],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

    return p.read_text(encoding="utf-8", errors="ignore")


def call_ai(system_prompt: str, user_prompt: str, model: str, api_key: str, api_base: str = None) -> str:
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 4000,
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
    parser = base_argparser("Parse product info into structured profile")
    parser.add_argument("--file", "-f", help="Path to product document (PDF/MD/TXT/DOCX)")
    parser.add_argument("--text", "-t", help="Product description text")
    parser.add_argument("--competitors", help="Comma-separated competitor names")
    parser.add_argument("--model", help="AI model (default: env AI_MODEL)")
    parser.add_argument("--api-key", help="AI API key (default: env AI_API_KEY)")
    parser.add_argument("--api-base", help="AI API base URL (default: env AI_API_BASE)")
    args = parser.parse_args()
    handle_schema(args, SCHEMA)

    model = args.model or os.environ.get("AI_MODEL", "deepseek/deepseek-chat")
    api_key = args.api_key or os.environ.get("AI_API_KEY", "")
    api_base = args.api_base or os.environ.get("AI_API_BASE", "")

    if not api_key:
        fail("AI_API_KEY not set. Export it or pass --api-key.")

    product_text = ""

    input_data = {}
    if args.file:
        print(f"[product_profile] Reading file: {args.file}", file=sys.stderr)
        product_text = read_product_file(args.file)
    elif args.text:
        product_text = args.text
    else:
        input_data = read_json_input(args)
        product_text = input_data.get("text", "")
        if not product_text and input_data.get("file"):
            product_text = read_product_file(input_data["file"])

    if not product_text:
        fail("No product info provided. Use --text, --file, or pipe JSON with 'text' field.")

    if len(product_text) > 10000:
        product_text = product_text[:10000] + "\n\n[...truncated...]"

    competitors_list = []
    if args.competitors:
        competitors_list = [c.strip() for c in args.competitors.split(",")]
    elif isinstance(input_data.get("competitors"), list):
        competitors_list = input_data["competitors"]

    if competitors_list:
        product_text += f"\n\n已知竞品：{', '.join(competitors_list)}"

    print(f"[product_profile] Extracting profile with {model}...", file=sys.stderr)

    user_prompt = PROFILE_PROMPT_USER.replace("{product_text}", product_text)

    try:
        response_text = call_ai(PROFILE_PROMPT_SYSTEM, user_prompt, model, api_key, api_base or None)
        result = parse_ai_response(response_text)
    except json.JSONDecodeError as e:
        fail(f"Failed to parse AI response: {e}")
    except Exception as e:
        fail(f"AI call failed: {e}")

    if "profile" not in result:
        result = {"profile": result}

    print(f"[product_profile] Profile extracted: {result['profile'].get('name', 'Unknown')}", file=sys.stderr)

    write_json_output(result, args)


if __name__ == "__main__":
    main()
