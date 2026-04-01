---
name: hot-creator
version: "4.3.1"
description: 产品 x 热点内容策划工具链 — 采集全网热点，结合你的产品生成完整创作方案
user-invocable: true
metadata: {"openclaw": {"emoji": "🔥", "homepage": "https://github.com/zhahaonan/hot-creator", "requires": {"anyBins": ["python3", "python"]}, "install": [{"id": "pip", "kind": "node", "label": "Install deps", "bins": ["python"]}]}}
---

# hot-creator

> **核心逻辑：采集全网热点 → 结合用户的产品/品牌 → 给出完整的创作思路和素材。**
> 不要用外部搜索替代采集，不要自己写分析替代 AI 脚本。

## 安装

```bash
cd {baseDir}
pip install -r requirements.txt
```

**不需要配置 AI_API_KEY。**

## 触发条件

用户意图涉及：热点、趋势、选题、内容创作、热搜、爆款、创作灵感、产品推广、蹭热点

**触发后必须获取产品/品牌信息**：
- 用户消息中已包含产品名/描述 → 直接使用
- 用户提供了 **PDF/文档路径**（或上传文件后给出路径）→  
  - **无 API Key（Skill）**：先 `python {baseDir}/scripts/product_profile.py --file <路径> --extract-only -o output/product-raw.txt` 抽出正文，Agent 再基于正文生成画像 JSON；或让用户粘贴 PDF 里的文字  
  - **有 API Key（CLI）**：`product_profile.py --file <路径> -o output/profile.json`，或 `start_my_day.py --product-file <路径>` 一键全流程
- 都没有 → 追问："你的产品/品牌是什么？一句话描述即可"

## 强制执行流程（每一步都必须做）

### Step 1 — 采集热点

```bash
# 热门榜单（默认 29 个平台）
python {baseDir}/scripts/collect_hotlist.py -o output/hotlist.json

# 或指定平台
python {baseDir}/scripts/collect_hotlist.py --platforms weibo,douyin,zhihu -o output/hotlist.json

# 同时采集实时新闻流
python {baseDir}/scripts/collect_hotlist.py --type realtime -o output/realtime.json

# 全部（热门+实时）
python {baseDir}/scripts/collect_hotlist.py --type all -o output/all.json
```

用 Task 子智能体执行，只取回文件路径。

**每条 item 尽量保留上游字段**（平台不一致，可能为空）：
- `snippet`：摘要/正文片段（如知乎 `hover` 长文预览）
- `published_at`：条目发布时间（如联合早报 `pubDate`、快讯 `extra.date`）
- `url` / `mobile_url`：原文与移动页
- `heat`：热度短标签（若有）
- `collected_at`：本次采集时间（北京时间 ISO 8601）
- `platform_updated_at`：该源榜单/流在 NewsNow 侧的更新时间
- `source_type`：`hotlist` 或 `realtime`

若某源只返回标题，则 `snippet` 为空；分析时可结合 `url` 或 `enrich_topics` 补全文。

### Step 2 — Agent 分析趋势

Agent 读取 `output/hotlist.json`，对采集到的热点做以下分析，输出 JSON 写入 `output/trends.json`：

- 跨平台去重聚合（同一事件合并）
- 热度评分 0-100（综合排名、覆盖平台数、新鲜度）
- 趋势方向：rising / peak / declining / emerging
- 分类：科技/财经/娱乐/社会/国际/教育/其他
- 一句话概要
- **注意 `platform_updated_at` 和 `source_type` 字段**：区分"已经火了"vs"刚刚发生"有助于判断时效性

输出格式：
```json
{
  "trends": [
    {
      "topic": "话题名（≤20字）",
      "score": 95,
      "direction": "rising",
      "category": "科技",
      "platforms": ["微博", "知乎"],
      "platform_count": 2,
      "summary": "一句话概要（≤50字）",
      "is_emerging": false
    }
  ]
}
```

### Step 3 — Agent 生成完整创作方案

Agent 读取 `output/trends.json`，结合用户的产品信息，为 top 8 个话题生成**完整的、可直接执行的内容方案**，写入 `output/briefs.json`。

**每个话题必须包含以下全部内容（不能省略）**：

1. **产品结合点** — 你的产品跟这个热点的真实连接（关联弱就说"不建议硬蹭"）
2. **创作角度**（1-2个）— 角度名具体到能当标题 + 完整执行步骤 + 产品角色 + 最适合平台
3. **短视频脚本** — 完整开头话术 hook + 逐句口播内容(30-60字/句) + 每句对应画面描述 + CTA
4. **小红书图文** — 封面大字标题(含emoji) + 每页内容(title+content+配图建议) + 话题标签
5. **长文大纲** — 标题 + 每章节的标题/核心论点/论据数据/产品植入点
6. **素材清单** — 5-8条含数字的数据点 + 口播金句(8-18字) + 封面字幕文字(≤14字) + 信源URL
7. **平台标题** — 抖音/小红书/公众号/知乎/B站各 2 个（直接能用，不是方向建议）
8. **发布建议** — 首发平台 + 最佳发布时间 + 热度窗口期 + 平台优先级

