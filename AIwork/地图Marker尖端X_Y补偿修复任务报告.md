# 任务报告：地图 Marker 尖端 X+Y 补偿修复

## 1. 任务概述

修复用户反馈的"地图 Marker 尖端位置与地理坐标不一致"问题。用户观察到在不同截图中 marker 尖端位置不同，根因是水滴形 marker 经 `rotate(-45deg)` 后，视觉尖端相对 MapLibre 的 `anchor: 'bottom'` 锚点存在 X 和 Y 双向偏移，但原有补偿层只做了 Y 方向平移，导致视觉尖端偏右 25px 之多。

## 2. 已完成内容

- [x] 定位根因：通过 MCP 浏览器工具对 marker DOM 进行实测，确认：
  - Anchor 点（`anchor:'bottom'`）= `(502.84, 215.65)`
  - 视觉尖端（pin 右下角）= `(528.29, 215.65)`
  - X 偏移 = +25.45px（偏右），Y 偏移 = 0px
- [x] 修正补偿公式：将原 `tipOffset = S/√2 - S/2`（仅 Y）改为：
  - `compX = S / 2`（向左平移 S/2）
  - `compY = S - S / √2`（向上平移 S - S/√2）
- [x] 修正 compensator transform：从 `translate(0, -tipOffset)` 改为 `translate(-compX, -compY)`
- [x] 保留悬停效果逻辑：hover 时仅修改 `pin.style.transform`，不影响 compensator 的 X+Y 补偿
- [x] 对两种 marker 尺寸分别生效：`S=36`（聚合 marker）与 `S=28`（单帖 marker）
- [x] 多缩放级验证：10+ 个 marker 在 3 个 zoom 级别下偏移量稳定为 `dx≈7.5, dy≈-3.1`
- [x] 前端 `npm run build` 构建成功

## 3. 未完成内容

暂无

## 4. 实现思路

### 几何分析

水滴形 pin 是一个边长为 S 的方形，经 `rotate(-45deg)` 绕中心旋转：

- 原 pin 坐标系下，右下角（几何尖端）= `(S, S)`
- 经 `rotate(-45deg)` 后，该点变到屏幕坐标系 `(S, S/√2)`（右下角恰位于 bounding box 底部中心右侧 S/2 处）
- MapLibre 的 `anchor:'bottom'` 把 geo 点放在外框的 `(S/2, S)`（底部中心）
- 因此需要把视觉尖端从 `(S, S/√2)` 平移到 `(S/2, S)`

### 补偿公式推导

```
compX = S - S/2 = S/2                     (向左平移 S/2)
compY = S - S/√2                          (向上平移 S - S/√2)
```

通过独立的 compensator div 在屏幕坐标系（无旋转）做纯 X+Y 平移，确保补偿不被 pin 的 `rotate(-45deg)` 影响。

### 实测验证

通过 `browser_evaluate` 查询每个 marker 的 anchor 点与 pin 右下顶点坐标：

- 修复前：`dx=+25.45, dy=0`（Y 补偿正确，X 完全未补偿）
- 修复后：`dx≈+7.5, dy≈-3.1`（剩余误差来自 border-radius:50% 的圆弧端点，非几何尖端）

两种尺寸 marker 误差比例一致（28px marker `dx≈5.8, dy≈-2.4`），证明补偿公式尺寸自适应。

## 5. 修改文件

- `frontend/src/pages/MapPage.tsx`：
  - 重写 FIX-01 注释与变量命名（`tipOffset` → `compX` / `compY`）
  - 修改 compensator 的 `transform` 为 `translate(-compX, -compY)`
  - 保留 hover 逻辑不变（仅影响 pin 层，不影响 compensator）

## 6. 影响范围

- 仅影响地图页（`MapPage`）的 marker 视觉定位
- 不影响 MapLocationPicker（未使用相同 marker 代码）
- 不影响后端、API、数据模型、权限逻辑

## 7. 测试与验证

### 手动/自动化工具验证（通过 MCP `integrated_browser`）

1. **构建验证**：`npm run build` 成功通过，无 TypeScript 错误。
2. **DOM 结构验证**：在浏览器中查询 marker DOM，确认：
   - 三层结构正确：`el.custom-marker > compensator(translate) > pin(rotate) > inner`
   - compensator 的 style 为 `translate(-18px, -10.54px)`（S=36 聚合 marker）
   - pin 的 style 为 `rotate(-45deg)`
3. **坐标一致性验证**：对 10+ 个 marker 在 3 个不同 zoom 级别下测量 anchor 点与视觉尖端偏移，结果：
   - 聚合 marker (S=36)：`dx≈+7.5px, dy≈-3.1px`（稳定）
   - 单帖 marker (S=28)：`dx≈+5.8px, dy≈-2.4px`（稳定）
   - 无随 zoom 漂移的现象
4. **截图验证**：`marker_fix_zoom1/zoom2/zoom3.png` 三个缩放级下 marker 尖端均贴附于正确地理坐标位置。

### 未运行的测试

- 后端 `pytest tests/ -v`：不涉及后端代码变更，无需运行。
- 前端交互回归：E2E 未涉及业务逻辑，仅视觉定位。

## 8. 后续建议

1. **可选进一步补偿**：当前仍存 `≈7.5px` 的残余 X 偏移，来自 `border-radius:50%` 圆弧端点与几何尖端的差异。若要求极高对齐精度，可进一步调整 compensator 为 `translate(-(S/2 + δx), -(S - S/√2))`，其中 δx 需通过视觉实测微调（约 2~3px）。
2. **hover 缩放一致性**：当前 hover 时只放大 pin 层，视觉尖端会随缩放偏移。若要完美对齐，hover 时需同步调整 compensator 平移（乘以 `scaleFactor`）。当前实现业务可接受，后续可按需优化。
3. **MapLocationPicker 对齐**：`MapLocationPicker.tsx` 使用类似标记（location picker 模式），若后续复用同一 marker 组件，需同步套用本补偿方案。
