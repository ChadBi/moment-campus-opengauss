# 任务报告：MapLibre Marker 与 GCJ-02 坐标彻底对齐

## 1. 任务概述

本任务解决地图帖子 Marker 在缩放时与高德底图视觉错位的问题，并统一项目坐标语义。原始方案先修正旋转方块的尖端几何，用户复验后进一步发现“三校各有一个食堂稳定、其他点漂移”。复核表明，仅证明 DOM Marker 的水滴尖端与其 DOM 锚点重合并不充分：高德栅格瓦片位于 WebGL canvas，DOM Marker 位于独立 overlay，两层仍可能经历不同的动画帧、合成和像素取整。

最终方案取消地图页的 DOM Marker，将帖子点改为 MapLibre 原生 GeoJSON source + symbol layer，使标记与高德瓦片由同一个 WebGL canvas、同一投影和同一渲染帧绘制；同时将数据库、API、导入和定位契约统一为 GCJ-02。

## 2. 已完成内容

- 地图帖子点由 `maplibregl.Marker` 重写为 MapLibre 原生 symbol layer，页面中旧 `.custom-marker` 数量为 0。
- 保留 28px 单帖、36px 聚合、水滴尖端、分类颜色、白点/数量、hover 底部固定缩放、点击侧栏、同点聚合和深链接行为。
- 增加请求序列保护，避免学校切换或快速缩放时旧请求覆盖新学校图层。
- 建立 GCJ-02 唯一业务契约；浏览器 WGS-84 定位在前端转换，地图点击/API/CSV 直接使用 GCJ-02。
- 建立江南大学 15 点、复旦大学 12 点、浙江大学 12 点坐标目录，区分 `amap_poi` 与 `demo_approximate`。
- 更新三校中心、种子数据、API 文档、数据字典、导入说明、小程序约定，并增加保护式 Alembic 迁移与只读审计脚本。
- 修复最终回归发现的 AI 发布摘要被硬编码为 `None`、发布表单下拉框缺少可访问名称等已有缺陷。
- 恢复前端完整 Playwright 基线，使当前 28 项用例为 27 通过、1 个已下线历史能力跳过。
- 完成 MCP 真实业务验收：地图点选发布、管理员审核、普通用户证实、权限拒绝、三校缩放锚点核验。

## 3. 未完成内容

本任务目标范围暂无未完成项。

非阻断的既有质量债务：axe 仍报告若干 `color-contrast` serious 提示，学校切换器高度为 40px（建议触控目标 44px）；后端 79 个 skip 为当前环境未安装高级数据库对象或测试明确跳过的场景；前端 1 个 skip 为已按产品决策下线的“官方发布主体”历史用例。

需要注意：高德栅格底图会在不同 zoom 使用不同的 POI 文字/图标排版。Marker 现在固定在地理坐标上；判断坐标是否正确应比较建筑/道路几何，而不是比较可能被制图引擎重新排版的文字标签。`demo_approximate` 点只保证位于对应校区合理范围，不宣称为唯一真实 POI。

## 4. 实现思路

1. 先用确定 SVG 几何纠正旧旋转方块错误：旧 `border-radius` 尖角判断方向有误，实测单帖与聚合分别存在约 `(-14px,-2.40px)`、`(-18px,-3.09px)` 尖端偏差。
2. 用户复验仍见部分点漂移后，放弃 DOM overlay 路径。将水滴 SVG 路径栅格化为 2x 像素比 sprite，以 GeoJSON Point feature 交给 MapLibre symbol layer；使用 `icon-anchor: bottom` 固定尖端。
3. 聚合仍按六位经纬度分组，动态生成分类色/数量 sprite；hover 通过图层 `icon-size` 表达式缩放，底部锚点不变。
4. 点击通过 `queryRenderedFeatures` 和图层事件映射回帖子分组；深链接通过 `post_id -> groupKey` 索引直接打开原侧栏。
5. 坐标层面统一为 GCJ-02，只在浏览器 Geolocation 入口做 WGS-84→GCJ-02，避免多入口重复转换。
6. 数据迁移用“学校 code + 地点名称 + 精确旧坐标”三重保护；downgrade 只回退仍匹配新坐标的记录，避免覆盖人工校正。
7. E2E 不再只测水滴内部几何，而是验证 feature 在 zoom 14/16/18 均能从其 `map.project()` 锚点命中；并以第二食堂、本部食堂、西区食堂为三校基准验证相对投影。

## 5. 修改文件

主要新增文件：

- `backend/app/data/demo_coordinates.py`
- `backend/alembic/versions/c8d9e0f1a2b3_gcj02_demo_coordinates.py`
- `backend/scripts/audit_demo_coordinates.py`
- `backend/tests/test_demo_coordinates.py`
- `frontend/src/utils/coordinates.ts`
- `docs/35_GCJ02坐标规范与三校点位目录.md`
- `AIwork/MapLibreMarker与GCJ02坐标彻底对齐任务报告.md`

主要修改文件：

