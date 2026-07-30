# 任务报告：小程序首页与 post-card 组件水墨风重写

## 1. 任务概述

在 `miniprogram` 目录下，使用项目已有的水墨风设计系统（CSS 变量已在 `app.wxss` 中定义）重写 `post-card` 组件和 `home` 首页，统一小程序视觉风格，对齐 Web 端 MobileNav 设计。

## 2. 已完成内容

### 任务 1：重写 post-card 组件
- **post-card.wxss**：完全重写为水墨风样式
  - 卡片：`var(--paper)` 背景 + `rgba(216,225,227,0.6)` 边框 + `var(--radius-lg)` 圆角 + `var(--shadow-sm)` 阴影 + `margin-bottom 24rpx`
  - 头部：头像 72rpx 圆形 + 昵称 `var(--ink)` 28rpx 600 + 分类标签（使用分类色板 CSS 类）+ 时间 `var(--muted)` 22rpx
  - 正文：标题 `var(--ink)` 30rpx 700 + 内容 `var(--ink-2)` 26rpx line-height 1.7
  - 图片：圆角 `var(--radius-sm)`
  - 底部分割线：`border-top 1rpx solid var(--ink-divider)`
  - 底部：位置 `var(--muted)` 22rpx + 统计数字用 `var(--font-data)` DIN 字体
- **post-card.wxml**：完全重写
  - 移除所有 emoji（📍 👍 💬 ✅）
  - 分类标签用 `class="category-tag cat-{{categoryClass}}"` 动态绑定
  - 位置图标用「⊙」符号代替 📍
  - 统计区域改为「浏览 / 赞 / 评」文字 + 数字（数字用 DIN 字体 `.stat-num`）
- **post-card.ts**：添加 `categoryClass` 计算逻辑
  - 新增 `mapCategoryToClass()` 辅助函数
  - 映射规则：美食/食物/餐饮→food、活动/事件→event、服务→service、学习/学术→study、失物招领/失物→lostFound、社团→club、其他→default
  - 兼容 `post.category_name` 与 `post.category.name` 两种数据结构
  - `data` 中新增 `categoryClass: 'default'` 默认值

### 任务 2：重写 home 首页
- **home.wxss**：完全重写为水墨风样式
  - 顶部栏：`var(--paper)` 背景 + `var(--ink-divider)` 底边 + padding 20rpx 30rpx
  - 校名：`var(--font-display)` 楷书 + 36rpx + 800 + `var(--lake)`
  - 搜索框：`var(--mist)` 背景 + `var(--radius-lg)` 圆角 + 64rpx 高 + `var(--muted)`
  - 专题入口：`var(--lake)` 色，无 emoji
  - 分类 Tab：白色背景，active 项 `var(--lake)` + `border-bottom 4rpx solid var(--lake)`，非 active `var(--muted)`
  - 帖子列表：padding 24rpx
  - 底部导航（浮动胶囊式，对齐 Web MobileNav）：
    - `position fixed`，`bottom/left/right 12rpx`
    - `background: rgba(23, 77, 94, 0.95)` (lake/95)
    - `border-radius: var(--radius-lg)` + `border: 1rpx solid rgba(255,255,255,0.1)`
    - `box-shadow: 0 16rpx 64rpx rgba(20,55,63,0.25)`
    - 4 项 grid 布局（首页/地图/发布/我的）
    - active 项：`var(--paper)` 背景 + `var(--lake)` 文字 + `var(--radius-sm)` 圆角
    - 非 active：`rgba(255,255,255,0.7)` 文字
    - 文字标签 20rpx，无 emoji
    - 发布按钮：中间凸出，`var(--lamp)` 灯笼橙 + 圆形 80rpx + `#fff` 文字 + `var(--shadow-lamp)` 阴影
- **home.wxml**：完全重写
  - 顶部栏：校名 + 搜索入口（"搜" 字 + "搜索校园信息..."）+ 专题入口，全部文字，无 emoji
  - 分类 Tab：横向 scroll-view
  - 底部导航 4 项：首页、地图、发布（中间凸出）、我的
  - 搜索从底部导航移除（已在顶部栏有搜索入口）
  - 空状态：用「○」符号代替 📭
  - 加载状态：用文字"加载中"代替 spinner（移除 .loading-spinner）
- **home.ts**：经核实无需功能性修改
  - `activeTab: 'home'` 字段已存在，取值范围对应 home/map/publish/profile
  - `goToSearch` 方法已保留，供顶部搜索入口调用
  - 所有跳转方法（goToHome/goToMap/goToPublish/goToProfile/goToTopics）齐全
  - 遵循"不过度设计"原则，未做无意义改动

