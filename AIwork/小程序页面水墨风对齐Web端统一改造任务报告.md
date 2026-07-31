# 任务报告：小程序页面水墨风对齐 Web 端统一改造

## 1. 任务概述

依据 [小程序页面设计对齐Web端-水墨风统一改造计划.md](../.trae/documents/小程序页面设计对齐Web端-水墨风统一改造计划.md) v5，对 `miniprogram/` 全部 14 个页面与 4 个公共组件进行水墨风统一改造。目标是将小程序视觉系统与 Web 端 `frontend/src/` 设计系统对齐，做到"同一套设计的双端实现"，而非"风格接近"。采用 design-taste-frontend skill 的 Redesign-Preserve 方法论：保留全部路由、业务功能、API 调用与 store 结构，仅对齐视觉系统。

## 2. 已完成内容

### 2.1 公共组件（4 个）
- **icon 组件**：基于 base64 SVG mask 实现 20+ 图标（search/x/mail/lock/arrow-left/upload/chevron-down/sparkles/school/bookmark/file-text/home/map/plus-circle/user/message-circle/alert-circle/heart/check-circle/eye/trash2/edit/bell/camera/log-out 等），统一替换全部页面的文字符号与几何符号
- **skeleton 骨架屏组件**：支持 post-card / line / avatar 变体，对齐 Web 端 Loading 组件的占位形态
- **empty-state 空状态组件**：icon + title + hint + action 结构，对齐 Web 端 EmptyState
- **post-card 组件**：分类色板圆点、DIN 数字统计、图片九宫格、状态徽标，对齐 Web 端 PostCard

### 2.2 全部 14 个页面改造
| 页面 | 改造要点 |
| --- | --- |
| home | 顶部栏新增校名 + slogan"把会消失的校园经验留下来"；新增"为你推荐"区块标题（sparkles icon）；骨架屏 + 空状态 |
| post-detail | 状态徽标 6 态配色、协同验证区块、评论列表 icon 化 |
| profile | 用户卡渐变背景 + 头像环；4 列统计卡 + icon 框；浏览历史/订阅管理/身份管理/设备管理模块补齐；退出登录 |
| login | 品牌区（logo"此"字 + "欢迎回来"标题 + slogan）；微信/邮箱双 Tab；icon 输入框；"忘记密码"+"以访客身份继续浏览" |
| search | icon 搜索框 + 清除按钮；模式 Tab 激活态 lake 填充；AI 卡片 lake 底色 + sparkles；骨架屏 + 空状态；结果卡片复用 post-card |
| publish | 分类色板圆点替代 emoji；upload/x/map-pin icon 替代文字符号；AI 助手按钮对齐 Web |
| edit-post | 同 publish 改造；分类色点 + 骨架屏 + 空状态 |
| notifications | 通知类型映射 icon；未读色条；骨架屏 + 空状态；hover 态 |
| map | 几何符号（⊙ ! ✕ ›）替换为 icon；hover 态；callout 颜色对齐 token |
| topics | 骨架屏 + 空状态 + icon meta 项 |
| topic-detail | 骨架屏 + 空状态；封面图 + 关联帖子 |
| subscriptions | 订阅类型映射 icon；骨架屏 + 空状态 |
| bind-account | 水墨风改造；icon 化；picker 显示逻辑修复；学校选择修复 |
| school-select | 骨架屏 + 空状态 + location/check icon |

### 2.3 统一文案对齐
- Login 标题统一为"欢迎回来"，slogan 统一为"把会消失的校园经验留下来"
- 注册链接统一为"还没有账号？立即注册"
- 空结果统一为"没有找到相关内容"
- 没有更多统一为"没有更多了"（删除 em-dash）

### 2.4 Pre-Flight Check 修复
- 修复 `map.ts` 中 callout 颜色 `#333333`/`#ffffff` 为 token 色值 `#152629`（ink）/ `#fafcfb`（paper）
- 全量扫描确认无 em-dash（—/–）、无几何符号（✕○⊙▾×✓›）

### 2.5 WXSS 编译错误修复（全方位排查）
微信小程序 WXSS 不支持 `mask-image` / `-webkit-mask-image` / `backdrop-filter` / `-webkit-backdrop-filter` 等属性，导致编译报错。本次全方位排查修复：

