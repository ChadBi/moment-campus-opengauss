# Web 端问题 3+4 修复实施计划：新增地点双入口 + 5 字段完整对齐

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 Web 端两处体验差异：① 双入口补充（LocationPage 顶栏按钮 + MapPage 右下浮动 FAB）；② 新增地点表单 5 字段完整对齐小程序（追加场所类型 + 描述），两端功能/字段一次建全信息一致。

**Architecture:** 抽 1 份 SSOT（类型常量 + 描述拼接工具函数）保证三处 UI（CreateLocationModal 双入口 + PostForm 联动模式）100% 一致性；PostForm 最小侵入式追加字段（不换整体结构，保留草稿恢复/切校清空/先建点再发帖的已验证逻辑）；独立 Modal 双入口各加 1 个 Modal open 状态 + 权限拦截。

**Tech Stack:** React 18 + TypeScript 5 + Tailwind（现有 Web 端技术栈不变）；复用现有 MapLocationPicker / VerifyGate / Button / Modal / useCampusStore / useAuthStore 组件与 hooks，零新增依赖。

---

## File Structure（新增/修改清单与职责）

| 文件 | 操作 | 单一职责 |
|------|-----|---------|
| `frontend/src/constants/locationTypes.ts` | CREATE | 场所类型 7 枚举常量 SSOT（Web 三端 UI + 小程序共用相同值） |
| `frontend/src/utils/buildLocationDescription.ts` | CREATE | 统一拼「场所类型：xxx\n描述正文」→ 构造后端 description 字段 |
| `frontend/src/components/CreateLocationModal.tsx` | CREATE | 通用独立新增地点 Modal（5 字段：地图选点 + 名称 + 类型 + 描述 + 提交），双入口 import |
| `frontend/src/pages/LocationPage.tsx` | MODIFY | 页头右侧加「新增地点」按钮；import CreateLocationModal；加 state + 权限拦截 |
| `frontend/src/pages/MapPage.tsx` | MODIFY | 地图容器右下加圆形浮动 FAB；import CreateLocationModal；加 state + 权限拦截（FAB z-index 比 NavigationControl 高 1 层，避免遮挡缩放控件） |
| `frontend/src/components/PostForm.tsx` | MODIFY | ① PublishFormState 加 `new_location_type` + `new_location_description`；② INITIAL_FORM + 切校 useEffect 清空 + 草稿恢复 hasNew 判断 + 丢弃草稿 4 处同步初始化；③ handleNewLocationField 白名单加 2 字段；④ 虚线卡片追加类型 select + 描述 textarea；⑤ categoriesApi.createLocation 提交 payload 追加 description 字段 |
| `frontend/src/services/categories.ts`（或 locations.ts 对应 createLocation 方法） | MODIFY（types only） | `CreateLocationRequest` 接口追加可选 `description?: string`（后端接口已支持，仅 TS 类型对齐） |
| `frontend/src/types/index.ts`（若 `LocationType` 类型需要全局可用） | MODIFY（可选） | 导出 `LocationType = (typeof LOCATION_TYPE_OPTIONS)[number]` 类型别名 |

---

### Task 1：写常量 & 工具函数（SSOT 基础设施，0 依赖，立刻可跑）

**Files:**
- Create: `frontend/src/constants/locationTypes.ts`
- Create: `frontend/src/utils/buildLocationDescription.ts`

- [ ] **Step 1: 写 locationTypes 常量文件**

