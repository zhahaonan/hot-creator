# Workflow Patterns — CLI 命令行工作流模板

> **何时加载此文件**：需要完整 CLI 命令示例时。
> 每个 Pattern 都是可复制粘贴的命令序列。Agent 原生模式参考 `orchestration.md`。

## Pattern 1: Full Pipeline — 完整流水线

从采集到输出一气呵成，获得最完整的热点情报。

```
Step 1 (parallel):
  python scripts/collect_hotlist.py --platforms weibo,douyin,zhihu,baidu -o hotlist.json
  python scripts/collect_rss.py -o rss.json
  python scripts/collect_social.py --targets xiaohongshu,weibo_rising -o social.json

Step 2: Merge outputs
  Combine items arrays from hotlist.json + rss.json + social.json into merged.json

Step 3:
  python scripts/trend_analyze.py -i merged.json -o trends.json

Step 4:
  python scripts/content_brief.py -i trends.json --top 15 -o briefs.json

Step 5 (parallel):
  python scripts/export_excel.py -i briefs.json -o report.xlsx
  python scripts/export_obsidian.py -i briefs.json --vault "C:/ObsidianVault"
  python scripts/export_mindmap.py -i briefs.json -o mindmap.html
```

## Pattern 2: Quick Trend Scan — 快速趋势扫描

跳过创作简报，只看当前趋势排名。适合快速了解"什么在火"。

```
Step 1 (parallel):
  python scripts/collect_hotlist.py -o hotlist.json

Step 2:
  python scripts/trend_analyze.py -i hotlist.json -o trends.json

Step 3:
  python scripts/export_excel.py -i trends.json -o quick-scan.xlsx
```

注意：export_excel 也接受 trend_analyze 的输出（没有 brief 字段时，创作简报 sheet 为空）。

## Pattern 3: Deep Dive on Single Topic — 单话题深挖

已知某个话题，直接生成完整创作简报。

```
Step 1: Construct input manually
  { "trends": [{ "topic": "AI行业大消息", "score": 90, "direction": "rising", "category": "科技", "platforms": ["微博", "知乎"], "summary": "..." }] }

Step 2:
  python scripts/content_brief.py -i topic.json -o brief.json

Step 3:
  python scripts/export_obsidian.py -i brief.json --vault "C:/ObsidianVault"
```

## Pattern 4: Hotlist Only (No CDP) — 纯热榜模式

不需要 Chrome/CDP，只使用公共 API 和 RSS。适合服务器环境。

```
Step 1 (parallel):
  python scripts/collect_hotlist.py -o hotlist.json
  python scripts/collect_rss.py -o rss.json

Step 2-5: Same as Pattern 1
```

## Pattern 5: Social Media Focus — 社交媒体聚焦

只采集社交媒体实时数据，用于捕捉 API 热榜可能遗漏的新兴趋势。

```
Step 1:
  node scripts/cdp/check.mjs  # Ensure CDP ready

Step 2:
  python scripts/collect_social.py --targets xiaohongshu,douyin,weibo_rising -o social.json

Step 3-5: Same as Pattern 1
```

## Pattern 6: Product x Trend — 产品 x 热点结合

用户提供了产品资料，生成与产品强关联的内容方案。

```
Step 1: Parse product info
  python scripts/product_profile.py --text "我们是一个AI写作助手，主要面向自媒体人..." -o profile.json
  # OR: python scripts/product_profile.py --file product-intro.pdf -o profile.json

Step 2 (parallel):
  python scripts/collect_hotlist.py --platforms weibo,douyin,zhihu -o hotlist.json
  python scripts/collect_rss.py -o rss.json

Step 3: Merge collected data
  # Combine items arrays from hotlist.json + rss.json into merged.json
  # (主 Agent 合并 或 start_my_day 自动完成)

Step 4:
  python scripts/trend_analyze.py -i merged.json -o trends.json

Step 5: Product-aware content briefs
  python scripts/content_brief.py --profile profile.json -i trends.json --top 10 -o briefs.json

Step 6 (parallel):
  python scripts/export_excel.py -i briefs.json -o product-trends.xlsx
  python scripts/export_obsidian.py -i briefs.json --vault "C:/ObsidianVault"
  python scripts/export_mindmap.py -i briefs.json -o mindmap.html
```

**一键模式**：`python scripts/start_my_day.py --profile profile.json`
或 `python scripts/start_my_day.py --product-text "我们是一个AI写作助手..."`

## Pattern 7: Full Intelligence — 完整情报（产品+竞品+行业）

最完整的模式：产品画像 + 全网热点 + 竞品监控 + 行业洞察。

```
Step 1: Product profile
  python scripts/product_profile.py --text "..." --competitors "竞品A,竞品B" -o profile.json

Step 2 (parallel):
  python scripts/collect_hotlist.py -o hotlist.json
  python scripts/collect_social.py -o social.json
  python scripts/monitor_competitor.py -i competitors.json -o comp.json
  # competitors.json example:
  # {"competitors": [
  #   {"name": "竞品A", "platform": "xiaohongshu"},
  #   {"name": "竞品A", "platform": "wechat_mp"},
  #   {"name": "竞品B", "platform": "xiaohongshu"}
  # ]}

Step 3:
  python scripts/trend_analyze.py -i merged.json -o trends.json

Step 4: Industry insight (combines trends + profile + competitor data)
  python scripts/industry_insight.py -i trends.json --profile profile.json --competitors comp.json -o insight.json

Step 5: Product-aware briefs
  python scripts/content_brief.py --profile profile.json -i trends.json --top 15 -o briefs.json

Step 6 (parallel):
  python scripts/export_excel.py -i briefs.json -o report.xlsx
  python scripts/export_obsidian.py -i briefs.json --vault "C:/ObsidianVault"
  python scripts/export_mindmap.py -i briefs.json -o mindmap.html
```

## Agent Orchestration Tips

- **Parallel collection**: Use Task subagents to run all collect tools simultaneously
- **Merge strategy**: Simply concatenate all `items` arrays into one `{"items": [...all...]}`
- **Selective output**: User only wants Excel? Skip export_obsidian and export_mindmap
- **Token budget**: Use `--top N` on content_brief to limit AI calls
- **No CDP available**: Fall back to Pattern 4 (hotlist + RSS only)
- **Product mode**: When user mentions their product, run `product_profile` first, then pass profile to `content_brief --profile`
- **Competitor input**: User can provide competitor names as text; `monitor_competitor` needs CDP for actual scraping
