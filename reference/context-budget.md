# Context Budget — 上下文管理策略

> "Context will fill up; you need a way to make room."
> 此文件定义 hot-creator 在 Agent 会话中的上下文消耗控制策略。

## Token 估算表

| 数据类型 | 典型大小 | 估算 tokens |
|----------|---------|------------|
| SKILL.md（v2 精简版） | ~80 行 | ~800 |
| 单平台热榜 JSON（50 items） | ~8KB | ~2,000 |
| 10 平台热榜合并 | ~80KB | ~20,000 |
| trend_analyze 输出（30 trends） | ~6KB | ~1,500 |
| content_brief 单话题 brief | ~4KB | ~1,000 |
| content_brief 15 话题 | ~60KB | ~15,000 |
| prompt-templates.md 完整 | ~260 行 | ~3,000 |
| orchestration.md | ~120 行 | ~1,500 |
| 本文件 | ~80 行 | ~800 |

**经验法则**：合并热榜 + 完整 brief = ~35K tokens。如果全部进主上下文，占用 200K 窗口的 17.5%。看似不多，但加上对话历史和系统提示，很容易超出。

## 三层压缩策略

### 第一层：子智能体隔离（Subagent Isolation）

**原则**：所有 I/O 密集型操作在子智能体中完成，主上下文只接收摘要。

```
[主 Agent]                          [子智能体]
   │                                    │
   ├─ Task: "采集微博+抖音+知乎热榜"    │
   │        ──────────────────────►     │
   │                                    ├─ 运行 collect_hotlist
   │                                    ├─ 输出 150 items → hotlist.json
   │                                    │
   │   ◄──────────────────────────      │
   │   返回: {file:"hotlist.json",      │
   │          count:150, errors:[]}     │
   │                                    │
   │  (子智能体的 150 items 不进主上下文)
```

**必须隔离的操作**：
- `collect_hotlist`（输出 100-500 items）
- `collect_rss`（输出 30-100 items）
- `collect_social`（输出 30-100 items）
- `monitor_competitor`（CDP 操作 + 输出数据）
- `export_*`（纯文件生成，不需要结果数据）

### 第二层：数据压缩（Data Compression）

在流水线各阶段之间压缩数据：

**采集 → 分析**：
```python
# 压缩：只保留分析必需字段
for item in items:
    compressed = {
        "title": item["title"],
        "platform": item["platform"],
        "rank": item["rank"]
    }
    # 丢弃 url, heat, published_at, summary
```

**分析 → 简报**：
```python
# content_brief --top 默认 0（全量），建议传 --top 8~15 控制数量
# config.yaml 的 analyze.top_n 控制 start_my_day 的默认值
for trend in trends[:top_n]:
    slim = {
        "topic": trend["topic"],
        "score": trend["score"],
        "direction": trend["direction"],
        "category": trend["category"],
        "platforms": trend["platforms"],
        "summary": trend["summary"]
    }
```

**简报 → 输出**：
- 简报数据直接写文件（`--output briefs.json`）
- 主 Agent 只传递文件路径给 export 工具
- 不在对话中打印完整 brief JSON

### 第三层：知识延迟加载（Deferred Knowledge Loading）

**reference 文件加载时机**：

| 阶段 | 加载什么 | 不加载什么 |
|------|---------|-----------|
| 初始触发 | 只有 SKILL.md | 其他一律不加载 |
| 编排决策 | orchestration.md（如需多工具） | prompt-templates, cdp-api |
| AI 分析 | prompt-templates.md 的对应 section | 不加载 content_brief section 如果只做 trend_analyze |
| CDP 操作 | cdp-api.md + 目标平台的 site-pattern | 不加载其他平台的 pattern |
| 调试/格式问题 | data-contracts.md | - |

**prompt-templates 分段加载**：
- 做趋势分析 → 只读 `## trend_analyze` section
- 做内容简报 → 只读 `## content_brief` section
- 不要一次性加载整个文件

## 长会话管理

### 单次完整流水线后

完整的 Pattern 5（完整情报）执行后，上下文已消耗较多。此时：

1. **不再保留**中间文件内容（merged.json, trends.json 的内容）
2. **只保留**最终文件路径和统计摘要
3. 如果用户要做第二轮分析，重新采集而不是复用旧数据

### 多轮对话策略

```
Round 1: 用户要求完整情报
  → 执行 Pattern 5
  → 产出 Excel + Obsidian + Mindmap
  → 告知用户文件路径 + 关键发现摘要（5-10 行）

Round 2: 用户问 "能不能针对 XXX 话题深入一下"
  → 不需要重新采集
  → 从 briefs.json 读取该话题的 brief
  → 在主上下文中展开讨论（单话题数据量小）

Round 3: 用户要求更新数据
  → 重新执行 Pattern 1-2（采集 + 分析）
  → 用子智能体隔离新数据
```

### 中间结果持久化

所有中间产物落盘，命名规范：

```
output/
├── {date}-hotlist.json       # collect_hotlist 输出
├── {date}-rss.json           # collect_rss 输出
├── {date}-social.json        # collect_social 输出
├── {date}-merged.json        # 合并后数据
├── {date}-trends.json        # trend_analyze 输出
├── {date}-briefs.json        # content_brief 输出
├── {date}-profile.json       # product_profile 输出
├── {date}-competitors.json   # monitor_competitor 输出
├── {date}-insight.json       # industry_insight 输出
├── {date}-report.xlsx        # Excel 报表
└── {date}-mindmap.md         # 思维导图
```

子智能体统一使用 `output/` 目录。下一轮操作可以复用已有中间文件。

## 紧急降级

当检测到上下文接近极限（对话非常长）：

1. 只做 Pattern 1（快速趋势），跳过 brief
2. `--top 5` 限制话题数量
3. 只输出 Excel，不做 Obsidian/Mindmap
4. 不加载任何 reference 文件，靠工具的 `--help` 自述
