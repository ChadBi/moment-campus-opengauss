# 任务报告：UI 组件手绘水墨风改造

## 1. 任务概述

重新设计 `frontend/src/components/ui/` 下的 8 个 UI 组件，使其符合手绘水墨风格。设计参考来自根目录 Demo 样式与已更新的 Tailwind 配置（新色系：lake / lamp / grass / sun / ink / paper / mist / line 等，字体 font-display / font-sans / font-data，圆角与阴影令牌）。

要求保持所有组件的 props 接口不变，仅修改样式实现。

## 2. 已完成内容

### Button.tsx
- primary：灯笼橙 `bg-lamp` + 白字 + `shadow-lamp` + hover `translateY(-2px)`
- secondary：雾色 `bg-mist` + 湖蓝字 + hover 上浮
- text：透明底 + 湖蓝字 + hover 浅雾色背景
- danger：危险红 `bg-danger` + 白字 + hover 上浮
- 圆角 `rounded-md`(14px)，过渡 `transition-[transform,...] duration-[180ms] ease-out`
- 尺寸微调（md 高度 44px），保持 sm/md/lg 三档

### Card.tsx
- elevated：`bg-paper/86` 半透明白底 + 白色边框 + `shadow-lg` + `backdrop-blur-xl` + `rounded-xl`(28px)
- outlined：白底 + `border-line` + `rounded-lg`(20px)
- filled：雾色底 + `rounded-lg`
- hover `translateY(-2px)` + shadow，统一过渡

### Input.tsx
- 高度 `h-11`(44px)，圆角 `rounded-[13px]`
- 半透明白底 `bg-white/78`
- focus：白底 + 湖蓝边框 + `shadow-sm`
- 错误态 `border-danger`，label/星号/错误文案使用 ink/danger 色

### Badge.tsx
- 圆角 `rounded-full`(999px)
- `font-data` 字体、`text-[11px]`、`tracking-wide`
- 五种 variant 配色（default/success/warning/danger/info）使用功能色半透明底

### Avatar.tsx
- 圆角 `rounded-md`(14px) 非圆形方圆角
- 默认雾色底 `bg-mist` + 湖蓝字 `text-lake`
- 加 `ring-1 ring-line` 描边，图片与 fallback 样式一致

### Modal.tsx
- 遮罩 `bg-[rgba(16,35,39,0.46)]` + `backdrop-blur-[8px]`
- 模态框纸张白底 `bg-paper` + `rounded-xl`(28px) + `shadow-xl` + `animate-modal-in`
- 标题用 `font-display` 楷体，关闭按钮 hover 湖蓝

### Toast.tsx
- 固定底部居中 `fixed bottom-6 left-1/2 -translate-x-1/2`
- 深墨色底 `bg-ink` + 白字 + `rounded-md`(14px) + `shadow-lg` + `animate-fade-in`
- 类型图标保留（success=grass / error=danger / warning=sun / info=lamp）

### Loading.tsx
- 湖蓝色旋转图标 `text-lake`
- fullScreen 背景改为 `bg-mist/80 backdrop-blur-sm`
- Skeleton 颜色由 gray-200 改为 `bg-mist`、`rounded-md`

### 其他
- 更新 `TODO.md`：追加 2026-06-26 更新日志，更新顶部"最后更新"日期

## 3. 未完成内容

暂无。

## 4. 实现思路

1. 先读取 `tailwind.config.js`、`index.css`、`styles/tokens.ts` 确认可用的色系/字体/圆角/阴影/动画令牌，避免使用未定义的类名。
2. 逐个读取 8 个组件现有实现，确保 props 接口与导出名保持不变（`index.ts` 未改动）。
3. 严格按照任务给出的视觉规格映射到 Tailwind 类：
   - 颜色用配置中已定义的语义名（`lake`/`lamp`/`mist`/`paper`/`ink`/`line`/`danger`/`grass`/`sun`/`info`），半透明用 `/NN` 修饰符或 `bg-[rgba(...)]` 任意值。
   - 圆角用 `rounded-md`(14px) / `rounded-lg`(20px) / `rounded-xl`(28px) / `rounded-full` / `rounded-[13px]`。
   - 阴影用 `shadow-sm/md/lg/xl/lamp/lake`。
   - 字体用 `font-display`/`font-sans`/`font-data`。
   - 动画用配置中已定义的 `animate-fade-in` / `animate-modal-in`。
4. 过渡动画统一用 `transition-[transform,...] duration-[180ms] ease-out`，hover 上浮统一 `-translate-y-0.5`(= -2px)。
5. 验证：`npx tsc -b`（仅 MapPage.tsx 有预先存在的未使用导入错误，与本次改动无关）、`npx eslint src/components/ui`（0 错 0 警）、`npx vite build`（构建成功 `✓ built in 3.08s`）。

## 5. 修改文件

- `frontend/src/components/ui/Button.tsx`
- `frontend/src/components/ui/Card.tsx`
- `frontend/src/components/ui/Input.tsx`
- `frontend/src/components/ui/Badge.tsx`
- `frontend/src/components/ui/Avatar.tsx`
- `frontend/src/components/ui/Modal.tsx`
- `frontend/src/components/ui/Toast.tsx`
- `frontend/src/components/ui/Loading.tsx`
- `TODO.md`（仅更新日志与日期）

> 说明：`frontend/tailwind.config.js`、`frontend/src/index.css`、`frontend/src/styles/tokens.ts` 在本次任务开始前已被更新（与任务描述"已更新的 Tailwind 配置"一致），本次未改动。

## 6. 影响范围

- UI 基础组件层：所有引用 `components/ui` 的页面与业务组件的视觉表现会变化（配色、圆角、阴影、字体），但 API 接口零变更，无需调用方改代码。
- 主要受影响模块：地图页、首页、登录/注册、发布、详情、个人中心、管理后台、通知、搜索等所有使用 Button/Card/Input/Modal/Toast/Loading/Badge/Avatar 的页面。
- 类型与导出未变，`index.ts` 未改动，构建产物正常。

## 7. 测试与验证

1. **TypeScript 类型检查** `npx tsc -b`：UI 组件目录无任何报错；唯一报错为 `src/pages/MapPage.tsx(5,10): error TS6133: 'MapPin' is declared but its value is never read.`，该文件不在本次改动范围（git status 确认未修改），属预先存在的问题。
2. **ESLint 检查** `npx eslint src/components/ui`：exit code 0，0 错 0 警。
3. **生产构建** `npx vite build`：exit code 0，`✓ built in 3.08s`，所有 UI 组件成功打包。（控制台出现的 PLUGIN_TIMINGS / chunk size 提示为 vite 的警告信息，非错误。）
4. 未运行浏览器端可视化测试（本次仅做静态代码与构建验证），建议后续在浏览器中抽查各页面的视觉一致性。

## 8. 后续建议

1. **可视化抽查**：在 dev 服务器中逐页检查 Button/Card/Input/Modal/Toast 等组件的实际呈现，特别是半透明 + backdrop-blur 在不同背景下的效果。
2. **修复预先存在的 MapPage tsc 报错**：删除 `MapPage.tsx` 中未使用的 `MapPin` 导入，以恢复 `npm run build`（`tsc -b && vite build`）的完整链路。
3. **手绘风装饰元素**：可在后续为 Card/Modal 增加更明显的手绘质感（如轻微旋转、不规则边、墨迹装饰），进一步提升水墨风识别度。
4. **暗色模式**：当前配色基于纸张白底，如后续需要暗色模式，需补充对应色板。
5. **组件文档**：可为改造后的 UI 组件补充 Storybook 或示例页，方便设计走查。
