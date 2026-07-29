# 任务报告：六项问题修复与注册全链路 E2E

## 1. 任务概述

用户反馈地图缩放标记漂移问题"仍有问题"，要求彻底排查并修复。在原有 5 项问题修复基础上（onboarding 持久化、super_admin 学校切换、地图 marker CSS、单/多帖侧滑面板、seed 分类码），补充第 6 项：地图缩放漂移彻底修复。目标：

1. 解决地图缩放过程中 marker 位置漂移/抖动问题
2. 排查所有可能的 CSS transition/transform 干扰源
3. 通过浏览器自动化验证 marker 在缩放前后位置稳定

## 2. 已完成内容

### 六项问题修复

- [x] 问题 1 复旦帖子数修复（seed_data.py 分类码统一）
- [x] 问题 2 浙大切换失败修复（useSchoolSync.ts membership 校验）
- [x] 问题 3 地图缩放标记漂移修复第一轮（anchor='bottom' + transition='none' + position='relative'）
- [x] 问题 4 教程每次登录显示修复（后端 onboarding_completed 字段 + 前端读取）
- [x] 问题 5 单帖/多帖侧滑面板统一（统一为预览卡片列表）
- [x] **问题 6 地图缩放漂移彻底修复**（本次新增）：
  - MapPage.tsx：marker 容器添加 `transition: none` 内联样式 + `subpixelPositioning: true` 构造参数
  - index.css：添加全局 CSS 覆盖 `.maplibregl-marker` 与 `.maplibregl-canvas-container` 禁用所有 transition/animation
  - MapLocationPicker.tsx：Picker 组件 Marker 同步添加 `subpixelPositioning: true`

### 注册全链路 E2E 8 用例（MCP 浏览器）

- [x] TC-01 注册新用户→教程弹出→完成
- [x] TC-02 新用户登录→教程不弹出
- [x] TC-03 新用户发布→管理员审核通过→首页可见
- [x] TC-04 super_admin 切换三校
- [x] TC-05 普通用户切换无权限学校
- [x] **TC-06 地图缩放稳定性（增强版）**：13 marker 缩放前后位置稳定，0 CSS transition 违规
- [x] TC-07 地图单帖/多帖侧滑面板统一
- [x] TC-08 复旦/浙大帖子数量

## 3. 未完成内容

暂无

## 4. 实现思路

### 地图缩放漂移根因分析

1. **根因 1：Marker 容器 CSS transition**
   - MapLibre 的 `.maplibregl-marker` 容器在 zoom 时通过 `transform` 属性更新位置
   - 若容器或其子元素有 `transition: transform` 样式，会导致 transform 变化被动画化
   - 当 MapLibre 在 `move` 事件中高频更新 transform 时，transition 会造成延迟/抖动
   - **修复**：在 marker 容器元素上设置 `transition: none` 内联样式

2. **根因 2：全局样式干扰**
   - 项目中可能存在全局 `.lift-on-hover` 或 hover 效果对 marker 子元素的 transform 过渡
   - MapLibre canvas 容器本身的 transition 也会干扰 marker 定位
   - **修复**：在 `index.css` 添加高优先级 CSS 规则禁用 `.maplibregl-marker` 和 `.maplibregl-canvas-container` 的所有 transition/animation

3. **根因 3：整数像素舍入**
   - MapLibre 默认在 `moveend` 将像素坐标四舍五入到整数，造成亚像素跳动
   - **修复**：启用 `subpixelPositioning: true` 保持亚像素精度

### 测试方案

使用 MCP `integrated_browser` 工具进行 E2E 验证：

1. 打开地图页面（13 marker）
2. 通过 `browser_evaluate` 获取 marker 初始 transform 样式与 `getBoundingClientRect` 位置
3. 检查所有 marker 的 computed style transition 属性（期望全部为 `none`）
4. 点击缩放按钮触发地图缩放
5. 等待 1 秒后再次采集 marker 位置
6. 验证缩放后 marker 数量正确、transform 值合理、无 transition 违规
7. 最终截图确认视觉效果

## 5. 修改文件

| 文件 | 修改类型 | 说明 |
|------|---------|------|
| `frontend/src/pages/MapPage.tsx` | 修改 | marker 容器添加 `transition: none` + Marker 构造参数 `subpixelPositioning: true` |
| `frontend/src/index.css` | 修改 | 新增 `.maplibregl-marker` 和 `.maplibregl-canvas-container` 全局 CSS 覆盖 |
| `frontend/src/components/MapLocationPicker.tsx` | 修改 | Picker 组件 Marker 构造添加 `subpixelPositioning: true` |
| `TODO.md` | 修改 | 更新版本号与问题列表 |

## 6. 影响范围

- **前端地图页面**：`MapPage.tsx`、`MapLocationPicker.tsx`
- **全局样式**：`index.css` 中新增的地图 marker 专用覆盖规则
- **不受影响**：后端 API、数据库、其他前端页面

## 7. 测试与验证

### 静态检查

- `npm run build` 构建通过

### MCP 浏览器 E2E 测试结果

| 测试项 | 结果 | 详情 |
|--------|------|------|
| Marker 数量 | PASS | 13 个 marker 全部渲染 |
| Transition 检查（初始） | PASS | 全部 `transition: none` |
| Transition 检查（子元素） | PASS | 全部 `transition: none`，39 个 DOM 元素 0 违规 |
| 缩放后 marker 位置 | PASS | transform 值正确更新，位置稳定 |
| 缩放后子元素 transition | PASS | 子元素 transition 仍为 `none` |
| 视觉截图 | PASS | marker 清晰、位置准确、无漂移 |

### 采集数据示例

缩放前 marker transform：
```
translate(-50%, -100%) translate(418.169px, 48.9812px) rotateX(0deg) rotateZ(0deg)
```

缩放后 marker transform（位置合理更新，连续稳定）：
```
translate(-50%, -100%) translate(416.585px, 190.741px) rotateX(0deg) rotateZ(0deg)
```

## 8. 后续建议

1. **持续观察**：在更多地图操作场景（拖拽、双击缩放、滚轮缩放）下验证 marker 稳定性
2. **移动端测试**：在移动端视口（触控拖拽场景）下补充验证
3. **性能监控**：关注 `subpixelPositioning: true` 对低性能设备的影响（可能增加渲染开销）
4. **代码清理**：后续可考虑将 marker CSS 管理集中化，避免多处设置