- `frontend/src/pages/MapPage.tsx`
- `frontend/src/utils/mapMarker.ts`
- `frontend/e2e/map-marker-alignment.spec.ts`
- `frontend/src/components/MapLocationPicker.tsx`
- `frontend/src/components/PostForm.tsx`
- `frontend/src/pages/admin/SchoolImportPage.tsx`
- `backend/scripts/seed_data.py`
- `backend/app/api/map.py`、`categories.py`、`platform.py`
- `backend/app/schemas/post.py`
- `backend/app/services/ai_publish.py`
- `frontend/e2e/accessibility.spec.ts`、`business.spec.ts`、`multi-tenant.spec.ts`、`other-flows.spec.ts`
- `docs/11_technical_architecture.md`、`docs/13_api_specification.md`、`docs/24_需求分析与数据字典.md`、`docs/34_微信小程序接入评估与实施准备报告.md`
- `frontend/README.md`、`TODO.md`、`CHANGELOG.md`

## 6. 影响范围

- 地图页 Marker 的渲染实现被替换，但 API wire shape、点击侧栏、分类筛选、聚合规则、地图点选发帖和多租户行为保持兼容。
- 地图、地点、学校中心、bounds、CSV 导入和距离搜索的经纬度公开语义变为 GCJ-02；字段名和数据库列未变化。
- 浏览器定位自动转换；后台录入、API 调用和 CSV 调用方必须直接提交 GCJ-02。
- 三校演示地点坐标被保护式迁移；帖子通过 `location_id` 自动跟随，无需改帖子外键。
- 最终 MCP 验收在主演示库创建并保留 `Post #87` 和地点“MCP地图验收点”，帖子已审核发布并由 user2 证实，用于复核完整链路。

## 7. 测试与验证

后端与数据：

- Alembic `upgrade head` 成功，当前 revision 为 `c8d9e0f1a2b3`。
- 坐标审计 `--strict`：GCJ-02、39 个目录地点、0 issue、0 outlier。
- 迁移后、MCP 发帖前核对主演示库：3 校中心已更新，`posts=86`、`locations=39`，帖子关联数量未变。
- 坐标/学校 API/导入/租户定向回归：82 通过。
- AI 发布模块：23 通过、2 跳过。
- 后端全量前两轮使用 `localhost` 时分别出现随机的 Docker/openGauss `WinError 64`；第一轮同时发现并修复 AI summary 断言。所有随机错误用例定向复跑均通过。
- 最终将 `TEST_DATABASE_URL` 主机改为 `127.0.0.1` 后全量通过：`919 passed / 79 skipped / 0 failed / 0 errors / 1786 warnings`，耗时 20 分 44 秒。

前端：

- `npm run lint`：0 error，25 个既有 warning。
- `npm run build`：通过；保留 MapLibre 大 chunk 的既有构建提示。
- Marker 专项 Playwright：5/5 通过，覆盖单帖/聚合、无 DOM Marker、hover、点击、zoom 14/16/18、三校基准相对投影和 WGS→GCJ 定位。
- 完整 Playwright：27 通过、1 跳过、0 失败；跳过项为已下线的官方发布主体历史能力。
- axe：0 critical；如实保留 color-contrast serious 与 40px 触控高度提示。

MCP 浏览器真实操作：

- user1 登录后在江南大学地图空白点点击，表单显示 GCJ-02 坐标 `(31.4870784, 120.2641272)`；提交得到 HTTP 201、`Post #87`、状态 `pending`。
- super_admin 在后台审核详情点击“通过”并确认，`PUT /api/v1/admin/posts/87/approve` 返回 200，帖子状态为 `published`。
- user2 打开帖子详情点击“证实”，`POST /api/v1/posts/87/validate` 返回 200，页面进入已证实状态。
- user2 调用 `/admin/stats` 与 `/platform/schools` 均返回 403；管理员审核 UI 正常访问。
- 三校锚点命中：江南 zoom 14/16/18 为 `20/20、20/20、2/2`；复旦为 `16/16、16/16、4/4`；浙大为 `21/21、21/21、2/2`；三校旧 DOM Marker 均为 0。
- 当前工具环境未提供名为 `integrated_code_mode/run_mcp` 的包装器，实际使用可用的 Playwright MCP 浏览器执行同等真实操作。

清理：

- 已删除 `.playwright-mcp/` 和 `map-audit-current.png`，保留用户提供的 `AIwork/MapLibreMarker对齐问题移交文档.md`。

## 8. 后续建议

- 若后续需要 39 个地点全部达到真实建筑级精度，应逐点获取官方高德 POI 或现场测绘坐标，将 `demo_approximate` 升级为 `amap_poi`，不要按栅格文字标签位置人工对齐。
- 将本机测试数据库连接示例统一改为 `127.0.0.1`，降低 Windows Docker Desktop 长套件随机连接重置概率。
- 单独安排无障碍视觉优化任务，处理 axe color-contrast serious 提示并把学校切换器触控高度提高到至少 44px。
- 为 MapLibre 大 chunk 继续评估动态导入；该构建提示不影响本次功能正确性。
