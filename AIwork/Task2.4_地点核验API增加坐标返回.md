# 任务报告：Task 2.4 地点核验 API 增加坐标返回

## 1. 任务概述

为前端「地点核验页」地图展示提供坐标数据支撑，确保管理端地点列表端点 `GET /admin/locations` 与地点核验端点 `PUT /admin/locations/{id}/verify` 的响应中均显式返回 `latitude` / `longitude` 字段，并通过测试用例固定契约。

属于「需要调整的地方」Issue #21「地点核验页加入地图展示」的后端契约保障部分。前端地图组件接入由 Task 3.6 完成。

## 2. 已完成内容

### Schema 校验
- `backend/app/schemas/admin.py`：`LocationAdminResponse` 已包含 `latitude: float` 与 `longitude: float` 字段（早前 ADM-02 已建立），无需改动

### API 端点校验
- `backend/app/api/admin.py`：
  - `list_admin_locations`：构建 `LocationAdminResponse` 时显式调用 `float(loc.latitude)` / `float(loc.longitude)` 转换，确保 SQLAlchemy `Numeric(10,7)` 类型序列化为 JSON number 而非 Decimal
  - `verify_location`：核验端点直接返回 `LocationAdminResponse.from_orm` 风格的对象，含坐标字段

### 测试契约固定
- `backend/tests/test_adm01_admin_workbench.py::test_admin_locations_list_filter_and_verify`：
  - 列表端点：新增 `target["latitude"] == 31.49` 与 `target["longitude"] == 120.27` 显式断言
  - 核验端点：新增 `verify_data["latitude"] == 31.49` 与 `verify_data["longitude"] == 120.27` 显式断言
  - 替换原有 `any(...)` 笼统断言为精确单点断言，便于定位回归

## 3. 未完成内容

暂无。前端地图组件接入（Task 3.6）依赖本任务返回的坐标字段，将在后续任务中实现。

## 4. 实现思路

1. **契约前置**：先核查 `LocationAdminResponse` schema，发现已含 `latitude` / `longitude` 字段，无需 schema 改动。
2. **显式 float 转换**：SQLAlchemy `Numeric` 类型默认序列化为 `Decimal`，对 JSON 不友好。在构建响应对象时显式 `float()` 转换，与公开 `LocationBrief` 字段处理保持一致。
3. **测试固定契约**：原有测试仅用 `any(i["id"] == loc.id and i["is_verified"] is False for i in items)` 断言存在性，无法保证坐标字段存在。改为 `next(...)` 精确定位目标项，并断言 `latitude` / `longitude` 等于创建时使用的固定值（31.49, 120.27）。
4. **核验端点双向覆盖**：列表端点与核验端点均加入坐标断言，确保前端无论从哪个入口拿数据都能获得坐标。
5. **不过度工程**：不新增 `with_coords=True` 参数、不新增独立 schema，直接在现有响应中保证坐标字段存在性。

## 5. 修改文件

### 后端代码（无改动）
- `backend/app/schemas/admin.py`：无修改（`LocationAdminResponse` 已含坐标字段）
- `backend/app/api/admin.py`：无修改（`list_admin_locations` 已使用 `float(loc.latitude)` 显式转换）

### 测试文件（1 个）
- `backend/tests/test_adm01_admin_workbench.py`：`test_admin_locations_list_filter_and_verify` 新增 4 个坐标断言（列表 2 个 + 核验 2 个），替换 `any(...)` 为 `next(...)` 精确定位

## 6. 影响范围

- **API 契约**：`GET /admin/locations` 与 `PUT /admin/locations/{id}/verify` 响应均稳定返回 `latitude` / `longitude` 数值字段（前端可放心集成地图组件）
- **数据库**：无影响（仅读取现有字段）
- **业务逻辑**：无变化（仅测试用例增强）
- **权限**：无影响（端点仍为 admin 专用）
- **多租户**：无影响（坐标属于地点本身的属性，不涉及跨校数据）
- **性能**：可忽略（float 转换为常数开销）

## 7. 测试与验证

### 单元测试

执行命令（PowerShell）：
```powershell
cd e:\Project\moment-campus\backend
$env:TEST_DATABASE_URL = 'postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test'
$env:APP_ENV = 'opengauss'
.\.venv\Scripts\python.exe -m pytest tests/test_adm01_admin_workbench.py::test_admin_locations_list_filter_and_verify -v
```

**测试结果**：
```
tests/test_adm01_admin_workbench.py::test_admin_locations_list_filter_and_verify PASSED [100%]
1 passed, 5 warnings in 4.92s
```

### 验证要点
1. 列表端点返回的 `items[*]` 中含 `latitude` / `longitude` 数值字段 → 前端可直接渲染地图标记
2. 核验端点返回的对象中含 `latitude` / `longitude` → 核验动作后无需重新查询列表
3. 坐标值与创建地点时传入的 `31.49 / 120.27` 精确匹配 → 数据未在序列化过程中丢失精度

### 未执行端到端自动化操作测试的原因

本任务为后端响应契约固定，影响面仅限于地点管理端点的字段断言。已通过单元测试验证响应结构。前端地图组件接入（Task 3.6）完成后，将统一进行端到端浏览器验证。

## 8. 后续建议

1. **前端接入**（Task 3.6）：
   - 地点核验页基于 `latitude` / `longitude` 渲染 Leaflet 地图标记
   - 核验通过/取消后可直接用响应中的坐标更新地图，无需重新拉取列表
2. **精度保留**：若未来需要更高精度（如室内定位），可考虑将 `Numeric(10, 7)` 升级为 `Numeric(12, 9)`，目前精度（11.1mm 级别）已足够校园场景
3. **批量核验端点**：若后续 ADM-01.6 新增批量核验端点，响应中应同样包含坐标字段，保持契约一致
