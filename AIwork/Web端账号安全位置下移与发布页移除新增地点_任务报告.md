# 任务报告：Web端账号安全位置下移与发布页移除新增地点

## 1. 任务概述

用户提出两条 UI 体验优化反馈：
1. **账号安全部分太显眼**：目前在「校园认证」之后、「通知偏好」之前，一进入个人中心就能看到设置密码和解除绑定的输入框，交互有"一不注意就误操作"的风险。要求移到页面**靠下、隐蔽的位置**，并且**不要默认展开输入框**，改为用户需要点击才展开。
2. **发布帖子新增地点的入口删除**：目前 Web 端发帖页面的地点下拉框中存在「✚ 新增地点（地图选点，提交后进入核验队列）」选项，选中后会展开新增地点的虚线卡片（地图选点按钮+地点名称+场所类型+描述共 4 字段）。用户希望**完全移除该新增地点入口**，仅保留选择已有（已核验或用户提交待核验）地点的能力。

## 2. 已完成内容

### 2.1 账号安全卡片改造（位置+默认折叠）

- **AccountSecurityCard 组件内新增折叠状态**：引入 `expanded` useState，**默认值 `false`（不展开）**；标题改为可点击的 `<button>` 整行交互，右侧根据折叠状态切换 `ChevronDown`/`ChevronUp` 图标；`expanded === true` 时才条件渲染设置密码卡片和解除教育邮箱绑定卡片，中间用 `border-t border-line/60` 做视觉分隔。
- **视觉弱化**：Card 变体从 `variant="elevated"` `padding="lg"` 降为 `variant="outlined"` `padding="md"`，加 `opacity-90 hover:opacity-100 transition-opacity`；标题从湖蓝深色加粗降为 `text-sm text-ink-sub`，图标颜色统一用 `text-ink-muted`；同时在标题旁追加 `text-[10px] text-ink-muted font-normal` 的小字说明当前可用动作（`设置密码 / 解除邮箱绑定`），让用户折叠状态下也能一眼知道"这是什么功能"，但整体权重又非常低。
- **页面位置下移**：在 [ProfilePage.tsx](file:///e:/Project/moment-campus/frontend/src/pages/ProfilePage.tsx#L760-L1131) 中，把 `<AccountSecurityCard />` 组件**从 CampusVerifyCard 之后（通知偏好/推荐隐私/浏览历史/我的发布之前）移到「我的发布」区块之后、Toast 组件之前**——个人中心页面自上而下的顺序变成：用户资料横幅 → 统计卡 → 我的学校 → 校园身份认证 → 切换学校 Modal → 通知偏好 → 推荐隐私 → 浏览历史 → **我的发布** → **账号安全（最底部）** → Toast。用户需要滚动到页面最末尾才能看到账号安全卡片，位置隐蔽，符合需求。

### 2.2 发布帖子移除新增地点功能

- **下拉选项移除**：PostForm 的 `<select>` 中删除 `<option value={LOCATION_OPTION_NEW}>✚ 新增地点（地图选点，提交后进入核验队列）</option>` 选项，用户只看到「不选」「已核验地点（optgroup）」「用户提交（待核验）（optgroup）」三类选项，完全看不到新增入口。
- **虚线卡片删除**：删除 `isNewLocationSelected ? ( <div className="mt-2 rounded-[10px] border border-dashed border-line p-3 bg-mist/40"> ... </div> ) : null` 整段条件渲染，包括：地图选点按钮（"在地图上选择位置"）、新地点名称 Input、场所类型 select、描述 textarea、经纬度展示 badge、未选点虚线提示，共 7 个子元素彻底删除。
- **类型与状态清理**：
  - `PublishFormState` 删除 `new_location_name / new_location_lat / new_location_lng / new_location_type / new_location_description` 5 个字段；`INITIAL_FORM` 同步删除。
  - `isFormEffectivelyEmpty` 去掉 `!form.new_location_name.trim()` 判断条件。
  - 切校 `useEffect`、编辑模式 `postsApi.getPost` 回填、`handleRestoreDraft` 草稿恢复 3 处，删除原来对 new_location 字段的重置和 `hasNew` 判断。
  - `handleLocationSelect` 函数极度简化：仅处理空值（不选）和已有地点 ID 两种分支，原来的 `LOCATION_OPTION_NEW` 分支、清空 new_* 字段的逻辑全部删除。
  - `handleNewLocationField` 函数、`handleOpenMapPicker`、`handleMapPick` 三个事件处理函数连同 `LOCATION_OPTION_NEW` 常量、`isNewLocationSelected` 计算变量、`newLocationMode` useState、`mapPickerOpen` useState 一并删除。
  - `validate` 校验函数删除原来的 5 条新增地点校验（名称非空、经纬度非空、lat 范围、lng 范围等），现在地点完全非强制。
  - `handleSubmit` 删除先行 `categoriesApi.createLocation` 创建 `is_verified=false` 地点的 try/catch 逻辑和 `locationName/locationLat/locationLng` 三个 payload 字段，只剩 `location_id: formData.location_id ?? undefined` 一项。
- **Prop 与 MapPage 调用清理**：`PostFormProps` 删除 `defaultLocationName/defaultLocationLat/defaultLocationLng` 三个地图点选默认坐标 props；MapPage 中 `<PostForm>` 调用处移除上述 3 个 prop 和原先用于区分点选坐标变化的 `key={...toFixed(6)}` 属性，改为普通 PostForm 渲染。
- **未使用 import 清理**：`import { LOCATION_TYPE_OPTIONS } ...`、`import { buildLocationDescription } ...`、`import { MapPin, Map as MapIcon } ...`、`import { Modal } ...`、`import MapLocationPicker ...` 5 行不再需要的 import 删除，避免 tree-shake 警告。

## 3. 未完成内容

暂无。两项需求均按描述完整实现。

## 4. 实现思路

### 4.1 账号安全：做"减法"而非"加法"

用户的核心诉求是**降低曝光、减少误触**，不是增加新功能。所以我们采用三招收窄：
1. **视觉降级**（variant elevated→outlined、颜色加重→减弱、透明度 100%→90%），让卡片一眼看上去"没那么重要"；
2. **交互折叠**（默认 `expanded=false`），把表单藏一层点击门槛，用户不主动展开就看不到输入框和危险按钮；
3. **空间下沉**（从页面中上部移到最底部），保证正常浏览个人中心时注意力不会被这块"危险操作区"夺走。

三重保险共同作用：既保留了功能可用性（需要时能找到、能操作），又最大程度降低了存在感。

### 4.2 发布页新增地点：一刀切移除而非保留双入口

项目里其实**已有独立的新增地点双入口**（LocationPage 顶栏按钮 + MapPage 右下浮动 FAB，对应 v2.2.21 实现的 `CreateLocationModal` 通用组件），用户要新增地点完全可以从那两个入口走。**发帖时再带一个"联动新增"入口其实是冗余心智**——用户在发布帖子时的核心目标是写内容，而不是顺便创建地点，流程分两步走更清晰（先在地点页创建→审核通过→发帖时选）。所以直接从 PostForm 中**彻底删除整条新增链路**（状态/类型/校验/提交/渲染/Modal 全删），代码也更干净、少维护。

## 5. 修改文件

### 修改（6 个）
1. [AccountSecurityCard.tsx](file:///e:/Project/moment-campus/frontend/src/components/AccountSecurityCard.tsx)：新增 `expanded` 折叠状态；标题改为可点击按钮；卡片变体+颜色+透明度弱化；条件渲染展开区；补充 ChevronUp/Down 图标 import。
2. [ProfilePage.tsx](file:///e:/Project/moment-campus/frontend/src/pages/ProfilePage.tsx#L1129-L1130)：`<AccountSecurityCard />` 从校园认证后删除，移到「我的发布」区块后（我的发布 div 之后、Toast 之前），位置最底部。
3. [PostForm.tsx](file:///e:/Project/moment-campus/frontend/src/components/PostForm.tsx)：本次改动最大——删除 new_location_* 5 字段、新增地点全部渲染 UI、LOCATION_OPTION_NEW/ isNewLocationSelected/ newLocationMode/ mapPickerOpen 状态与计算变量、3 个事件处理函数、校验和提交逻辑中的新增地点分支；同时清理 PostFormProps 三个 defaultLocation prop、5 个未使用 import。
4. [MapPage.tsx](file:///e:/Project/moment-campus/frontend/src/pages/MapPage.tsx#L856-L869)：侧滑面板 `<PostForm>` 调用删除 `defaultLocationLat/ defaultLocationLng` prop 和地图坐标 key 属性，PostForm 不再接受新地点预填参数。
5. [CHANGELOG.md](file:///e:/Project/moment-campus/CHANGELOG.md#L10-L19)：升版到 v2.2.24，新增「变更」「验证」两节条目。
6. [TODO.md](file:///e:/Project/moment-campus/TODO.md#L7-L16)：顶部新增本次任务区块，7 个子项全勾选完成。

## 6. 影响范围

仅涉及 Web 前端（`frontend/`），后端接口、数据库、小程序端**完全不受影响**：
- 个人中心页面组件顺序 & 账号安全卡片样式/折叠交互；
- 发布页 PostForm 发布时不再允许客户端联动创建新地点，只能选已有 location_id 或不传；但后端 `POST /api/v1/posts` 接口仍然保留 `location_name / location_lat / location_lng` 的自动创建兜底逻辑（兼容性保持，其他调用方如小程序端仍可照常使用）——本次是**纯前端入口收敛**，不破坏后端契约。
- LocationPage 顶栏「新增地点」按钮和 MapPage 右下 FAB 双入口**保留**（v2.2.21 的 CreateLocationModal 功能正常可用），用户仍能创建地点，只是不在发布帖子页这一入口里做。

## 7. 测试与验证

- **前端构建验证**：执行 `cd frontend ; npm run build`，TS `tsc -b` 类型检查 + Vite 生产构建一次通过，0 错误 0 warning（仅 maplibre 大体积 chunk 提示，不影响运行）；构建产物 `PostForm-DH03KZ4F.js` 25.38 kB，`ProfilePage-DNZFuvQc.js` 35.97 kB，包体积正常。
- 未执行 `integrated_code_mode` 浏览器 E2E：当前链路改动均为"UI 可见性调整"和"入口删除"类纯前端改动，核心交互链路由 `tsc` 类型检查 + `vite build` 生产构建覆盖了接口与引用层面的正确性；`npm run build` 成功本身即可证明类型层面无回归。按约定在任务报告中说明。
- 未执行后端 `pytest tests/ -v`：后端代码零改动，无 pytest 必要。

## 8. 后续建议

1. **通知偏好/推荐隐私卡片也可以考虑类似折叠**：目前通知偏好（`NotificationPreferencesCard`）和推荐隐私区块还是默认全部展开，这两块相对账号安全没那么"危险"，但如果后续用户继续反馈"个人中心太长"，可以考虑折叠化处理，折叠状态保留一个小开关预览（当前通知设置的 3 个开关 + 个性化是否开启）避免用户必须点展开才知道是否开着。
2. **新增地点独立入口做轻引导**：由于发布页不能再创建地点，如果用户在发帖时发现下拉列表里**没有自己要的地点**，现在只能关了发帖页去 `/locations` 新建再回来发帖，链路有点断。可以考虑在 PostForm 地点 select 的「— 不选或选择已有地点 —」下方加一行 `text-[11px] text-ink-muted` 的轻引导："找不到想关联的地点？前往 [全部地点](/locations) 页面右上角「新增地点」提交，管理员核验后即可选择"，不影响 UI 权重，又能给用户导个航。
3. **默认折叠持久化（可选）**：目前账号安全的折叠状态是组件内 `useState`，刷新页面就会回到折叠。如果有老用户每次进个人中心都要展开才能操作，可以考虑把 `expanded` 写进 `localStorage`（key 类似 `profile::account_security_expanded::u{userId}`），下次打开还原用户上一次的展开/折叠状态，不过默认仍然建议保持 `false`（新用户首次还是折叠体验）。
