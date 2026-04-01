# hot-creator

**产品 x 热点内容策划助手** — AI Agent Skill for content creators.

采集全网热点趋势，结合你的产品/品牌，生成完整的创作思路和素材（短视频脚本、小红书图文、长文大纲、素材清单、平台标题）。输出 Obsidian .md 笔记、Excel 报表、D3 交互式关系图谱。

## Quick Start / 快速开始

### As AI Agent Skill（推荐）

**Cursor / Claude Code / Cline / Windsurf / 其他 Agent 工具：**
```bash
git clone https://github.com/zhahaonan/hot-creator.git
cd hot-creator
pip install -r requirements.txt
```

> 有 `uv` 的话更快：`uv pip install -r requirements.txt`
> **不需要配置 AI API Key** — Agent 自己就是 AI。

装好后对 Agent 说：

```
"我的产品是 XXX，帮我结合当下热点生成内容创作方案"
```

Agent 自动执行：采集全网热点 → 分析趋势 → 结合你的产品生成完整创作方案 → 输出 .md + .xlsx + 思维导图。

### Standalone CLI（独立命令行）

```bash
# 一键全流程（会交互式问你的产品信息）
python scripts/start_my_day.py

# 或指定产品直接跑
python scripts/start_my_day.py --no-interactive --product-text "我们是一个AI写作助手..."

# 逐步执行
python scripts/collect_hotlist.py --platforms weibo,douyin,zhihu -o output/hotlist.json
python scripts/trend_analyze.py -i output/hotlist.json -o output/trends.json
python scripts/content_brief.py -i output/trends.json --profile profile.json --top 8 -o output/briefs.json
python scripts/export_excel.py -i output/briefs.json --xlsx output/report.xlsx
python scripts/export_obsidian.py -i output/briefs.json --vault .
python scripts/export_mindmap.py -i output/briefs.json -o output/mindmap.html
```

> CLI 独立运行 AI 脚本（trend_analyze / content_brief）需要 `AI_API_KEY` 环境变量和 `pip install litellm`。

## What You Get / 输出内容

每个热点话题生成**完整的、可直接执行的内容方案**：

| 内容 | 说明 |
|------|------|
| 产品结合点 | 你的产品跟这个热点怎么关联 |
| 创作角度 | 具体到能当标题，含完整执行步骤 |
| 短视频脚本 | 逐句话术 + 画面描述 + CTA |
| 小红书图文 | 封面标题 + 每页内容 + 标签 |
| 长文大纲 | 章节 + 论据 + 产品植入点 |
| 素材清单 | 数据点、口播金句、封面文字、信源 |
| 平台标题 | 抖音/小红书/公众号/知乎/B站各 2 个 |
| 发布建议 | 首发平台 + 最佳时间 + 窗口期 |

输出格式：
- **Obsidian .md 笔记** — 按类别和平台归类的 Markdown 文档
- **Excel 报表** — 趋势总览 + 创作简报 + 素材库 + 标题矩阵 (4 Sheet)
- **D3 关系图谱** — 交互式 HTML 力导向图，可视化话题关联

## Tools / 工具

| Tool | Description | Deps |
|------|-------------|------|
| **collect_hotlist** | 全网热榜采集（10+ 平台，内置 retry） | requests |
| **collect_rss** | RSS 订阅采集 | feedparser |
| **collect_social** | 社媒数据规范化器 | — |
| **enrich_topics** | 话题充实（合并 WebSearch 结果） | — |
| **trend_analyze** | AI 趋势评分与分类 | litellm (可选) |
| **content_brief** | 产品 x 热点完整内容方案 | litellm (可选) |
| **product_profile** | 产品资料 → 结构化画像 | litellm (可选) |
| **industry_insight** | 行业趋势洞察 | litellm (可选) |
| **knowledge_base** | 累积知识库（追加/搜索/图谱） | — |
| **export_excel** | Excel 报表 (4 Sheet) | openpyxl |
| **export_obsidian** | Obsidian .md 笔记 | — |
| **export_mindmap** | D3 力导向关系图谱 (HTML) | — |
| **verify** | 对抗性验证（5 套件） | — |
| **start_my_day** | 一键编排器（内置 retry + 降级） | — |

```bash
python scripts/collect_hotlist.py --help    # Usage
python scripts/collect_hotlist.py --schema  # JSON Schema
python scripts/collect_hotlist.py --version # Version
```

## Self-Healing / 自修复

- 单平台采集超时 → 内置 3 次 retry，指数退避
- AI 返回非法 JSON → 自动剥离 markdown fence + 修复截断
- Pipeline 采集全失败 → 降级到 RSS-only
- Pipeline brief 失败 → 降级到 trends-only 导出
- 单个 export 失败 → 不影响其他 export
- 依赖未安装 → 自动 pip install

## Supported Platforms / 支持平台

**热门榜单 (40+ 源):** 微博, 抖音, 知乎, 百度热搜, 今日头条, B站, 澎湃新闻, 虎扑, 百度贴吧, 酷安, 豆瓣, 凤凰网, 牛客, 腾讯新闻, 腾讯视频, 爱奇艺, 虫部落, 36氪人气榜, 华尔街见闻, 财联社热门, 雪球, Hacker News, Product Hunt, GitHub Trending, 少数派, 稀土掘金, Freebuf, Steam

**实时新闻流:** 联合早报, 华尔街见闻快讯, 36氪快讯, 财联社电报, IT之家, 格隆汇, 金十数据, 法布财经

**RSS:** 36氪, Hacker News, 少数派（可配置自定义 feed）

> 数据源来自 [NewsNow](https://newsnow.busiyi.world/)，采集结果除标题外还会尽量保留：**`snippet`**（如知乎 `hover` 长摘要）、**`published_at`**（如联合早报 `pubDate`、快讯里的毫秒时间）、**`url` / `mobile_url`**、**`heat`**。若某平台 API 只给标题，则 `snippet` 为空——需正文时请用 `url` 打开或配合 `enrich_topics` / Web 抓取。

## Version / 版本

- 版本号见 `VERSION` 文件
- `start_my_day` 自动对比 GitHub 上的版本（缓存 24h）
- 手动检查：`python scripts/check_update.py`
- 关闭检查：`HOT_CREATOR_SKIP_UPDATE_CHECK=1`

## Requirements / 依赖

- Python >= 3.10
- Core: `requests`, `feedparser`, `openpyxl`, `pytz`, `pyyaml`
- CLI AI 脚本（可选）: `litellm`

## License

MIT