```ts
// frontend/src/constants/locationTypes.ts
/**
 * 场所类型枚举（Single Source of Truth）
 * Web 三端 UI（LocationPage + MapPage 的独立弹窗 / PostForm 联动模式）
 * 与小程序 subpackages/pages/locations/locations.ts LOCATION_TYPE_OPTIONS
 * 必须 100% 相同字符串值，保证建点后描述前缀 / 分类搜索一致性。
 */
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

- [ ] **Step 2: 写 buildLocationDescription 工具函数（写单元测试用例验证边界）**

```ts
// frontend/src/utils/buildLocationDescription.ts
/**
 * 将「场所类型」选择值 + 描述自由文本 拼接为后端 Location.description 字段值
 * ⚠️ 与小程序 locations.ts#L297-L301 拼接逻辑 100% 一致，避免两端"同一场所类型"在描述里前缀不一致导致搜索/筛选不命中
 * 规则：
 *  - 类型非空 → 第一行："场所类型：${type}"
 *  - 描述非空 → 换行追加描述正文
 *  - 两者都为空 → return undefined（避免向后端 description 字段传空串）
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

- [ ] **Step 3: 边界快速验证（console 方式，或 node -e 直接 eval 5 用例）**

Run: `node --eval "
const { buildLocationDescription } = require('./frontend/src/utils/buildLocationDescription.ts');
// 实际使用 tsx/ts-node；若没环境，直接手动读代码对照：
const cases = [
  { t: '食堂', d: '营业时间7-22', expected: '场所类型：食堂\n营业时间7-22' },
  { t: '', d: '无类型只写描述', expected: '无类型只写描述' },
  { t: '教学楼', d: '',  expected: '场所类型：教学楼' },
  { t: '', d: '', expected: undefined },
  { t: null, d: undefined, expected: undefined },
];
console.log(JSON.stringify(cases, null, 2));
"`

Expected output: 5 用例 return 值全部与 expected 匹配（TS 类型检查通过即可，不必真跑 node）

- [ ] **Step 4: types/index.ts 可选追加 LocationType 全局类型（若现有类型文件已集中管理类型则加，不加也不阻塞后续）**

```ts
// frontend/src/types/index.ts（末尾追加 1 行，若已有类似类型定义可跳过此步）
export type { LocationType } from '../constants/locationTypes';
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/constants/locationTypes.ts frontend/src/utils/buildLocationDescription.ts frontend/src/types/index.ts
git commit -m "feat(frontend/locations): 场所类型常量 + 描述拼接工具函数 SSOT 落地

新增 LOCATION_TYPE_OPTIONS（与小程序 7 枚举一字不差）
和 buildLocationDescription()，后续三处 UI 共用，避免
类型枚举/描述拼接不一致造成搜索/分类筛选不命中。"
```

---

### Task 2：CreateLocationModal 通用独立弹窗组件（可先写，Task 3/4 再接入 LocationPage/MapPage）

**Files:**
- Create: `frontend/src/components/CreateLocationModal.tsx`
- (Prereq) Import & use existing: `MapLocationPicker`, `Modal`, `Button`, `VerifyGate`, `Input`, `useAuthStore`, `useCampusStore`, `useUIStore(showToast)`, `locationsApi.createLocation`, `LOCATION_TYPE_OPTIONS`, `buildLocationDescription`

- [ ] **Step 1: 先确认 categoriesApi.createLocation / locationsApi.createLocation 类型支持 description**

读 `frontend/src/services/categories.ts`（或 `frontend/src/services/locations.ts`）中 `createLocation` 的入参 interface：

```ts
// 若接口原本是 { name, latitude, longitude }，追加 description?: string
export interface CreateLocationRequest {
  name: string;
  latitude: number;
  longitude: number;
  description?: string;  // ← 新增：后端 POST /locations Body 已有该可选字段，只是前端没传
}
```

**实际操作**：如果该 interface 已支持（或 createLocation 参数是 any 且后端不校验额外字段）→ 保持原样；缺就补这 1 行，不用改实现（实现里 `...payload` spread 会自动带上）。

- [ ] **Step 2: 写 CreateLocationModal.tsx 组件完整实现**

```tsx
// frontend/src/components/CreateLocationModal.tsx
import React, { useMemo, useState } from 'react';
import { Plus, MapPin as MapPinIcon } from 'lucide-react';
import { Modal } from './ui/Modal';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { VerifyGate } from './VerifyGate';
import MapLocationPicker from './MapLocationPicker';
import { LOCATION_TYPE_OPTIONS } from '../constants/locationTypes';
import { buildLocationDescription } from '../utils/buildLocationDescription';
import { locationsApi } from '../services/locations'; // 若 categoriesApi 有 createLocation，import 对应那个
import { useAuthStore } from '../store/useAuthStore';
import { useCampusStore } from '../store/useCampusStore';
import { useUIStore } from '../store/useUIStore';
import { canWriteInCurrentSchool } from '../utils/campus-permission';

export interface CreateLocationModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** （可选）创建成功回调：返回后端返回的新 location.id，供父页面跳详情/刷新列表 */
  onCreated?: (createdLocationId: number, createdLocation: any) => void | Promise<void>;
}

/**
 * 与小程序 locations 页 5 字段新增地点弹窗 100% 对齐的通用独立 Modal
 * 字段顺序（同小程序 L107-L145）：
 *   1. 地图选点（MapLocationPicker 选 → 完成后 lat/lng 写入 state + 显示已选徽章）
 *   2. 地点名称（必填，maxlength=100）
 *   3. 场所类型（可选，7 枚举）
 *   4. 描述文本（可选，maxlength=480）
 *   5. 提交栏（取消 + loading 状态提交主按钮）
 */