输出格式：
```json
{
  "briefed_trends": [
    {
      "topic": "话题名",
      "score": 95,
      "direction": "rising",
      "category": "科技",
      "platforms": ["微博"],
      "summary": "概要",
      "product_relevance": "high",
      "brief": {
        "product_tie_in": "产品与热点的连接",
        "angles": [{"name": "角度名", "description": "完整执行方案", "product_role": "产品角色", "best_platform": "抖音", "appeal": "高"}],
        "outlines": {
          "short_video": {"hook": "开头话术", "beats": [{"content": "口播内容", "visual": "画面"}], "cta": "引导语"},
          "xiaohongshu": {"cover_title": "封面标题", "slides": [{"title": "页标题", "content": "内容", "image_note": "配图"}], "hashtags": ["标签"]},
          "article": {"title": "文章标题", "sections": [{"heading": "章节", "core_point": "论点", "evidence": "论据", "product_mention": "植入点"}]}
        },
        "materials": {
          "data_points": [{"fact": "含数字的事实", "source": "来源", "how_to_use": "用法"}],
          "sound_bites": ["8-18字口播金句"],
          "screenshot_lines": ["≤14字封面文字"],
          "sources": [{"title": "标题", "url": "链接", "takeaway": "要点"}]
        },
        "titles": {"douyin": ["标题1", "标题2"], "xiaohongshu": ["标题1", "标题2"], "gongzhonghao": ["标题1", "标题2"], "zhihu": ["标题1", "标题2"], "bilibili": ["标题1", "标题2"]},
        "recommendation": {"first_platform": "首发", "best_time": "时间", "trending_window": "窗口", "platform_priority": ["平台1", "平台2"]}
      }
    }
  ]
}
```

### Step 4 — 必须执行全部 3 个导出（不能跳过）

```bash
# 生成 Obsidian Markdown 笔记（这是用户要的 .md 文档）
python {baseDir}/scripts/export_obsidian.py -i output/briefs.json --vault .

# 生成 Excel 报表
python {baseDir}/scripts/export_excel.py -i output/briefs.json --xlsx output/report.xlsx

# 生成 D3 力导向思维导图（HTML 交互式）
python {baseDir}/scripts/export_mindmap.py -i output/briefs.json -o output/mindmap.html
```

**3 个导出都必须执行。** export_obsidian 生成 .md 文件，export_mindmap 生成可交互的 HTML 图谱。

### Step 5 — 告知用户结果

告诉用户生成了哪些文件及路径，简要总结 top 3 话题的创作方向。

## 支持平台

**热门榜单 (29 源)：** 微博, 抖音, 知乎, 百度热搜, 今日头条, B站, 澎湃新闻, 虎扑, 百度贴吧, 酷安, 豆瓣, 凤凰网, 牛客, 腾讯新闻, 腾讯视频, 爱奇艺, 虫部落, 36氪人气榜, 华尔街见闻, 财联社热门, 雪球, Hacker News, Product Hunt, GitHub Trending, 少数派, 稀土掘金, Freebuf, Steam

**实时新闻流 (8 源)：** 联合早报, 华尔街见闻快讯, 36氪快讯, 财联社电报, IT之家, 格隆汇, 金十数据, 法布财经

> 数据源来自 [NewsNow](https://newsnow.busiyi.world/)，采集数据自动带时间标签。

## 工具索引

| 工具 | 一句话 |
|------|--------|
| **collect_hotlist** | 全网热榜+实时采集（37 源，支持 --type hotlist/realtime/all） |
| **collect_rss** | RSS 订阅采集 |
| **collect_social** | 社媒数据规范化 |
| **enrich_topics** | 合并 WebSearch 结果到趋势数据 |
| **export_excel** | Excel 报表（4 Sheet） |
| **export_obsidian** | Obsidian .md 笔记（按类别+按平台） |
| **export_mindmap** | D3 力导向关系图谱（HTML 交互式） |
| **knowledge_base** | 累积知识库 |
| **verify** | 对抗性验证 |

> `python {baseDir}/scripts/<tool>.py`，JSON stdin/stdout，`--schema` 查看接口。

## 自修复

| 故障 | 自修复行为 |
|------|-----------|
| 单平台采集超时 | 内置 3 次 retry，指数退避 |
| 依赖未安装 | `ensure_deps()` 自动 pip install |
| 单个 export 失败 | 不影响其他 export，继续执行 |
| 采集全失败 | 用 collect_rss 替代 |

## 约定

- 采集类脚本用 Task 子智能体执行，只取回文件路径
- 中间 JSON 写 `output/`，传路径不传内容
- Agent 自己做 Step 2 和 Step 3 的 AI 分析，不需要调用 trend_analyze.py 和 content_brief.py
- **Step 4 的 3 个 export 脚本必须全部执行，不能跳过**
- 分析趋势时注意 `platform_updated_at` 和 `source_type` 字段判断时效性