- **icon 组件重构**：从 `mask-image + currentColor` 方案改为 `<image src="data:image/svg+xml;base64,...">` 方案
  - 新增 `miniprogram/components/icon/._gen.cjs` 脚本：解码原 `icon.wxss` 中的 41 个 base64 SVG，提取内部路径，生成新的 `icon.ts`（含 `ICON_PATHS` 映射 + `buildSvgSrc()` 动态注入颜色）
  - `icon.wxml` 改为 `<image mode="aspectFit">` 渲染
  - `icon.wxss` 精简为 `.icon { display: inline-block; vertical-align: middle; }`
  - 41 个图标完整覆盖：home/map/plus-circle/user/bell/menu/heart/message-circle/eye/map-pin/clock/sparkles/check-circle/x/alert-circle/file-text/edit/send/trash2/log-out/log-in/user-circle/camera/refresh-cw/star/shield/school/mail/message-square/calendar/search/chevron-right/bookmark/settings/more-horizontal/thumbs-up/info/lock/arrow-left/upload/chevron-down
- **home.wxss 修复**：移除 `.tab-bar` 的 `backdrop-filter: blur(20rpx)` 和 `-webkit-backdrop-filter: blur(20rpx)`（WXSS 不支持）
- **tsconfig.json 修复**：移除 `types: ["miniprogram-api-typings"]` 配置（该包不在 typeRoots 指定的 `./typings` 或 `./node_modules/@types` 目录下，本地 `./typings` 已含完整 wx 类型定义）
- **全量扫描确认**：除 `._gen.cjs` 脚本本身外，小程序目录无任何 `mask-image` / `-webkit-mask-image` / `backdrop-filter` / `-webkit-backdrop-filter` / `filter:` / `clip-path:` 引用

## 3. 未完成内容

- 微信开发者工具 `simulator_refresh` 实机编译验证未执行（当前环境未安装 wechatide CLI，需用户在微信开发者工具中手动验证）
- 小程序实机截图对比 Web 端视觉未执行（需用户在微信开发者工具中截图）
- 小程序 E2E 自动化测试未执行（需前后端启动 + 微信开发者工具联调）

## 4. 实现思路

采用 design-taste-frontend skill 的 **Redesign-Preserve 模式**：

1. **Design Read**：读取 Web 端 `MobileNav.tsx` + `max-w-2xl mx-auto` 容器为移动优先设计，小程序应直接复用其布局结构、色彩、字体、组件视觉
2. **Three Dials**：DESIGN_VARIANCE=5（trust-first 居中容器）、MOTION_INTENSITY=3（信息消费类微动画）、VISUAL_DENSITY=5（中等密度）
3. **保留不可改**：全部 14 页路由、API endpoint、store 结构、type 定义、业务逻辑（6 态状态机、2 类协同验证、RBAC 权限矩阵）
4. **视觉系统复用**：直接使用 Web 端 Brand Tokens（五级墨/宣纸/lake/lamp/grass/sun + 楷书 display + 苹方 body + DIN data），app.wxss 已在 v4 Phase A 对齐
5. **Pre-Flight Check 门禁**：每页改造后机械扫描 em-dash / 灰色通用色 / 文字符号，零容忍

改造以"页面为单位、逐页对照 Web 端组件"的方式推进，文字符号统一替换为 icon 组件，加载态统一替换为骨架屏，空态统一替换为 empty-state 组件，确保双端视觉一致。

## 5. 修改文件

### 新增文件
- `miniprogram/components/icon/` （icon.wxml / icon.wxss / icon.json / icon.ts / ._gen.cjs 生成脚本）
- `miniprogram/components/skeleton/` （skeleton.wxml / skeleton.wxss / skeleton.json / skeleton.ts）
- `miniprogram/components/empty-state/` （empty-state.wxml / empty-state.wxss / empty-state.json / empty-state.ts）
- `AIwork/小程序页面水墨风对齐Web端统一改造任务报告.md`（本报告）

