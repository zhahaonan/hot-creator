---
name: hot-creator
version: "3.1.0"
license: MIT
description: 内容创作者热点情报 Harness — 从全网采集到 AI 创作简报的完整操作环境
harness:
  tools: 13 atomic scripts (JSON pipe, --schema self-describing)
  knowledge: reference/*.md (on-demand) + SOP/*.md (deep-dive)
  observation: collect_* + knowledge_base --query + WebSearch
  action: analyze + brief + export_* + start_my_day
  permissions: AI_API_KEY (CLI only) + CDP (optional)
---

# hot-creator

> **Harness 定位**：模型决定做什么，hot-creator 负责执行怎么做。
> 本 Skill 不试图编程智能，而是为 Agent 提供热点情报领域的完整操作环境。

## 触发条件

用户意图涉及：热点、趋势、选题、内容创作、热搜、爆款、创作灵感、竞品分析、行业洞察、产品推广、蹭热点

| 触发词 | 架构模式 | 入口 |
|--------|---------|------|
| "开始今日选题" / "start my day" | Pipeline (Orchestrator) | `start_my_day` |
| "看看什么热点" | Fan-out → Pipeline | `collect_* → trend_analyze` |
| "帮我做内容选题" | Fan-out → Pipeline | `collect_* → trend_analyze → content_brief → export` |
| "搜索我的产品并结合热点" | Search → Pipeline | WebSearch → `product_profile → collect_* → content_brief(--profile)` |
| "我产品怎么蹭热点" | Pipeline + Expert | `product_profile → collect_* → content_brief(--profile)` |
| "监控竞品在做什么" | Fan-out → Expert | `monitor_competitor → industry_insight(--profile)` |
| "完整情报" | Hierarchical | 全部工具，加载 `reference/orchestration.md` |
| "搜索历史热点 {关键词}" | Direct | `knowledge_base --query` |
| "生成关系图谱" | Direct | `export_mindmap --cumulative` |
| "更新知识库" | Direct | `knowledge_base --append` |

## 工具索引

13 个原子脚本 · `scripts/` 目录 · JSON stdin/stdout · `--schema` 自描述

| 工具 | Harness 层 | 一句话 | 权限 |
|------|-----------|--------|------|
| **collect_hotlist** | 感知 | 全网热榜采集（公共 API） | 网络 |
| **collect_rss** | 感知 | RSS 订阅采集 | 网络 |
| **collect_social** | 感知 | 社媒实时数据（小红书/抖音/微博） | CDP + 网络 |
| **monitor_competitor** | 感知 | 竞品内容监控 | CDP + 网络 |
| **trend_analyze** | 行动 | AI 趋势评分与分类 | AI API (CLI) |
| **content_brief** | 行动 | AI 内容创作简报（支持产品模式 `--profile`） | AI API (CLI) |
| **product_profile** | 行动 | 产品资料 → 结构化画像 | AI API (CLI) |
| **industry_insight** | 行动 | 行业趋势洞察（`--profile` + `--competitors`） | AI API (CLI) |
| **knowledge_base** | 知识 | 累积知识库：追加/搜索/统计/图谱导出 | 文件读写 |
| **export_excel** | 行动 | Excel 报表（总览/简报/素材/平台标题 4 Sheet） | 文件写入 |
| **export_obsidian** | 行动 | Obsidian：Topics 按类别 + Copywriting 按平台 + 周报 | 文件写入 |
| **export_mindmap** | 行动 | 力导向关系图谱（支持 `--cumulative`） | 文件写入 |
| **start_my_day** | 协调 | 一键编排器（支持 `--profile` / `--product-text`） | 组合 |

> **"AI API (CLI)"** = 独立运行才需要密钥。作为 Skill 时 Agent 自身就是 AI，直接按 `reference/prompt-templates.md` 在对话中完成分析。

## 渐进式知识加载（Progressive Disclosure）

**不要预加载所有 reference。** 按当前任务阶段，只读取需要的层级。

```
Level 1: 本文件 SKILL.md                (~1500 tokens) — 触发时自动加载
Level 2: reference/*.md                 (按需加载)      — 执行具体任务阶段时
Level 3: SOP/*.md + prompt-templates.md (深入时)        — 用户要求最佳实践/模板时
```

| Level 2 文件 | ~tokens | 何时加载 |
|-------------|---------|---------|
| `reference/orchestration.md` | ~1600 | 编排多工具流水线时 |
| `reference/data-contracts.md` | ~2500 | 确认工具 I/O 格式时 |
| `reference/context-budget.md` | ~1100 | 优化上下文/处理大数据集时 |
| `reference/workflow-patterns.md` | ~1500 | 需要完整 CLI 命令示例时 |
| `reference/platforms.md` | ~800 | 用户问支持哪些平台时 |
| `reference/cdp-api.md` | ~600 | 需要 CDP 操作细节时 |

| Level 3 文件 | 何时加载 |
|-------------|---------|
| `reference/prompt-templates.md` (分段) | Agent 原生模式执行 AI 分析时（只读对应 section） |
| `SOP/每日选题工作流.md` | 用户问 SOP/最佳实践时 |
| `SOP/话题深度分析.md` | 深入分析单个话题时 |
| `SOP/平台策略指南.md` | 用户问平台策略时 |
| `SOP/内容日历模板.md` | 用户做内容排期时 |
| `SOP/爆款复盘模板.md` | 用户复盘内容表现时 |
| `site-patterns/*.md` | CDP 操作特定平台时 |

## 上下文预算（必须遵守）

| 规则 | 执行方式 |
|------|---------|
| 采集数据不进主上下文 | 用 Task 子智能体运行 collect_*，只取回 `{file, count, errors}` |
| 中间 JSON 写磁盘 | `--output file.json` 落盘，不在对话中传递大 JSON |
| AI 分析用摘要 | trend_analyze 输入前只保留 title/platform/rank |
| --top N 控制量 | content_brief `--top` 默认全量，`config.yaml` 的 `analyze.top_n` (默认 8) 自动限制 |
| 输出文件路径传递 | 子智能体只返回文件路径，主 Agent 告知用户位置 |
| reference 不预加载 | 参见上方 Progressive Disclosure |

## 权限边界

| 权限层级 | 工具 | 条件 |
|----------|------|------|
| **无需授权** | knowledge_base (查询/统计), export_excel, export_obsidian, export_mindmap | 纯本地文件操作 |
| **网络访问** | collect_hotlist, collect_rss | 公共 API，无认证 |
| **AI API 密钥** | trend_analyze, content_brief, product_profile, industry_insight | CLI 模式需 `AI_API_KEY`；Agent 原生模式不需要 |
| **CDP 环境** | collect_social, monitor_competitor | 需 Chrome 远程调试 + `node scripts/cdp/check.mjs` |
| **文件写入** | knowledge_base (--append), 所有 export_*, start_my_day | 写入 `output/` 目录和 Obsidian vault |

**降级策略**：CDP 不可用 → 跳过 social/competitor；AI API 不可用 → Agent 原生分析；网络受限 → 单平台尝试。

## 六种架构模式

根据用户意图选择（详见 `reference/orchestration.md`）：

| 模式 | 适用场景 | 通信 |
|------|---------|------|
| **Pipeline** | 顺序链（collect → analyze → brief → export） | 上一步输出 → 下一步输入 |
| **Fan-out/Fan-in** | 并行采集（多平台 collect_*） | 分发后聚合 |
| **Expert Pool** | 产品/行业/竞品分析 | 按任务选专家工具 |
| **Producer-Reviewer** | Brief 质量检查 | content_brief → Agent 审核 → 迭代 |
| **Hierarchical** | 完整情报全流程 | 树状层级委派 |
| **Orchestrator** | 一键 start_my_day | 编排器统一调度 |

## 配置

`config.yaml`（从 `config.example.yaml` 复制）：

| 配置项 | 默认 | 说明 |
|--------|------|------|
| `vault_path` | `./HotCreator` | Obsidian 笔记库路径 |
| `collect.hotlist_platforms` | weibo/douyin/zhihu/baidu | 热榜采集平台 |
| `analyze.top_n` | 8 | content_brief 处理话题数上限 |
| `analyze.batch_size` | 2 | content_brief 每批处理数 |
| `graph.rolling_days` | 7 | 图谱滚动窗口天数 |
| `product.default_profile` | (空) | 预设产品画像路径 |

环境变量（仅 CLI）：`AI_API_KEY`、`AI_MODEL`（默认 deepseek/deepseek-chat）、`CDP_PROXY_PORT`（默认 3456）

## 依赖

```
pip install requests feedparser litellm openpyxl pytz pyyaml
```
