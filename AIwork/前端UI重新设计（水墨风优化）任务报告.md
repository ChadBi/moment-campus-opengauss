# 任务报告：前端UI重新设计（水墨风优化）

## 1. 任务概述

对整个项目前端进行全面的UI重新设计，保留并优化手绘水墨风格，解决过度使用圆角、帖子内部分割设计不合理、页面风格不统一等问题，提升整体视觉体验和一致性。

## 2. 已完成内容

- 建立完整的设计令牌系统（tokens.ts），规范色彩、字体、圆角、阴影
- 更新 Tailwind 配置，扩展水墨风主题
- 优化全局样式和宣纸纹理效果
- 重构所有 UI 基础组件（Button、Card、Badge、Input、Avatar、Modal、Toast、Table）
- 重构帖子详情页为长卷式布局，减少卡片碎片化
- 重构首页信息流，统一卡片样式与间距
- 调整 Header、MainLayout、Sidebar 等布局组件
- 更新登录、注册、发布等表单页，统一表单样式
- 更新个人中心、搜索、通知等列表页，标准化布局
- 更新地图页与侧边面板
- 统一 Admin 后台样式与设计系统
- TypeScript 编译通过，生产构建成功

## 3. 未完成内容

暂无

## 4. 实现思路

1. **设计系统先行**：首先建立统一的设计令牌（Design Tokens），定义五级墨色、宣纸底色、湖蓝/朱砂点缀色，规范圆角层级（6px/10px/16px/20px）替代之前的过度大圆角
2. **水墨风保留与增强**：保留楷体标题字体、宣纸纹理背景、墨线分割，通过微妙的阴影和色彩层次增强水墨质感
3. **长卷式布局**：帖子详情页从之前的6个碎片化卡片改为2个主卡片，用墨线分割内容区域，类似中国传统卷轴的阅读体验
4. **组件一致性**：所有 UI 组件使用统一的设计令牌，确保按钮、卡片、徽章、输入框等在全站风格一致
5. **渐进式更新**：从基础组件到页面，再到后台，分阶段逐步更新，确保每一步构建通过

## 5. 修改文件

### 设计系统
- `frontend/src/styles/tokens.ts` - 设计令牌定义
- `frontend/tailwind.config.js` - Tailwind 主题扩展
- `frontend/src/index.css` - 全局样式和纹理

### UI 组件
- `frontend/src/components/ui/Button.tsx`
- `frontend/src/components/ui/Card.tsx`
- `frontend/src/components/ui/Badge.tsx`
- `frontend/src/components/ui/Input.tsx`
- `frontend/src/components/ui/Avatar.tsx`
- `frontend/src/components/ui/Modal.tsx`
- `frontend/src/components/ui/Toast.tsx`
- `frontend/src/components/ui/Table.tsx`

### 布局组件
- `frontend/src/components/layout/Header.tsx`
- `frontend/src/components/layout/MainLayout.tsx`
- `frontend/src/components/layout/Sidebar.tsx`
- `frontend/src/components/layout/MobileNav.tsx`

### 页面组件
- `frontend/src/pages/PostDetailPage.tsx`（长卷式重构）
- `frontend/src/pages/HomePage.tsx`
- `frontend/src/pages/LoginPage.tsx`
- `frontend/src/pages/RegisterPage.tsx`
- `frontend/src/pages/PublishPage.tsx`
- `frontend/src/pages/ProfilePage.tsx`
- `frontend/src/pages/SearchPage.tsx`
- `frontend/src/pages/NotificationsPage.tsx`
- `frontend/src/pages/MapPage.tsx`
- `frontend/src/pages/admin/*`（所有后台页面样式统一）

### 文档
- `TODO.md` - 更新任务进度

## 6. 影响范围

- 全站所有前端页面和组件
- 视觉风格统一，交互体验一致
- 不影响后端 API 和业务逻辑
- 移动端响应式布局同步优化

## 7. 测试与验证

- `npm run build` 构建成功，TypeScript 类型检查通过
- 生产包大小正常（CSS ~39KB，主 JS ~272KB）
- 各页面组件样式统一应用新设计系统
- 保留了手绘水墨风格的核心元素（宣纸纹理、楷体标题、墨色层次）

## 8. 后续建议

- 可在实际设备上进行视觉验收，微调个别页面间距
- MapPage 代码块较大（~1MB），后续可考虑代码分割优化
- 可添加页面过渡动画增强体验
- 暗色模式（水墨夜色主题）可作为后续扩展
