# Web 端问题 3+4 修复设计：新增地点双入口 + 5 字段完整对齐

> 撰写日期：2026-08-08  
> 关联任务：修复 P3 体验差异（Web 端缺独立新增地点入口 + 新增地点表单缺类型/描述字段），对齐小程序端交互

## 1. 背景 & 问题定义

### 1.1 问题 3（入口缺失）
Web 端**只有通过发布页下拉选「✚ 新增地点」才能建点**，无独立入口。小程序端对应两处独立入口：
- 全部地点页（subpackages/pages/locations）右上角「新增地点」按钮
- 地图页（pages/map）工具栏进入 `mode=create` 的新建地点页

**后果**：用户只想建点、不发帖时找不到入口；Web 端用户必须绕到「发布页」才能完成独立建点，学习成本高。

### 1.2 问题 4（字段不完整）
Web 端发布页「✚ 新增地点」联动模式的表单只有 **3 个字段（名称 + 纬度 + 经度）**。小程序端独立新增地点流程有 **5 字段（含选点）**：
1. 地图选点（必填）
2. 地点名称（必填）
3. 场所类型（可选，枚举 7 种：教学楼/食堂/宿舍/运动场/服务点/公共空间/其他）
4. 描述文本（可选，maxlength=480，引导填「开放时间、使用规则、联系方式等」）
5. 提交按钮

**后果**：
- 两端信息质量不一致：Web 端新建的地点**缺少分类筛选维度**（type），无法在分类/类型下被搜到
- 描述文本里的「开放时间、使用规则、联系电话」无法在建点时一次录入，用户只能在地点详情页再走「补充/修改 → 稳定资料提议」流程，需要管理员二次审核，体验冗余

## 2. 用户决策汇总（2026-08-08 澄清问答）

### 2.1 入口范围（问题 3）
用户选 **C 方案 = 双入口**：
1. LocationPage（`/locations`）页头右侧「新增地点」按钮 → 对齐小程序 locations 页右上角按钮
2. MapPage（`/map`）地图容器**右下角浮动加号圆形 FAB** → 对齐小程序 map 页工具栏入口

### 2.2 字段完整度范围（问题 4）
用户选 **A 方案 = 两端都加完整字段**：
1. 独立弹窗（双入口点击后打开的新 Modal）：完整 5 字段（和小程序一致）
2. 发布页联动模式（PostForm 内的虚线卡片）：**在现有 3 字段基础上追加场所类型 select + 描述 textarea**，**不替换整体结构**（最小侵入，保已有草稿恢复/切校清空/发帖联动逻辑稳定）

### 2.3 技术方案
**方案 1（常量+工具函数复用，PostForm 内嵌轻改造）**，整体思路：
- 抽 1 份场所类型枚举常量 + 1 份描述拼接工具函数 → 三处 UI（独立弹窗×2 入口 + PostForm 联动模式）共同使用，保证 100% 一致性
- 新建 CreateLocationModal 组件给双入口复用（LocationPage/MapPage 各加 1 个 Modal open 状态即可）
- PostForm 内**只追加 2 个字段 + 1 处 description 提交 payload 拼接**，不替换内嵌虚线卡片整体结构，避免破坏已验证的复杂联动

## 3. 组件架构 & 文件清单

