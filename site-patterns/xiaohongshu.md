---
domain: xiaohongshu.com
aliases: [小红书, xhs, RED]
updated: 2026-03-31
---

## 平台特征

- SPA 架构，内容通过 JS 动态渲染，静态抓取无法获得完整数据
- 反爬严格：请求中含 xsec_token 等签名参数，手动构造 URL 大概率被拦
- 登录态影响内容可见性，未登录可看部分公开内容但可能触发登录弹窗
- 热搜/发现页为动态加载，需要真实浏览器环境

## 有效模式

### 热搜趋势提取

1. 打开 `https://www.xiaohongshu.com/explore`（发现页）
2. 页面加载后，热搜通常在侧边栏或顶部标签区域
3. 用 `/eval` 提取热搜列表：
   ```javascript
   // 提取思路：查找热搜容器，遍历子元素提取标题和链接
   // 实际选择器需根据当前页面 DOM 结构确定
   JSON.stringify(
     [...document.querySelectorAll('.hot-item, .trending-item, [class*="hot"]')]
       .map((el, i) => ({
         rank: i + 1,
         title: el.textContent?.trim(),
         url: el.querySelector('a')?.href || ''
       }))
       .filter(item => item.title)
   )
   ```
4. 如果上述选择器无效，先用 eval 探索页面结构：
   ```javascript
   document.body.innerHTML.substring(0, 5000)
   ```

### 话题详情

- 从 DOM 中提取的完整 URL（含 xsec_token）比手动构造可靠
- 在新 tab 中打开话题链接获取详情

## 已知陷阱

- (2026-03) 手动构造 `/search_result?keyword=xxx` URL 会被 xsec_token 验证拦截
- (2026-03) 密集请求（短时间内打开 >5 个 tab）可能触发滑动验证
- (2026-03) 部分内容在未登录状态下显示"内容不存在"，实际是反爬行为而非真的不存在
