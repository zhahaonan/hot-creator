---
domain: douyin.com
aliases: [抖音, TikTok CN, 巨量算数]
updated: 2026-03-31
---

## 平台特征

- 抖音网页版 (douyin.com) 为 SPA 架构，内容动态渲染
- 热榜数据可通过巨量算数 (trendinsight.oceanengine.com) 获取，该站公开且反爬较弱
- 抖音主站反爬较强，优先使用巨量算数入口

## 有效模式

### 热榜提取（巨量算数）

1. 打开 `https://trendinsight.oceanengine.com/arithmetic-index/analysis/hot` 或类似热榜页面
2. 页面加载后，用 `/eval` 提取热搜列表：
   ```javascript
   JSON.stringify(
     [...document.querySelectorAll('.hot-list-item, [class*="rank-item"], tr')]
       .map((el, i) => ({
         rank: i + 1,
         title: el.querySelector('.title, .keyword, td:nth-child(2)')?.textContent?.trim(),
         heat: el.querySelector('.heat, .hot-value, td:nth-child(3)')?.textContent?.trim(),
       }))
       .filter(item => item.title)
   )
   ```

### 抖音主站热点

1. 打开 `https://www.douyin.com/hot`（热点榜）
2. 滚动加载更多内容：`/scroll?target=ID&direction=bottom`
3. 提取热点列表 DOM

## 已知陷阱

- (2026-03) 巨量算数首次访问可能弹出用户协议，需点击同意
- (2026-03) 抖音主站未登录时部分热点详情页会跳转到登录页
- (2026-03) 热榜页面可能有多种布局版本（A/B 测试），选择器需要灵活适配
