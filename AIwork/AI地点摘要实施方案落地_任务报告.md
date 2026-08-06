# 任务报告：AI 地点摘要实施方案落地

## 1. 任务概述

依据《评委反馈与产品优化方案》执行重构：将文档改成六部分的内部实施方案，建立“地点稳定资料 + 近期动态 AI 摘要 + 来源追溯 + 管理员审核”的闭环，并彻底移除实时定位、附近、距离和最近排序产品入口。

## 2. 已完成内容

- 重写 `docs/此刻校园_评委反馈与产品优化方案.md`，明确已实现、本轮开发和后续设想，并补齐来源范围、证据门槛、冲突、版本、刷新、开发顺序和量化验收指标。
- 新增 `location_facts`、`location_fact_proposals`、`location_summary_versions` 数据模型、Schema 和 Alembic 迁移；地点增加当前已批准摘要引用及 dirty 标记。
- 认证用户可提交地点资料提议，管理员可整批批准/驳回；批准后更新稳定资料并触发摘要刷新。
- 实现 AI 摘要来源快照、7 天帖子/30 天评价过滤、被证伪内容排除、双用户动态证据门槛、冲突输出、虚构来源拒绝、服务端可信层级和来源卡片。
- 实现摘要待审队列、批准/驳回、旧版本归档、dirty worker、调用日志复用和失败回退；Web/小程序地点详情接入稳定资料、摘要、证据和补充入口，管理端增加两类队列。
- 从有效代码和产品文案中移除 `/locations/nearby`、Haversine、距离字段、`nearest`、实时位置授权和相关入口；保留学校静态地图、地点坐标和帖子地点关联。
- 将历史 TODO、旧方案和测试记录标记为历史/已废弃；附近回归测试改为接口不可访问边界测试。

## 3. 未完成内容

- 后端全量 `pytest tests/ -v` 已执行但在 10 分钟窗口内超时，未宣称通过；目前完成了本任务相关的 14 项专项回归。
- 当前仓库存在任务开始前就已存在的 Alembic 重复 revision/cycle（含重复 `a1b2c3d4e5f6`），`alembic current/heads` 无法解析，因此演示数据库尚未应用地点知识层迁移，网页端真实数据 E2E 被阻断。
- 当前工具集中没有 `integrated_code_mode` 或 `run_mcp`；使用可用 Playwright 做了页面冒烟，但因上述迁移阻断，未完成“提交资料→批准→worker→摘要审核→用户查看来源”的完整 E2E。
- 小程序已完成 TypeScript 类型检查；本轮未获得微信开发者工具编译工具，未重复执行模拟器编译。

## 4. 实现思路

- 稳定资料和动态摘要分层：低频事实只能由认证用户提议、管理员审核后写入事实表；AI 只整理近期帖子和评价。
- 生成前构造当前学校/地点的不可变来源快照并计算哈希，动态结论至少要求两个不同用户来源；服务端验证所有来源 ID 和可信层级，模型不能自行扩展事实或选择冲突一方。
- 摘要生成只进入 `pending_review`，管理员同时查看正文、结论、来源和冲突后才切换地点当前摘要；新版本待审、驳回或失败期间继续读旧的已批准版本。
- 通过帖子、评价、协同验证、地点资料等事件统一设置 `summary_dirty_at`，后台 worker 异步处理，避免用户访问时现场生成。
- 删除实时定位产品链路，地图只承担学校静态空间组织；首页和地图后续只消费已批准摘要。

## 5. 修改文件

**后端**

- `backend/app/models/location_fact.py`、`location_summary.py`、`location.py`、`user.py`
- `backend/app/schemas/location_knowledge.py`、`location_review.py`
- `backend/app/api/locations.py`、`location_knowledge.py`、`router.py`
- `backend/app/services/location_summary.py`、`backend/app/jobs/location_summary_worker.py`
- 帖子、评价、协同验证触发 dirty 的 API/服务，以及 `backend/scripts/location_summary_worker.py`
- `backend/alembic/versions/a6b7c8d9e0f1_location_knowledge.py`
- `backend/tests/test_location_knowledge.py`、`test_location_summary_unit.py`、`test_location_reviews.py`、`test_nearby.py`

**Web / 小程序 / 运维**

- `frontend/src/services/locations.ts`、`LocationPage.tsx`、管理端地点页、搜索/地图类型与新手引导
- `miniprogram/services/locations.ts`、地点详情页面、全局类型、隐私说明和 `app.json`
- `deploy/bare-metal/moment-location-summaries.service/.timer` 及安装、更新、混合部署脚本

**文档与项目记录**

- `docs/此刻校园_评委反馈与产品优化方案.md` 及相关有效产品文档/历史废弃标记
- `TODO.md`、`CHANGELOG.md`
- 本报告：`AIwork/AI地点摘要实施方案落地_任务报告.md`

## 6. 影响范围

- 数据库新增地点事实、提议、摘要版本和摘要引用字段；部署前必须先处理现有 Alembic 图问题并执行迁移。
- 地点详情 API 返回稳定资料和已批准摘要；新增用户提议、管理员审核、摘要查询和手动刷新接口。
- Web 与小程序地点详情的展示顺序、空状态和审核门禁发生变化；地图和首页不再依赖用户定位或距离排序。
- 帖子发布/编辑/过期/归档、评价、协同验证和地点资料审核会触发摘要 dirty 标记；新增定时 worker 和 systemd timer。
- 旧 `/locations/nearby` 入口不再提供服务，历史文档仅作归档记录。

## 7. 测试与验证

- `backend/.venv`：`pytest tests/test_location_knowledge.py tests/test_location_summary_unit.py tests/test_location_reviews.py tests/test_nearby.py -q` → **14 passed**。
- `backend/.venv`：`pytest tests/ --collect-only -q` → **1012 tests collected**。
- `backend/.venv`：全量 `pytest tests/ -q` 在约 10 分钟执行窗口内超时，未计为通过。
- Web：`npm run build` → **通过**（仅有 MapLibre 产物体积提示）。
- 小程序：`npm run typecheck` → **通过**。
- 后端 `compileall`、应用导入和 OpenAPI 检查通过；OpenAPI 不包含 `/locations/nearby`，带学校头访问旧路径返回 422（动态地点 ID 路由参数校验）。
- Playwright 页面冒烟可打开 `/locations`，但演示库缺少 `locations.current_summary_id`（迁移未执行）导致真实地点请求 500；已记录为 E2E 阻塞，不伪造完整链路结果。
- `alembic current/heads` 被既有重复 revision 和 cycle 阻断；这是当前部署/真实 E2E 的前置风险。

## 8. 后续建议

- 先单独修复并审计 Alembic revision 图（不得直接改写已部署数据库的历史版本），再执行地点知识层迁移并重跑真实数据 E2E。
- 将全量 pytest 拆成按模块/慢测试批次执行，补齐全量结果；在可用的微信开发者工具中执行小程序编译和地点详情走查。
- 完成认证用户提议→管理员批准→来源变化→worker 生成→摘要审核→用户查看来源的 E2E，并按江南大学 10 个地点开展两周试点。
- 试点持续记录来源可追溯率、证据不足具体结论数、跨校泄漏数、待审回退成功率和相同快照重复调用数，达到文档第 6 节指标后再开放地图摘要预览与首页动态地点卡片。