## 3. 未完成内容

暂无。

## 4. 实现思路

1. **设计 Token 复用**：所有颜色、阴影、圆角、字体均直接使用 `app.wxss` 中已定义的 CSS 变量（`--ink`、`--paper`、`--lake`、`--lamp`、`--shadow-sm`、`--radius-lg`、`--font-display` 等），确保与 Web 端视觉系统一致。
2. **分类色板动态绑定**：在 `post-card.ts` 中通过 `mapCategoryToClass()` 将中文分类名正则匹配到 7 个分类色板 CSS 类名（food/event/service/study/lostFound/club/default），WXML 通过 `cat-{{categoryClass}}` 动态渲染，复用 `app.wxss` 已定义的 `.cat-*` 类。
3. **去 emoji 化**：所有 emoji 替换为文字或几何符号（⊙ ○ + 搜），符合水墨风简约设计语言。
4. **底部导航对齐 Web**：采用浮动胶囊式设计（lake/95 半透明背景 + 大圆角 + 强阴影），与 Web 端 `MobileNav.tsx` 视觉对齐；发布按钮中间凸出使用灯笼橙强调色。
5. **数据结构兼容**：`post-card.ts` 同时兼容 `post.category_name`（列表 API）和 `post.category.name`（详情 API）两种数据结构，提升组件复用性。

## 5. 修改文件

- `miniprogram/components/post-card/post-card.wxss`（完全重写）
- `miniprogram/components/post-card/post-card.wxml`（完全重写）
- `miniprogram/components/post-card/post-card.ts`（新增 `mapCategoryToClass` 函数与 `categoryClass` data 字段）
- `miniprogram/pages/home/home.wxss`（完全重写）
- `miniprogram/pages/home/home.wxml`（完全重写）
- `AIwork/小程序首页与post-card组件水墨风重写任务报告.md`（新增任务报告）

## 6. 影响范围

- **小程序首页**（`pages/home/`）：视觉风格全面水墨化，底部导航从 5 项（含搜索）改为 4 项，搜索入口上移至顶部栏。
- **post-card 组件**（`components/post-card/`）：视觉风格水墨化，分类标签支持 7 类色板动态渲染，统计区改用 DIN 字体。该组件被首页使用，间接影响所有使用 post-card 的页面（如需后续扩展）。
- **不影响**：`app.json`、`app.wxss`、后端代码、Web 前端、其他小程序页面。

## 7. 测试与验证

**未运行自动化测试**，原因如下：
1. 本次任务为小程序 UI 视觉重写，属于纯样式与模板调整，不涉及业务逻辑变更。
2. 小程序端无单元测试覆盖（项目测试集中在后端 `pytest` 与 Web 前端 `playwright`）。
3. `home.ts` 与 `post-card.ts` 的逻辑变更仅为新增 `categoryClass` 计算函数，对原有数据流无影响。

**静态验证已完成**：
- 确认 `app.wxss` 已定义所有使用的 CSS 变量与分类色板类（`.cat-food` 等 7 类）。
- 确认 `home.wxml` 引用的所有方法（`goToHome/goToSearch/goToTopics/goToMap/goToPublish/goToProfile/onCategoryTap/onPostTap`）在 `home.ts` 中均有定义。
- 确认 `post-card.wxml` 引用的 `categoryClass` 在 `post-card.ts` 的 `data` 中已初始化。
- 确认 `mapCategoryToClass` 函数对所有 7 类分类名正则匹配正确，default 兜底。

**建议后续**：在微信开发者工具中手动编译预览，确认首页与 post-card 视觉效果符合预期；如条件具备，可启动后端用真实数据进行联调验证。

## 8. 后续建议

1. **小程序其他页面水墨化**：当前仅完成首页与 post-card，建议后续按相同设计系统重写发布页、详情页、个人中心、地图页等，保持视觉统一。
2. **分类名映射完善**：`mapCategoryToClass` 的正则规则基于常见中文分类名，若后端分类名调整，需同步更新映射规则；可考虑后端在分类 API 直接返回 `color_class` 字段，前端免映射。
3. **底部导航复用**：浮动胶囊式底部导航可抽取为独立组件 `components/tab-bar/`，供首页、地图页、个人中心页等共享，避免重复实现。
4. **小程序端测试体系建设**：建议引入小程序自动化测试（如 miniprogram-automator），覆盖关键页面渲染与交互。
5. **发布按钮凸出量微调**：当前 `margin-top: -36rpx`，可在真机预览后根据视觉效果微调凸出高度。