### 修改文件（14 页面 + post-card 组件 + 配置修复）
- `miniprogram/components/post-card/` （json/wxml/wxss）
- `miniprogram/pages/home/` （json/wxml/wxss）
- `miniprogram/pages/post-detail/` （json/ts/wxml/wxss）
- `miniprogram/pages/profile/` （json/ts/wxml/wxss）
- `miniprogram/pages/login/` （json/wxml/wxss）
- `miniprogram/pages/search/` （json/wxml/wxss）
- `miniprogram/pages/publish/` （json/ts/wxml/wxss）
- `miniprogram/pages/edit-post/` （json/ts/wxml/wxss）
- `miniprogram/pages/notifications/` （json/ts/wxml/wxss）
- `miniprogram/pages/map/` （json/ts/wxml/wxss）
- `miniprogram/pages/topics/` （json/wxml/wxss）
- `miniprogram/pages/topic-detail/` （json/wxml/wxss）
- `miniprogram/pages/subscriptions/` （json/ts/wxml/wxss）
- `miniprogram/pages/bind-account/` （json/ts/wxml/wxss）
- `miniprogram/pages/school-select/` （json/wxml/wxss）
- `miniprogram/tsconfig.json` （移除错误的 types 配置，修复 TypeScript 类型解析）
- `miniprogram/components/icon/icon.ts` / `icon.wxml` / `icon.wxss` （重构为 image + SVG data URI 方案）

## 6. 影响范围

- **小程序前端**：全部 14 个页面 + 4 个公共组件视觉系统统一改造，不影响业务逻辑与 API 调用
- **Web 前端**：无改动（`npm run build` 通过，验证未受影响）
- **后端**：无改动（`pytest tests/ -v` 936 passed，验证未受影响）
- **数据库**：无改动
- **配置**：无改动

## 7. 测试与验证

### 7.1 Pre-Flight Check 机械扫描
- em-dash（—/–）扫描：14 页面 0 匹配 ✅
- 几何符号（✕○⊙▾×✓›）扫描：14 页面 0 匹配 ✅
- 灰色通用色扫描：发现 map.ts 中 `#333333`/`#ffffff`，已修复为 token 色值；其余 `#fff` 均为深色背景上的白色文本（合法）✅

### 7.2 TypeScript 编译验证
- `npx tsc --noEmit`：icon.ts 编译通过 ✅
  - 修复 `tsconfig.json` 中 `types: ["miniprogram-api-typings"]` 配置错误（该包不在 typeRoots 路径下，本地 `./typings` 已含完整 wx 类型定义）
  - 剩余错误均为预先存在的代码问题（services/*.ts 的 URLSearchParams、request.ts 类型不匹配等），与本次 icon 组件重构无关

### 7.3 后端测试
- `pytest tests/ -q`：**936 passed, 79 skipped, 0 failed**（769.11s）✅

### 7.4 前端构建
- `npm run build`：成功，1.87s 构建完成 ✅

### 7.5 未执行测试及原因
- **微信开发者工具 simulator_refresh**：当前环境未安装 wechatide CLI，需用户在微信开发者工具中手动打开 `miniprogram/` 项目编译验证
- **小程序 E2E 自动化测试**：需前后端启动 + 微信开发者工具联调，且小程序 E2E 依赖实机/模拟器环境，本次未执行

## 8. 后续建议

1. **用户手动验证**：在微信开发者工具中打开 `miniprogram/` 项目，编译并逐页截图对比 Web 端，确认视觉一致性；重点验证 icon 组件在 `<image mode="aspectFit">` 渲染下的颜色注入是否符合预期
2. **icon 组件补全**：若实机发现有 icon name 未覆盖，可在 `icon.ts` 的 `ICON_PATHS` 映射中追加新条目（inner SVG 内容从 lucide-react 源码或 `._gen.cjs` 脚本扩展获取）
3. **实机性能验证**：在真机上验证骨架屏动画、stagger-card 进场动画的流畅度，必要时降级 MOTION_INTENSITY
4. **小程序 E2E 测试**：待微信开发者工具 CLI 联调通后，补充登录/发布/协同验证/权限校验等关键链路的自动化测试
5. **Profile 模块验收**：逐模块（浏览历史/订阅管理/身份管理/设备管理/通知偏好）对照 Web ProfilePage 截图验收
6. **预先存在的 TypeScript 错误**：services/*.ts 中 `URLSearchParams` 未定义（需在 tsconfig lib 中添加 `DOM` 或改用 wx 提供的 querystring 方案）、request.ts 中 method 类型不匹配等，建议后续单独修复