| 路径 | 类型 | 作用 |
|------|------|------|
| `frontend/src/constants/locationTypes.ts` | 新增 | 场所类型 7 枚举常量（与小程序 `LOCATION_TYPE_OPTIONS` 完全一致，SSOT） |
| `frontend/src/utils/buildLocationDescription.ts` | 新增 | `buildLocationDescription(type, description)` → 统一拼「场所类型：xxx\n描述正文」（与小程序 [locations.ts#L297-L301](file:///e:/Project/moment-campus/miniprogram/subpackages/pages/locations/locations.ts#L297-L301) 逻辑 100% 对齐） |
| `frontend/src/components/CreateLocationModal.tsx` | 新增 | 通用 5 字段 Modal（选点 + 名称 + 类型 + 描述 + 提交），LocationPage/MapPage 两处 import |
| `frontend/src/pages/LocationPage.tsx` | 修改 | 页头右侧加「新增地点」Button；import CreateLocationModal；加 `createModalOpen` state；权限拦截 |
| `frontend/src/pages/MapPage.tsx` | 修改 | 地图容器右下角加圆形浮动 FAB 加号；import CreateLocationModal；加 `createModalOpen` state；权限拦截 |
| `frontend/src/components/PostForm.tsx` | 修改 | PublishFormState 加 `new_location_type` + `new_location_description`；INITIAL_FORM + 切校清空 + 草稿恢复 hasNew 判断 + 丢弃草稿 4 处同步初始化；新增地点虚线卡片追加类型 select + 描述 textarea；提交 createLocation 时 payload 追加 description 字段 |
| `frontend/src/services/categories.ts` / `services/locations.ts` | 修改（若需要） | `CreateLocationRequest` 接口追加可选 `description?: string`（后端接口已支持，之前前端没传） |

## 4. 双入口 UI 详细设计

### 4.1 入口 ①：LocationPage（/locations）页头按钮
**位置**：[LocationPage.tsx#L237-L246](file:///e:/Project/moment-campus/frontend/src/pages/LocationPage.tsx#L237-L246) `<header className="mb-4 flex items-end justify-between gap-3">` 右侧天然空位。

**代码结构**：
```tsx
<header ...>
  <div>
    <h1>校园地点</h1>
    <p>全部地点 · 打印店 · 食堂 · 图书馆…</p>
  </div>
  {/* 新增：右侧「新增地点」按钮 */}
  <Button
    variant="primary"
    size="sm"
    icon={<Plus size={13} />}
    onClick={handleOpenCreate}
    className="h-[34px] px-3.5 text-[12px] gap-1 rounded-[9px]"
  >
    新增地点
  </Button>
</header>
```

**权限判断**（点击 handleOpenCreate 时）：
- `!isAuthenticated` → `navigate('/login')` + `showToast('登录后即可新增地点', 'info')`
- `isAuthenticated && !canCreateLocation`（canCreate = canWriteInCurrentSchool || admin/super_admin）→ `showToast('请先完成校园认证', 'warning')`，**不打开 Modal**
- 通过 → `setCreateModalOpen(true)`

### 4.2 入口 ②：MapPage（/map）右下浮动 FAB
**位置**：[MapPage.tsx](file:///e:/Project/moment-campus/frontend/src/pages/MapPage.tsx) 中 `relative flex-1 m-3 rounded-[23px] overflow-hidden border border-line shadow-md` 地图容器内部（与 `<div ref={mapContainer}>` 同级，地图覆盖层 z-index 之上但低于 Modal z=50）。

**样式与结构**：
```tsx
<div ref={mapContainer} className="w-full h-full" />
<div className="paper-noise" />
{/* 新增：右下角浮动加号 FAB */}
<button
  type="button"
  onClick={handleOpenCreateLocation}
  className="absolute bottom-5 right-5 z-[3] w-12 h-12 rounded-full bg-lake hover:bg-lake/90 text-white shadow-lg flex items-center justify-center transition-transform hover:scale-105 active:scale-95"
  aria-label="新增地点"
>
  <Plus size={20} strokeWidth={2.5} />
</button>
```

**Z-index 说明**：
- maplibregl NavigationControl（右下缩放/平移控件）默认 z-index 低，约 2
- FAB 设 `z-[3]` = 高于 NavigationControl 避免被盖住，但远低于 Modal `z-50`，Modal 打开时自然盖住 FAB

**权限同上：同入口 ①，点击时先校验**。

## 5. 5 字段表单详细对齐（CreateLocationModal + PostForm 联动）

### 5.1 5 字段顺序 & 校验（与小程序 [locations.wxml#L107-L145](file:///e:/Project/moment-campus/miniprogram/subpackages/pages/locations/locations.wxml#L107-L145) 一致）

| # | 字段 | 必填 | 组件 | 细节 |
|---|------|-----|------|------|
| 1 | **地图选点** | ✅ | `<MapLocationPicker>`（复用 PostForm 已验证的组件，独立 Modal 点击按钮开 Modal 内嵌 Picker，或直接在 CreateLocationModal 里渲染 Picker 区域——用后者更直接） | initialCenter = 当前学校 center_lat/center_lng；用户点击地图后 → 更新已选 badge「已选位置」+ 显示 lat,lng + 写入 state |
| 2 | **地点名称** | ✅ | `<Input>` | maxlength=100，placeholder="例如：南区便利店" |
| 3 | **场所类型** | ⭕ 可选 | `<select>`（或 `<Input label>` 封装的 select） | import `LOCATION_TYPE_OPTIONS` = ['教学楼','食堂','宿舍','运动场','服务点','公共空间','其他']，默认空值 placeholder = "场所类型（可选）" |
| 4 | **描述文本** | ⭕ 可选 | `<textarea>` | maxlength=480，rows=4，placeholder="地点描述（可选），可补充开放时间、使用规则、联系方式等" |
| 5 | **提交栏** | — | 左取消 / 右主按钮 loading 状态 | 成功回调独立 Modal = `showToast('地点已提交，等待核验', 'success') → closeModal → 可选打开地点详情页`；PostForm 联动 = `清空 2 个新字段` |

### 5.2 常量 & 工具函数实现

#### constants/locationTypes.ts：
```ts
/** 场所类型枚举（SSOT：Web 双入口 + PostForm 联动 + 小程序共用） */
export const LOCATION_TYPE_OPTIONS = [
  '教学楼',
  '食堂',
  '宿舍',
  '运动场',
  '服务点',
  '公共空间',
  '其他',
] as const;

export type LocationType = (typeof LOCATION_TYPE_OPTIONS)[number];
```

#### utils/buildLocationDescription.ts：
```ts
/**
 * 将「场所类型」前缀 + 描述正文 拼接为后端 description 字段
 * 与小程序 locations.ts#L297-L301 逻辑 100% 对齐：
 *  - 类型存在 → "场所类型：${type}"
 *  - 描述存在 → 换行追加
 *  - 两者都为空 → return undefined（后端 description 字段为可选，避免传空串）
 */
export function buildLocationDescription(
  locationType: string | null | undefined,
  description: string | null | undefined,
): string | undefined {
  const type = String(locationType || '').trim();
  const desc = String(description || '').trim();
  const parts: string[] = [];
  if (type) parts.push(`场所类型：${type}`);
  if (desc) parts.push(desc);
  const joined = parts.join('\n');
  return joined.length > 0 ? joined : undefined;
}
```

### 5.3 PostForm 虚线卡片追加 2 字段（最小侵入）

**PublishFormState 接口追加**（[PostForm.tsx#L69-L95](file:///e:/Project/moment-campus/frontend/src/components/PostForm.tsx#L69-L95)）：
```ts
new_location_type: string;           // 新增
new_location_description: string;    // 新增
```

**INITIAL_FORM 同步补 2 字段**（[PostForm.tsx#L86-L93](file:///e:/Project/moment-campus/frontend/src/components/PostForm.tsx#L86-L93)）：
```ts
new_location_type: '',
new_location_description: '',
```

**4 处初始化兜底全部补这两字段**：
1. getInitialForm()（defaultLocationLat/Lng 场景，[PostForm.tsx#L300-L304](file:///e:/Project/moment-campus/frontend/src/components/PostForm.tsx#L300-L304)）
2. 切校 useEffect 清空新地点字段处（[PostForm.tsx#L387-L394](file:///e:/Project/moment-campus/frontend/src/components/PostForm.tsx#L387-L394)）+ setNewLocationMode 后确保字段清空
3. handleDiscardDraft（getInitialForm() 会兜底，但若有显式写 new_location_* 也要补）
4. handleRestoreDraft 的 hasNew 判断要加这两字段（**避免「只填了类型/描述但没填名称 + 坐标」被误判为未进入新增地点模式导致跳回下拉空值 → 显示选不中**——这正是 PostForm 为什么专门加 `newLocationMode` 显式状态的原因）

**UI 追加位置**：[PostForm.tsx#L1403-L1428](file:///e:/Project/moment-campus/frontend/src/components/PostForm.tsx#L1403-L1428) 「新地点名称 Input」下方：
```tsx
<Input label="新地点名称" ... />  {/* 原有 */}
{/* 新增 2 字段 ↓↓↓ */}
<div className="mt-2">
  <label className={vs.label} htmlFor="post-new-location-type">
    场所类型 <span className="text-ink-muted text-xs">（可选）</span>
  </label>
  <select
    id="post-new-location-type"
    value={formData.new_location_type}
    onChange={(e) => handleNewLocationField('new_location_type', e.target.value)}
    className={vs.select}
  >
    <option value="">场所类型（可选）</option>
    {LOCATION_TYPE_OPTIONS.map((t) => (
      <option key={t} value={t}>{t}</option>
    ))}
  </select>
</div>
<div className="mt-2">
  <label className={vs.label} htmlFor="post-new-location-description">
    描述 <span className="text-ink-muted text-xs">（可选，480 字内）</span>
  </label>
  <textarea
    id="post-new-location-description"
    value={formData.new_location_description}
    onChange={(e) => handleNewLocationField('new_location_description', e.target.value)}
    maxLength={480}
    rows={3}
    placeholder="可补充开放时间、使用规则、联系方式等"
    className="w-full rounded-[10px] border border-line bg-paper px-3 py-2 text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-lake/30 resize-none"
  />
</div>
{/* 坐标 Badge / 未选点提示（原有的，不用动） */}
```

**handleNewLocationField 字段白名单扩充**（[PostForm.tsx#L605-L621](file:///e:/Project/moment-campus/frontend/src/components/PostForm.tsx#L605-L621)）：
```ts
const handleNewLocationField = (
  field: 'new_location_name' | 'new_location_lat' | 'new_location_lng'
       | 'new_location_type' | 'new_location_description',  // 新增 2 个
  value: string,
) => { ... }
```

**提交 payload 追加 description**（[PostForm.tsx#L817-L821](file:///e:/Project/moment-campus/frontend/src/components/PostForm.tsx#L817-L821)）：
```ts
const newLoc = await categoriesApi.createLocation({
  name: locationName,
  latitude: locationLat,
  longitude: locationLng,
  description: buildLocationDescription(
    formData.new_location_type,
    formData.new_location_description,
  ),  // 新增：SSOT 拼接
});
```

## 6. 权限 & 校验对齐（与小程序 100% 一致）

### 6.1 创建地点权限 canCreateLocation
复用小程序同逻辑，Web 端实现（封装为 hook 或工具函数都可，**最简：直接 inline 判断**）：
```ts
const canCreateLocation = Boolean(
  user && (
    // 1. 本校权限写入（校园认证通过 + 属于当前学校）
    canWriteInCurrentSchool(user, currentSchoolId)
    // 2. 管理员或超管，可跳过校园认证直接建
    || user.role === 'admin'
    || user.role === 'super_admin'
  )
);
```

**失败提示**：
- 未登录 → `navigate('/login')` + Toast「登录后即可新增地点」
- 已登录但 !canCreateLocation → VerifyGate compact 包在 Modal 内（独立弹窗场景）或 直接 Toast「请先完成校园认证」（PostForm 联动场景可复用已有 VerifyGate 包裹新字段区，但更简单方案：点提交时才校验失败 Toast，避免改变布局）

### 6.2 提交前校验（3 条硬规则，与小程序 [locations.ts#L274-L289](file:///e:/Project/moment-campus/miniprogram/subpackages/pages/locations/locations.ts#L274-L289) 完全一致）
```ts
function validateCreateLocationPayload(payload: {
  name: string; lat: number | ''; lng: number | ''; picked: boolean;
}): string | null {
  if (!payload.name.trim()) return '请填写地点名称';
  if (!payload.picked) return '请先在地图上选择地点位置';
  const lat = Number(payload.lat);
  const lng = Number(payload.lng);
  if (!Number.isFinite(lat) || lat < -90 || lat > 90 || !Number.isFinite(lng) || lng < -180 || lng > 180) {
    return '请在地图上重新选择地点位置';
  }
  return null;
}
```

## 7. 数据流 & 提交成功处理

### 7.1 独立弹窗（CreateLocationModal）成功后
```
用户点击提交 → validateCreateLocationPayload
  → 失败：showToast(错误)，不关闭
  → 成功：locationsApi.createLocation({ name, lat, lng, description })
    → 成功 Toast："地点已提交，等待核验"
    → 调用 onCreated(createdId) 回调：
      - LocationPage：可选 → 立刻 openDetail(createdId) 打开详情 Modal（对应用户想立刻看刚提交的内容），同时 loadLocations() 刷新列表显示新的"待核验"条目
      - MapPage：可选 → setLocationPanel(刚创建的 location) 打开地点信息面板，同时重新 installMapLocationLayer 刷新地图上的点
    → setModalOpen(false)
```

### 7.2 PostForm 联动模式成功后
逻辑不变（PostForm 原本就会清空新地点字段 → 把新 locationId 赋给 formData → Post 的 payload 带 location_id），**仅新增 description 传入，不改变任何已验证流程**。

## 8. 错误处理 & 边界兜底
- **网络错误**：submit try/catch → showToast(e.detail || "新增地点失败", 'error')，Modal 不关闭，用户可以改了再提交
- **未选点**：提交前 validate 先拦，Toast 提示
- **空名称**：同上
- **lat/lng 非法字符串**：Number() 后非有限数 → validate 拦截，避免后端抛 422
- **PostForm 草稿恢复 hasNew 判断**：`new_location_type.trim() || new_location_description.trim()` 也加入判断 → 避免「用户只填了类型+描述没选点/填名，草稿恢复后没进入 newLocationMode → 字段显示丢失」

## 9. 测试计划（验证通过标准）

### 9.1 前端构建
`npm run build` 无 TS 错误，无 ESLint 错误。

### 9.2 Playwright / 浏览器 E2E（3 条链路，必须全通过）
1. **双入口 + 独立弹窗**：
   - 登录 user1（已认证）→ `/locations` 点顶栏「新增地点」→ Modal 打开 → 选点 + 名称"南区便利店" + 类型选「服务点」 + 描述「营业时间：7:00-22:00，有打印和奶茶」 → 提交 → Toast 成功 → 地点详情页自动打开，核验 Badge = "待核验"，描述段显示 `"场所类型：服务点\n营业时间：7:00-22:00，有打印和奶茶"`
   - 回到 `/map` → 右下 FAB 出现（圆形 + 号）→ 点击 → 同 5 字段表单弹窗打开 → 再建一个"三食堂二楼窗口"类型=食堂 → 提交 → 地图上出现新建地点 marker
2. **发布页联动模式追加字段**：
   - `/publish` → 下拉选「✚ 新增地点」→ 选点 + 名称"北区打印店" + 类型「服务点」 + 描述"A4 黑白 0.1 元/张，支持微信" → 填帖子标题/正文 → 发布 → 帖子详情页关联地点正确；打开地点详情页 → 描述显示类型前缀 + 填写的描述正文
3. **权限拦截**：
   - 退出登录 → `/locations` 点「新增地点」→ 跳 `/login`
   - 登录一个未认证用户（user2）→ `/locations` 点「新增地点」→ Toast「请先完成校园认证」，Modal 不打开

### 9.3 类型分类有效性（验证地点能被类型筛选搜到）
在地点列表搜索框输入类型关键词（如"食堂"）→ 刚创建的「三食堂二楼窗口」能被名称+描述搜索命中（描述中含「场所类型：食堂」前缀）。

## 10. 影响范围 & 风险控制

| 模块 | 影响级别 | 风险点 | 控制措施 |
|------|---------|--------|---------|
| PostForm 发布流程 | 低 | 新增 2 字段可能漏了切校/草稿的同步 | 4 处初始化兜底全部人工检查一遍 + 草稿恢复 hasNew 判断专门加类型/描述字段 |
| MapPage 地图控件 | 低 | FAB 可能遮挡原有的 NavigationControl zoom | FAB 放 bottom-right 时和 maplibre 的 NavigationControl 位置完全一致？实际位置调整：改为 bottom-20 right-5（下移 5rem）避开缩放控件 |
| CreateLocationModal 组件 | 低 | MapLocationPicker 初始视野用默认的 DEFAULT_PICKER 而非当前学校中心 → 视野不对 → 用户选点找不到 | initialCenter = currentSchool.center_lat/center_lng，currentSchool 从 useCampusStore 取 |
| locationType 常量 | 极低 | 枚举翻译不一致（如"公共空间"误写成"公共场所"）→ 两端类型不一致 | 复制粘贴小程序 `LOCATION_TYPE_OPTIONS` 源字符串，不手敲 |
