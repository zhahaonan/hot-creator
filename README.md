# hot-creator

**内容创作者的热点情报助手** — AI Agent Skill for content creators.

扫描全网热点趋势，AI 评分预测走向，生成完整的内容创作简报。输出 Excel 报表、Obsidian 笔记、Markmap 思维导图。

## Architecture / 架构

遵循 [Harness 工程](https://docs.anthropic.com/) 五维度设计：

```
┌─────────────────────────────────────────────────────────────────┐
│  SKILL.md (~80 行, 渐进式披露入口)                               │
│  ├─ 触发条件 + 工具索引                                          │
│  ├─ 编排选择器 → reference/orchestration.md                      │
│  ├─ 上下文预算 → reference/context-budget.md                     │
│  └─ 知识按需加载表 → reference/*.md + site-patterns/*.md         │
├─────────────────────────────────────────────────────────────────┤
│  13 原子工具 (scripts/)                                          │
│  ├─ 采集层: collect_hotlist / collect_rss / collect_social       │
│  ├─ 分析层: trend_analyze / content_brief / industry_insight     │
│  ├─ 画像层: product_profile / monitor_competitor                 │
│  └─ 输出层: export_excel / export_obsidian / export_mindmap      │
├─────────────────────────────────────────────────────────────────┤
│  多智能体编排                                                     │
│  ├─ Fan-out/Fan-in: 并行采集                                     │
│  ├─ Pipeline: 分析 → 简报 → 输出                                 │
│  ├─ Expert Pool: 产品/竞品/行业专项分析                           │
│  └─ Hierarchical: 完整情报全流程                                  │
├─────────────────────────────────────────────────────────────────┤
│  上下文管理                                                       │
│  ├─ 子智能体隔离: 采集数据不进主上下文                             │
│  ├─ 数据压缩: 流水线中间产物落盘                                  │
│  └─ 知识延迟加载: reference 文件按需读取                           │
└─────────────────────────────────────────────────────────────────┘
```

## Features / 特性

- **Atomic & Composable** — 13 独立工具，JSON stdin/stdout，自由组合
- **Self-Describing** — 每个工具支持 `--help` / `--schema` / `--version`
- **Progressive Disclosure** — SKILL.md 只有 ~80 行，reference 按需加载
- **Multi-Agent Ready** — 内置 Fan-out/Fan-in、Pipeline、Expert Pool 编排策略
- **Context-Aware** — 三层压缩策略（子智能体隔离 + 数据压缩 + 知识延迟加载）
- **Dual Mode** — Agent 原生模式（无需 AI API）+ 独立 CLI 模式
- **Full Creative Briefs** — 创作角度、大纲（视频/图文/长文）、标题矩阵、对标案例、发布策略
- **Structured Output** — Excel (4 Sheet) + Obsidian (Topics 按类别 + Copywriting 按平台) + 力导向图谱
- **Product Integration** — 产品画像 x 热点结合，竞品监控，行业洞察
- **Built-in CDP** — 内置浏览器引擎，抓取小红书/抖音/微博动态页面

## Quick Start / 快速开始

### As AI Agent Skill（推荐，3 秒安装）

**OpenClaw 小龙虾：**
```bash
openclaw skills add https://github.com/zhahaonan/hot-creator
```

**Cursor / Claude Code / Cline / Windsurf / 其他 Agent 工具：**
```bash
git clone https://github.com/zhahaonan/hot-creator.git
cd hot-creator
pip install -r requirements.txt
cp .env.example .env   # 填入你的 AI API Key
```

> 有 `uv` 的话更快：`uv pip install -r requirements.txt`

装好后对 Agent 说：

```
"帮我看看现在什么热点最火，生成一份内容创作简报"
```

Agent 自动读取 `SKILL.md`，严格按内置工作流执行：采集 → AI 分析 → 创作简报 → 多格式输出。

### Standalone CLI（独立命令行）

```bash
# 一键全流程
python scripts/start_my_day.py

# 或逐步执行
python scripts/collect_hotlist.py --platforms weibo,douyin,zhihu -o output/hotlist.json
python scripts/trend_analyze.py -i output/hotlist.json -o output/trends.json
python scripts/content_brief.py -i output/trends.json --top 10 -o output/briefs.json
python scripts/export_excel.py -i output/briefs.json --xlsx output/report.xlsx
```

## Tools / 工具

| Tool | Description | Deps | Mode |
|------|-------------|------|------|
| **collect_hotlist** | 全网热榜采集（公共 API） | requests | Core |
| **collect_rss** | RSS 订阅采集 | feedparser | Core |
| **collect_social** | 社媒实时数据（小红书/抖音/微博） | CDP | Core |
| **monitor_competitor** | 竞品内容监控 | CDP | Core |
| **trend_analyze** | AI 趋势评分与分类 | litellm | CLI |
| **content_brief** | AI 内容创作简报（支持产品模式） | litellm | CLI |
| **product_profile** | 产品资料 → 结构化画像 | litellm | CLI |
| **industry_insight** | 行业趋势洞察 | litellm | CLI |
| **knowledge_base** | 累积知识库（追加/搜索/图谱） | — | Core |
| **export_excel** | Excel 报表（4 Sheet） | openpyxl | Core |
| **export_obsidian** | Obsidian（Topics 按类别 + Copywriting 按平台） | — | Core |
| **export_mindmap** | 力导向关系图谱 | — | Core |
| **start_my_day** | 一键编排器 | — | Core |

> **Core** = `requirements.txt` 即可 · **CLI** = 额外需要 `requirements-cli.txt`（litellm）
> 作为 Skill 时，CLI 模式的工具由 Agent 自身完成 AI 分析，不需要 litellm

```bash
# Tool self-description
python scripts/collect_hotlist.py --help    # Usage
python scripts/collect_hotlist.py --schema  # JSON Schema
python scripts/collect_hotlist.py --version # Version
```

## Harness Design Principles / 设计原则

### 1. Implement Tools — 工具原子性

每个脚本只做一件事。`--schema` 输出完整的 input/output/examples/errors 合约。工具之间通过 JSON 管道组合。

### 2. Curate Knowledge — 知识渐进式披露

SKILL.md 是唯一的入口，只有 ~80 行。8 个 reference 文件按需加载，避免浪费上下文。

### 3. Manage Context — 三层上下文管理

- **子智能体隔离**：采集数据在子智能体中完成，不进主上下文
- **数据压缩**：中间产物落盘（`output/`），只传递文件路径
- **知识延迟加载**：prompt-templates 分段锚点，只读需要的 section

### 4. Coordinate Agents — 多智能体编排

支持 6 种架构模式：Fan-out/Fan-in、Pipeline、Expert Pool、Producer-Reviewer、Supervisor、Hierarchical Delegation。

### 5. Error Contracts — 结构化错误

每个工具的 SCHEMA 包含 `errors` 字段，定义可能的错误类型和解决方案。`_common.py` 提供 `structured_error()` 和 `_error_hint()` 自动生成可操作的错误提示。

## Supported Platforms / 支持平台

**Hotlist (API):** 微博, 抖音, 知乎, 百度, 头条, B站, 36氪, IT之家, 澎湃新闻, 财联社

**Social (CDP):** 小红书, 抖音实时, 微博上升趋势

**RSS:** Configurable — defaults include 36氪, Hacker News, 少数派

## Requirements / 依赖

- Python >= 3.10
- Node.js >= 22 (CDP only)
- Chrome (CDP only)

## License / 许可

MIT — See [LICENSE](LICENSE) for details.

CDP browser engine adapted from [web-access](https://github.com/eze-is/web-access) (MIT License).
