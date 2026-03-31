# Supported Platforms

## Hotlist Platforms (via public API)

These platforms are fetched through the NewsNow public API. No authentication required.

| Platform ID | Name | Type | Notes |
|-------------|------|------|-------|
| `weibo` | 微博 | hotlist | 微博热搜榜 |
| `douyin` | 抖音 | hotlist | 抖音热点榜 |
| `zhihu` | 知乎 | hotlist | 知乎热榜 |
| `baidu` | 百度 | hotlist | 百度热搜 |
| `toutiao` | 头条 | hotlist | 今日头条热榜 |
| `bilibili-hot-search` | B站 | hotlist | B站热搜 |
| `36kr` | 36氪 | hotlist | 36氪热榜 |
| `ithome` | IT之家 | hotlist | IT之家热榜 |
| `thepaper` | 澎湃新闻 | hotlist | 澎湃新闻热榜 |
| `cls-telegraph` | 财联社电报 | hotlist | 财联社快讯 |

### API Details

- Endpoint: `https://newsnow.busiyi.world/api/s?id={platform_id}&latest`
- Method: GET
- Response: JSON with `items` array
- Rate: Add 0.3-1s delay between requests

## Social Platforms (via CDP browser)

These platforms require the built-in CDP browser engine for dynamic page rendering.

| Platform ID | Name | Type | Target URL | Notes |
|-------------|------|------|------------|-------|
| `xiaohongshu` | 小红书 | social | `xiaohongshu.com/explore` | Needs CDP; strict anti-scraping |
| `douyin_realtime` | 抖音实时 | social | `douyin.com/hot` | Needs CDP |
| `weibo_rising` | 微博上升 | social | `s.weibo.com/top/summary` | Rising trends section |

### CDP Requirements

- Chrome with remote debugging enabled
- Node.js 22+
- Run `node <SKILL_DIR>/scripts/cdp/check.mjs` before social collection

## RSS Feeds (configurable)

Default feeds included in `collect_rss.py`:

| Feed ID | Name | URL |
|---------|------|-----|
| `36kr` | 36氪 | `https://36kr.com/feed` |
| `hn` | Hacker News | `https://hnrss.org/frontpage` |
| `sspai` | 少数派 | `https://sspai.com/feed` |

Custom feeds can be provided via `--input` JSON or `--feeds-json` file.

### Custom Feed Format

```json
{
  "feeds": [
    {
      "id": "my-feed",
      "name": "My Custom Feed",
      "url": "https://example.com/rss",
      "max_items": 20,
      "max_age_days": 3
    }
  ]
}
```
