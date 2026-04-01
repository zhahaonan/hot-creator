# hot-creator — Claude Code 配置

> **重要**：热点/趋势/选题/内容创作任务，只能用本项目 `scripts/*.py` 工具。

## 允许的命令

```
allow: python scripts/*.py *
allow: python -m py_compile *
allow: pip install -r requirements.txt
allow: uv pip install *
```

## 安装

```bash
pip install -r requirements.txt
```

**不需要配置 AI_API_KEY。**

## 入口

读取 `SKILL.md` — 含完整的分步执行流程和 JSON 输出结构。

## 核心要求

1. **先获取产品信息**，再执行 Pipeline
2. **Agent 自己做趋势分析和内容方案**（不调 trend_analyze.py / content_brief.py）
3. **内容方案必须完整**：完整短视频脚本、完整小红书图文、完整长文大纲、完整素材清单、每平台标题。不是建议、不是方向——是拿来就能用的内容
4. **3 个导出脚本全部执行**：export_obsidian（.md 文档）、export_excel（.xlsx 报表）、export_mindmap（HTML 思维导图）。不能跳过任何一个

## 约定

- 采集用 Task 子智能体，只取回文件路径
- 中间 JSON 写 `output/`，传路径不传内容