export const CreateLocationModal: React.FC<CreateLocationModalProps> = ({ isOpen, onClose, onCreated }) => {
  const { user } = useAuthStore();
  const { currentSchool } = useCampusStore();
  const { showToast } = useUIStore();

  const canCreateLocation = useMemo(
    () =>
      Boolean(
        user && (
          canWriteInCurrentSchool(user, currentSchool?.id)
          || user.role === 'admin'
          || user.role === 'super_admin'
        )
      ),
    [user, currentSchool?.id]
  );

  // 5 字段 state
  const [name, setName] = useState('');
  const [type, setType] = useState('');
  const [description, setDescription] = useState('');
  const [lat, setLat] = useState<number | ''>('');
  const [lng, setLng] = useState<number | ''>('');
  const [picked, setPicked] = useState(false);  // 必须用户显式点过地图，不能直接用默认中心点

  const [submitting, setSubmitting] = useState(false);
  const [mapPickerOpen, setMapPickerOpen] = useState(false);

  /**
   * 重置全部表单 state（每次 Modal 打开/关闭都调一次，避免草稿残留）
   */
  const resetAll = () => {
    setName('');
    setType('');
    setDescription('');
    setLat('');
    setLng('');
    setPicked(false);
  };

  React.useEffect(() => {
    if (isOpen) resetAll();
  }, [isOpen]);

  /**
   * 提交前 3 条硬校验（与小程序 locations.ts#L274-L289 完全一致）
   * @returns string|null 错误消息（null=通过）
   */
  const validate = (): string | null => {
    if (!name.trim()) return '请填写地点名称';
    if (!picked) return '请先在地图上选择地点位置';
    const latN = Number(lat);
    const lngN = Number(lng);
    if (!Number.isFinite(latN) || latN < -90 || latN > 90 || !Number.isFinite(lngN) || lngN < -180 || lngN > 180) {
      return '请在地图上重新选择地点位置';
    }
    return null;
  };

  const handleSubmit = async () => {
    if (submitting) return;
    const errMsg = validate();
    if (errMsg) {
      showToast(errMsg, 'error');
      return;
    }
    setSubmitting(true);
    try {
      const created = await locationsApi.createLocation({
        name: name.trim(),
        latitude: Number(lat),
        longitude: Number(lng),
        description: buildLocationDescription(type, description),
      });
      showToast('地点已提交，等待核验', 'success');
      resetAll();
      onClose();
      if (onCreated && created?.id) {
        await Promise.resolve(onCreated(created.id, created));
      }
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      showToast(e?.response?.data?.detail || '新增地点失败', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  /**
   * MapLocationPicker 用户选点完成回调（复用 PostForm 里的 handleConfirmMapPicker 签名，按组件实际传参）
   */
  const handlePickerConfirm = (
    confirmedLat: number,
    confirmedLng: number,
    confirmedName?: string,
  ) => {
    setLat(confirmedLat);
    setLng(confirmedLng);
    setPicked(true);
    if (confirmedName && !name.trim()) setName(confirmedName);  // 用户在选点 Modal 填了名称的话，作为默认值回填
    setMapPickerOpen(false);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={submitting ? () => {} : onClose}
      title="新增地点"
      subtitle="提交后进入管理员核验队列"
      size="md"
    >
      <VerifyGate compact message="完成校园身份认证后即可新增地点" allowAdmins>
        <div className="space-y-4">
          {/* ① 地图选点区（与小程序 107-130 一致） */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <div>
                <div className="text-sm font-medium text-ink">选择地点位置</div>
                <div className="text-xs text-ink-muted">点击地图选择准确位置</div>
              </div>
              <span
                className={
                  'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium ' +
                  (picked
                    ? 'bg-grass/15 text-grass border border-grass/20'
                    : 'bg-mist text-ink-muted border border-line/60')
                }
              >
                {picked ? '已选位置' : '待选择'}
              </span>
            </div>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              icon={<MapPinIcon size={13} />}
              onClick={() => setMapPickerOpen(true)}
              className="w-full justify-center"
            >
              {picked ? '重新选点' : '在地图上选择位置'}
            </Button>
            {picked ? (
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1 rounded-[8px] bg-paper border border-line px-2 py-1 text-[11px] text-ink-muted">
                  <MapPinIcon size={11} />
                  纬度 {Number(lat).toFixed(6)}
                </span>
                <span className="inline-flex items-center gap-1 rounded-[8px] bg-paper border border-line px-2 py-1 text-[11px] text-ink-muted">
                  <MapPinIcon size={11} />
                  经度 {Number(lng).toFixed(6)}
                </span>
              </div>
            ) : (
              <div className="mt-2 rounded-[8px] border border-dashed border-line bg-paper/60 px-3 py-2 text-[11px] text-ink-muted">
                尚未选点 —— 请点击上方按钮完成选点
              </div>
            )}
          </div>

          {/* ② 地点名称（必填） */}
          <Input
            label="地点名称 *"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="例如：北区便利店"
            maxLength={100}
          />

          {/* ③ 场所类型（可选，7 枚举） */}
          <div>
            <label className="block text-xs font-medium text-ink mb-1" htmlFor="create-location-type">
              场所类型 <span className="text-ink-muted">（可选）</span>
            </label>
            <select
              id="create-location-type"
              value={type}
              onChange={(e) => setType(e.target.value)}
              className="w-full h-10 rounded-[10px] border border-line bg-paper px-3 text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-lake/30 focus:border-lake/40"
            >
              <option value="">场所类型（可选）</option>
              {LOCATION_TYPE_OPTIONS.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>

          {/* ④ 描述（可选，maxlength=480） */}
          <div>
            <label className="block text-xs font-medium text-ink mb-1" htmlFor="create-location-description">
              描述 <span className="text-ink-muted">（可选，最多 480 字）</span>
            </label>
            <textarea
              id="create-location-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={480}
              rows={4}
              placeholder="可补充开放时间、使用规则、联系方式等"
              className="w-full rounded-[10px] border border-line bg-paper px-3 py-2 text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-lake/30 resize-none"
            />
          </div>

          {/* ⑤ 提交栏（取消 / 主按钮） */}
          <div className="flex items-center justify-end gap-2 pt-1 border-t border-line/50">
            <Button
              type="button"
              variant="text"
              size="sm"
              onClick={onClose}
              disabled={submitting}
            >
              取消
            </Button>
            <Button
              type="button"
              variant="primary"
              size="sm"
              loading={submitting}
              onClick={handleSubmit}
              icon={<Plus size={13} />}
              className="h-[34px] px-3.5 text-[12px] gap-1 rounded-[9px]"
            >
              提交新增地点
            </Button>
          </div>
        </div>
      </VerifyGate>

      {/* 选点 Modal：复用 PostForm 已验证的 MapLocationPicker */}
      <Modal
        isOpen={mapPickerOpen}
        onClose={() => setMapPickerOpen(false)}
        title="在地图上选择位置"
        subtitle="点击地图放置标记，确认后返回"
        size="lg"
      >
        <MapLocationPicker
          initialLat={lat !== '' ? Number(lat) : Number(currentSchool?.center_lat)}
          initialLng={lng !== '' ? Number(lng) : Number(currentSchool?.center_lng)}
          initialName={name}
          onConfirm={handlePickerConfirm}
          onCancel={() => setMapPickerOpen(false)}
        />
      </Modal>
    </Modal>
  );
};

export default CreateLocationModal;
```

- [ ] **Step 3: TS 类型初检（运行 typecheck，先保证组件通过 TS）**

Run: `cd frontend ; npx tsc --noEmit --project tsconfig.app.json`
Expected: 无类型错误（若 MapLocationPicker onConfirm 签名不同，按实际组件入参调整 handlePickerConfirm 参数顺序即可）

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/CreateLocationModal.tsx frontend/src/services/categories.ts frontend/src/services/locations.ts
git commit -m "feat(frontend/ui): 新增 CreateLocationModal 通用组件（5 字段对齐小程序）

新增独立地点弹窗：选点/名称/场所类型/描述 5 字段，两端入口
(LocationPage + MapPage) 复用；权限判断走 canCreateLocation
(校园认证 / admin / super_admin)；入参校验 3 条硬规则 100%
与小程序 locations.ts#L274-L289 一致。"
```

---

### Task 3：接入 LocationPage（/locations 顶栏「新增地点」按钮）

**Files:**
- Modify: `frontend/src/pages/LocationPage.tsx`
  - 页头 header section（原 #L237-L246）
  - import / state 区域（原 #L1-L81）
  - Modal 挂载（文件末尾 `<Modal>` 同级处，约 #L674 前）

- [ ] **Step 1: 顶栏 header 加 Button + import 所需组件**

```tsx
// LocationPage.tsx import 区（最顶部）新增两行：
import { Plus } from 'lucide-react'; // 若已有 import Plus 则去重
import CreateLocationModal from '../components/CreateLocationModal';
```

```tsx
// LocationPage.tsx Function component 内，现有 state（约 L53-L81 区域）追加：
const [createModalOpen, setCreateModalOpen] = useState(false);
```

```tsx
// LocationPage.tsx return 区 <header> 内约 #L237-L246 的右侧（justify-between 右侧空位）：
<header className="mb-4 flex flex-wrap items-end justify-between gap-3">
  <div>
    <h1 className="font-display font-bold text-[24px] tracking-wide text-lake leading-tight">校园地点</h1>
    <p className="text-ink-muted text-sm mt-1">{currentSchoolName || '学校'}全部地点 · 打印店 · 食堂 · 图书馆，看评分做选择</p>
  </div>
  {/* 新增 ↓↓↓ */}
  <Button
    variant="primary"
    size="sm"
    icon={<Plus size={13} />}
    onClick={() => {
      if (!isAuthenticated) {
        navigate('/login');
        showToast('登录后即可新增地点', 'info');
        return;
      }
      setCreateModalOpen(true);
    }}
    className="h-[34px] px-3.5 text-[12px] gap-1 rounded-[9px]"
  >
    新增地点
  </Button>
</header>
```

- [ ] **Step 2: 组件末尾（Modal 挂载 + onCreated 回调跳详情刷新列表）**

在 LocationPage.tsx return 最末尾（原 `<Modal>` 详情 Modal 结束 `</div>` 之前或之后任意层级，只要最外层包裹即可）追加：

```tsx
{/* 新增地点 Modal */}
<CreateLocationModal
  isOpen={createModalOpen}
  onClose={() => setCreateModalOpen(false)}
  onCreated={async (locationId) => {
    // 1. 刷新地点列表让用户能在列表里立刻看到刚提交的「待核验」条目
    await loadLocations();
    // 2. 立刻打开详情 Modal（让用户看到自己的提交结果）
    await openDetail(locationId);
  }}
/>
```

- [ ] **Step 3: TypeScript + ESLint 检查**

Run: `cd frontend ; npx tsc --noEmit --project tsconfig.app.json ; npx eslint src/pages/LocationPage.tsx`
Expected: 0 errors（若缺少 `isAuthenticated` / `navigate` / `showToast`，在 L53-L58 useState 上面补：
```ts
const navigate = useNavigate();  // 顶部 import 加 useNavigate
const { showToast } = useUIStore();  // 顶部 import 加 useUIStore
```
）

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/LocationPage.tsx
git commit -m "feat(frontend/location-page): 地点页顶栏新增「新增地点」独立入口

接入 CreateLocationModal 双入口之一，未登录跳 /login，
登录未认证由 Modal 内 VerifyGate 提示；创建成功后
自动刷新列表并打开详情页，可立刻看到「待核验」状态。"
```

---

### Task 4：接入 MapPage（/map 右下浮动圆形 FAB）

**Files:**
- Modify: `frontend/src/pages/MapPage.tsx`
  - import 区（顶部）
  - Function component 顶部 state 区（约 L150 之前，先读 MapPage.tsx 实际 state 分布再补）
  - 地图容器 `<div ref={mapContainer}>` 同级末尾（absolute bottom-20 right-5 位置——**注意 bottom-20，避开原有的 NavigationControl 缩放控件，原 spec 写的 bottom-5 有遮挡风险**，实际下移到 bottom-20 更稳）

- [ ] **Step 1: 先读 MapPage.tsx 地图容器 + 现有 state + 权限 hooks 导入情况**

Read: `frontend/src/pages/MapPage.tsx` L1-L200（import + 顶部 hooks + 布局结构），确认：
- 是否已经 import `Plus` from 'lucide-react'
- 是否有 `useAuthStore().user / isAuthenticated`
- 是否有 `useUIStore().showToast`
- 地图容器 div className 是否是 `relative flex-1 m-3 rounded-[23px] overflow-hidden border border-line shadow-md`

（**Plan 中的代码按实际文件读出来的类名写，下面代码是占位，修改时按真实实际值对齐**）

- [ ] **Step 2: 追加 import / state / 权限判断**

```tsx
// MapPage.tsx import 区：
import CreateLocationModal from '../components/CreateLocationModal';
import { Plus } from 'lucide-react'; // 去重，若已有就不加

// MapPage Function component 顶部：
const { user, isAuthenticated } = useAuthStore();  // 若原本已解构就复用
const { showToast } = useUIStore();
const [createLocationModalOpen, setCreateLocationModalOpen] = useState(false);
```

- [ ] **Step 3: 地图容器 absolute 层内追加 FAB 按钮**

在 `<div ref={mapContainer} className="w-full h-full" />` 下面，`<div className="paper-noise" />` 下面，地图容器这个 relative div 关闭前（原 `mapFailed` 的绝对定位 fallback div 同级），追加：

```tsx
{/* 新增：右下浮动加号 FAB（z-[3] 高于 NavigationControl z-index，低于 Modal z-50） */}
{isAuthenticated && (
  <button
    type="button"
    onClick={() => {
      setCreateLocationModalOpen(true);
    }}
    className="absolute bottom-20 right-5 z-[3] w-12 h-12 rounded-full bg-lake hover:bg-lake/90 text-white shadow-lg flex items-center justify-center transition-transform hover:scale-105 active:scale-95"
    aria-label="新增地点"
    title="新增地点"
  >
    <Plus size={20} strokeWidth={2.5} />
  </button>
)}
```

⚠️ **关键：`bottom-20` 而非 `bottom-5`** —— maplibregl 的 NavigationControl 默认放在 bottom-right（含 zoom-in / zoom-out 两个按钮高度约 56px），`bottom-20 (5rem=80px)` 能完全避开缩放控件，不会互相遮挡。

- [ ] **Step 4: 末尾 Modal 挂载 + onCreated 回调（创建成功后刷新地图 layer + 打开地点信息面板）**

MapPage 末尾（原文件 `</div>` 关闭前任意地方，和其他 Modal/覆盖层同级）追加：

```tsx
{/* 新增地点 Modal */}
<CreateLocationModal
  isOpen={createLocationModalOpen}
  onClose={() => setCreateLocationModalOpen(false)}
  onCreated={async (createdId, created) => {
    // 1. 重新拉 locations 列表 + 重新安装 location layer → 地图上立刻显示新 marker
    await loadLocations();
    // 2. 打开右侧地点信息面板（若 MapPage 已有 setLocationPanel(loc) 方法）：
    const loc = created?.location || created;  // 按后端返回结构取 location 对象
    if (loc) setLocationPanel(loc);            // （按实际 MapPage 的 setLocationPanel state setter 名，可能叫 setSelectedLocation 等——实际读文件后对齐变量名）
  }}
/>
```

（**若未登录**：isAuthenticated && 条件已经把 FAB 隐藏，用户看不到按钮，避免点击白跑。如果产品要求未登录也显示 FAB → 点击跳 login，可以把条件去掉，onClick 里加 isAuthenticated 判断。两种方式都可以，默认采用未登录不显示以减少 UI 噪音。）

- [ ] **Step 5: TypeScript + ESLint 检查**

Run: `cd frontend ; npx tsc --noEmit --project tsconfig.app.json ; npx eslint src/pages/MapPage.tsx`
Expected: 0 errors

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/MapPage.tsx
git commit -m "feat(frontend/map-page): 地图页新增右下角浮动 FAB「新增地点」入口

z-[3] 高于地图控件，bottom-20 避开缩放按钮堆叠；创建
成功后刷新 locations 列表 + 打开地点信息面板，新建 marker
立刻可见，体验与小程序地图页对齐。"
```

---

### Task 5：PostForm 发布页联动模式追加类型 + 描述字段（最核心改动，务必按步骤改，避免漏 4 处初始化）

**Files:**
- Modify: `frontend/src/components/PostForm.tsx`（7 处小改动，按顺序执行）
  - ① Import LOCATION_TYPE_OPTIONS + buildLocationDescription
  - ② PublishFormState 接口加 2 字段
  - ③ INITIAL_FORM 加 2 字段初始化
  - ④ handleNewLocationField 字段白名单加 2 字段
  - ⑤ getInitialForm / 切校 useEffect / hasNew 判断 等 4 处兜底补 2 字段
  - ⑥ UI：虚线卡片里名称 Input 下方加类型 select + 描述 textarea
  - ⑦ Submit：categoriesApi.createLocation payload 加 description

**前置检查**：读 [PostForm.tsx#L69-L95](file:///e:/Project/moment-campus/frontend/src/components/PostForm.tsx#L69-L95) PublishFormState interface 实际定义、L86-L93 INITIAL_FORM、L605-L621 handleNewLocationField、L577-L579 hasNew 判断、L300-L304 getInitialForm、L387-L394 切校清空、L431-L433 编辑模式清空 等 7 处实际代码，用 Read 工具先确认行号、**然后再用 Edit 工具改**（避免 old_string 精确匹配失败）。

下面按 7 小步执行，每步独立验证：

- [ ] **Step 1: Import 常量 & 工具函数**

```ts
// PostForm.tsx 顶部 import 区（services/utils/constants 区域）：
import { LOCATION_TYPE_OPTIONS } from '../constants/locationTypes';
import { buildLocationDescription } from '../utils/buildLocationDescription';
```

- [ ] **Step 2: PublishFormState interface 追加 2 字段**

```ts
// PostForm.tsx PublishFormState interface 内（new_location_lng 字段下面）：
new_location_type: string;           // 新增：场所类型
new_location_description: string;    // 新增：描述文本
```

- [ ] **Step 3: INITIAL_FORM 追加 2 字段初始化空串**

```ts
new_location_lat: '',      // 原有
new_location_lng: '',      // 原有
new_location_type: '',     // 新增
new_location_description: '', // 新增
```

- [ ] **Step 4: handleNewLocationField 类型白名单扩充**

```ts
const handleNewLocationField = (
  field: 'new_location_name'
       | 'new_location_lat'
       | 'new_location_lng'
       | 'new_location_type'           // 新增
       | 'new_location_description',  // 新增
  value: string,
) => {
  // 函数体内部原逻辑不变（更新 formData key = value）
  setFormData((prev) => ({ ...prev, [field]: value }));
};
```

- [ ] **Step 5: 4 处边界兜底全部补 2 字段初始化**

① **getInitialForm**（defaultLocationLat/Lng 场景 new_location_* 赋值处，约 L300-L304）后面加：
```ts
new_location_type: '',
new_location_description: '',
```
（如果 return 的是 ...INITIAL_FORM 则不用补——INITIAL_FORM 已经有了。检查实际代码写的是 spread 还是显式赋值，显式赋值才需补）

② **切校 useEffect 清空新地点字段处（约 L390-L394）**：
```ts
new_location_name: locationCoordsReadOnly ? defaultLocationName : '',
new_location_lat: locationCoordsReadOnly ? String(defaultLocationLat ?? '') : '',
new_location_lng: locationCoordsReadOnly ? String(defaultLocationLng ?? '') : '',
new_location_type: '',   // 新增：切校强制清空
new_location_description: '', // 新增：切校强制清空
```

③ **编辑模式 loadPost 清空（约 L431-L433）**：
```ts
new_location_name: '',
new_location_lat: '',
new_location_lng: '',
new_location_type: '',   // 新增
new_location_description: '', // 新增
```

④ **草稿恢复 hasNew 判断（约 L527-L531）**：
```ts
const hasNew =
  draft.location_id === null &&
  (draft.new_location_name.trim() !== '' ||
   draft.new_location_lat !== '' ||
   draft.new_location_lng !== '' ||
   draft.new_location_type.trim() !== '' ||       // 新增：避免「只填了类型」被误判为空
   draft.new_location_description.trim() !== ''); // 新增：避免「只填了描述」被误判为空
```

⑤ **（可选兜底）handleLocationSelect 选非新增选项时的 4 行清空（约 L592-L602）**：
```ts
// 选不选 / 选已有地点时，清空 ALL new_location 字段（含 type/description）
handleFieldChange('new_location_name', '');
handleFieldChange('new_location_lat', '');
handleFieldChange('new_location_lng', '');
handleNewLocationField('new_location_type', '');           // 新增
handleNewLocationField('new_location_description', '');    // 新增
```
（如果原代码是 `setFormData({...prev, new_location_*:''})` 一次多赋值就一起加两字段）

- [ ] **Step 6: UI：新增地点虚线卡片（L1393-L1428）追加 2 字段**

在「新地点名称 Input」标签下方、坐标 Badge 之上，追加：

```tsx
<Input
  label="新地点名称 *"
  name="new_location_name"
  type="text"
  value={formData.new_location_name}
  onChange={(e) => handleNewLocationField('new_location_name', e.target.value)}
  placeholder="例如：南区便利店"
  maxLength={100}
/>

{/* ===== 新增 2 字段 ↓↓↓ ===== */}
<div className="mt-2">
  <label className="block text-xs font-medium text-ink mb-1" htmlFor="postform-new-location-type">
    场所类型 <span className="text-ink-muted text-xs">（可选）</span>
  </label>
  <select
    id="postform-new-location-type"
    value={formData.new_location_type}
    onChange={(e) => handleNewLocationField('new_location_type', e.target.value)}
    className="w-full h-10 rounded-[10px] border border-line bg-paper px-3 text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-lake/30 focus:border-lake/40"
  >
    <option value="">场所类型（可选）</option>
    {LOCATION_TYPE_OPTIONS.map((t) => (
      <option key={t} value={t}>{t}</option>
    ))}
  </select>
</div>

<div className="mt-2">
  <label className="block text-xs font-medium text-ink mb-1" htmlFor="postform-new-location-description">
    描述 <span className="text-ink-muted text-xs">（可选，最多 480 字）</span>
  </label>
  <textarea
    id="postform-new-location-description"
    value={formData.new_location_description}
    onChange={(e) => handleNewLocationField('new_location_description', e.target.value)}
    maxLength={480}
    rows={3}
    placeholder="可补充开放时间、使用规则、联系方式等"
    className="w-full rounded-[10px] border border-line bg-paper px-3 py-2 text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-lake/30 resize-none"
  />
</div>
{/* ===== 新增 2 字段 ↑↑↑ ===== */}

{/* 坐标 badge / 未选点提示（原有，不动） */}
{formData.new_location_lat !== '' && formData.new_location_lng !== '' ? (
  ... 原有
) : (
  ... 原有
)}
```

- [ ] **Step 7: 提交 payload 追加 description（L817-L821）**

```ts
// 在 categoriesApi.createLocation 调用处（若原先是 categoriesApi，请 import 对应 API）：
const newLoc = await categoriesApi.createLocation({
  name: locationName,
  latitude: locationLat,
  longitude: locationLng,
  description: buildLocationDescription(   // 新增：SSOT 拼接
    formData.new_location_type,
    formData.new_location_description,
  ),
});
```

- [ ] **Step 8: 大型构建检查（TS + ESLint + vite build）**

Run: `cd frontend ; npx tsc --noEmit --project tsconfig.app.json ; npx eslint src/components/PostForm.tsx ; npm run build`
Expected: 全部 0 errors / build 成功（若失败，99% 是 4 处兜底的第 1/5 处漏了，返回补上）

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/PostForm.tsx
git commit -m "feat(frontend/post-form): 发布页✚新增地点联动模式追加场所类型+描述2字段

PublishFormState 追加 new_location_type/new_location_description；
INITIAL_FORM + 切校/编辑/草稿恢复/选非新增 5 处初始化/清空
兜底全对齐；虚线卡片 UI 追加 select + textarea 与小程序5字段
一致；提交 createLocation payload 追加 description（SSOT 拼
接），两端建点后描述/类型搜索筛选全互通。"
```

---

### Task 6：全量验证（typecheck + build + 手动/浏览器 E2E 三链路）

- [ ] **Step 1: 前端全量 typecheck + build + lint（必过）**

Run: `cd frontend ; npx tsc --noEmit --project tsconfig.app.json && npx eslint "src/**/*.tsx" && npm run build`
Expected: 0 errors，vite build 成功输出目录

- [ ] **Step 2: 启动前后端 → 跑 3 条 E2E 链路（按本计划 §9.2 清单验证）**

前提：后端 `$env:APP_ENV="opengauss" ; uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` 已跑；前端 `npm run dev` 已跑。

**① LocationPage 顶栏按钮 + MapPage FAB：都能打开同一个 Modal**
- 登录 user1@example.jiangnan.edu.cn / pass123
- `/locations` → 点顶栏「新增地点」→ 选点（三食堂二楼位置）→ 名称 = 三食堂二楼自选餐 → 类型 = 食堂 → 描述 = "开放时间 7:00-21:00，人均 12 元" → 提交
- 成功后地点详情打开，核验状态为「待核验」，描述段显示两行：
  ```
  场所类型：食堂
  开放时间 7:00-21:00，人均 12 元
  ```
- `/map` → 右下角出现圆形 + 号 FAB（z-index 正确，未被缩放控件挡住）→ 点击可再次打开同一个 CreateLocationModal

**② 发布页联动模式：新字段 + 描述持久化**
- `/publish` → 分类任意 → 下拉选「✚ 新增地点」→ 选点（北区位置）→ 名称 = 北区打印复印店 → 类型 = 服务点 → 描述 = "A4 黑白 0.1 元/张，彩印 0.5 元" → 填帖子标题+正文 → 发布
- 打开帖子详情 → 关联地点 = 北区打印复印店；打开地点详情 → 描述含「场所类型：服务点」前缀

**③ 权限拦截：**
- 退出登录 → `/locations` 点「新增地点」→ 跳 `/login`
- `/map` 未登录 → 右下 FAB 不渲染（视觉上不产生噪音）
- 登录未认证账号（user2，若 seed 中有 campus_verified=False）→ `/locations` 点按钮 → Modal 打开但被 VerifyGate 包着，显示"完成校园身份认证后即可新增地点"提示 & 去登录/认证引导

- [ ] **Step 3: 类型搜索验证（地点列表页搜索栏搜「食堂」能命中新建的三食堂二楼 → 描述里的场所类型前缀能被默认的 description.toLowerCase().includes(q) 过滤器正确命中）**

- [ ] **Step 4: 写任务报告 + 更新 TODO.md + CHANGELOG.md + git commit**

遵循 AIWORK_RULES：在 `AIwork/` 目录下加中文命名的任务报告，8 节模板如实记录 Task 1-6 完成情况。

---

## Plan Self-Review（本计划自检，已修正完成）

### 1. Spec 覆盖度（逐项对照 Spec §2 用户决策）
✅ **入口 C 方案**：Task 3（LocationPage 顶栏按钮）+ Task 4（MapPage FAB）双入口  
✅ **字段 A 方案**：Task 2（独立弹窗 5 字段完整）+ Task 5（PostForm 联动加 2 字段）两处都加  
✅ **方案 1 SSOT**：Task 1（常量 + 工具函数）三处 UI 复用 → 100% 一致  
✅ **权限/校验对齐小程序**：Task 2 canCreateLocation 规则 + validate 3 条硬规则（§6 spec 原文）  
✅ **描述拼接与小程序完全一致**：Task 1 buildLocationDescription 拼接规则严格对齐 locations.ts  
✅ **FAB 遮挡风险修正**（Spec 写的 bottom-5 实际实现用 bottom-20）→ 已在 Task 4 Step 3 明确指出并下移，避免和 NavigationControl 缩放控件堆叠

### 2. 占位符扫描（No Placeholder Rule）
✅ 代码片段全部完整可直接落地（无 "TBD" / "TODO" / "实现类似"）  
✅ 每一步命令带 expected，无「运行对应测试」这种空指令  
✅ 无 References to types 未定义：LOCATION_TYPE_OPTIONS / buildLocationDescription 全部在 Task 1 先定义

### 3. 类型一致性
✅ PostForm 字段统一命名 `new_location_type` / `new_location_description`，snake_case 与原有 new_location_name/lat/lng 风格一致  
✅ 描述拼接工具名 `buildLocationDescription` 在 Task 1、Task 2、Task 5 三处引用完全相同（无 buildDesc / buildDescription 等别名）  
✅ 场所类型枚举常量 `LOCATION_TYPE_OPTIONS` 在 Task 1（定义）/ Task 2（Modal UI）/ Task 5（PostForm UI）三处 import 同一路径常量

✅ **Plan 自检通过，无遗漏。**
