---
domain: weibo.com
aliases: [微博, Weibo, 新浪微博]
updated: 2026-03-31
---

## 平台特征

- 微博热搜榜 (s.weibo.com/top/summary) 公开可访问
- 页面为服务端渲染 + 客户端增强，基础内容在 HTML 中可用
- "实时上升"板块需要动态渲染才能完整获取
- 登录态不影响热搜榜可见性，但影响详情页完整度

## 有效模式

### 热搜榜提取

1. 打开 `https://s.weibo.com/top/summary`（微博热搜榜）
2. 等待页面加载，用 `/eval` 提取：
   ```javascript
   JSON.stringify(
     [...document.querySelectorAll('#pl_top_realtimehot table tbody tr')]
       .slice(1) // 跳过表头
       .map((tr, i) => ({
         rank: i + 1,
         title: tr.querySelector('.td-02 a')?.textContent?.trim(),
         heat: tr.querySelector('.td-02 span')?.textContent?.trim(),
         url: tr.querySelector('.td-02 a')?.href || '',
         tag: tr.querySelector('.td-03 i')?.textContent?.trim() || '',
       }))
       .filter(item => item.title)
   )
   ```

### 实时上升趋势

1. 同一页面中找到"实时上升热点"板块
2. 该板块可能在页面下方，需要先滚动：`/scroll?target=ID&direction=bottom`
3. 提取上升趋势列表

## 已知陷阱

- (2026-03) 微博页面可能弹出 APP 下载引导覆盖层，影响内容提取，用 eval 关闭或忽略即可
- (2026-03) `#pl_top_realtimehot` 选择器稳定性较好，但微博偶尔改版
- (2026-03) 热搜条目的 heat 值格式不固定（有时是数字，有时是"沸"/"热"等标签）
