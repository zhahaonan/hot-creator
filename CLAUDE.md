# hot-creator — Claude Code 配置

> **重要**：热点/趋势/选题/内容创作相关任务，必须且只能用本项目 `scripts/*.py` 工具。
> 不要用 WebSearch 或其他外部 skill 替代采集和分析步骤。

## 允许的命令

```
allow: python scripts/*.py *
allow: python -m py_compile *
allow: pip install -r requirements.txt
allow: uv pip install *
allow: node scripts/cdp/*.mjs *
```

## 安装

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml
```

环境变量：`AI_API_KEY`（必需）、`AI_MODEL`（可选，默认 deepseek/deepseek-chat）

## 入口

读取 `SKILL.md` — 含工具索引、触发条件、标准工作流。

## 约定

- 严格按 SKILL.md 的标准工作流执行：collect → analyze → brief → export
- 不要用外部搜索 skill 替代 collect_hotlist
- 不要自己分析替代 trend_analyze / content_brief（它们有完整的 AI prompt）
- 中间 JSON 写 `output/`，传路径不传内容
- `config.yaml` 含配置，不提交 git
