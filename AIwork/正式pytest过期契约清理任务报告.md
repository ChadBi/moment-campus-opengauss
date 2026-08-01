# 任务报告：正式 pytest 过期契约清理

## 1. 任务概述

按批准计划清理正式 pytest 收集目录中的 debug/diag、永久 skip、五类验证、favorites、PostType 等过期测试契约，并将地图响应测试更新为当前 `{markers: []}` 响应结构。

## 2. 已完成内容

- 删除正式 pytest 中残留的诊断用例和 debug/diag 字节码缓存。
- 删除 Tag、PostType、PostChangeReport、活动时间等永久下线能力对应的 skip 测试体。
- 删除由模块级永久 skip 屏蔽、且断言历史高级 SQL 对象的 integration 测试模块及专用 fixture。
- 将协同验证 Schema、API 和统计测试统一为 confirmation/refutation 两类正式契约，保留废弃输入返回 422 的负向测试。
- 保留 favorites 表不得重新出现的数据库防回归断言。
- 将地图 N+1 和租户隔离测试更新为从响应对象的 `markers` 字段读取标记列表。
- 修复验证统计测试使用帖子作者自行验证导致 403 的过期测试设置，改为两个非作者用户分别提交证实和证伪。

## 3. 未完成内容

- 未运行后端全量 957 项 pytest；用户要求运行 collect 和相关测试，本次执行了 364 项相关测试。
- 未运行前端构建和端到端浏览器测试；本次仅修改后端正式 pytest，不涉及前端或业务交互实现。
- 测试输出中的 Pydantic、FastAPI、`datetime.utcnow()` 弃用警告及 `UserBrief` 序列化警告未处理，属于本任务范围外的既有问题。

## 4. 实现思路

先以批准计划的任务 17 为边界审计 `backend/tests/`，区分永久下线能力的不可达测试与仍有价值的条件跳过。永久下线测试直接删除，不通过 skip 保留虚假覆盖；废弃验证类型改为负向拒绝契约；地图测试按当前 API 响应对象读取 `markers`。所有验证均显式设置独立测试库 `moment_campus_test`，避免触碰开发数据库。

## 5. 修改文件

- 修改 `backend/tests/conftest.py`。
- 修改 `backend/tests/test_adm01_admin_workbench.py`、`test_adm02_school_settings.py`。
- 修改 `backend/tests/test_ai_publish.py`、`test_ai_search.py`。
- 修改 `backend/tests/test_api_contract.py`、`test_validation_type.py`、`test_schemas.py`。
- 修改 `backend/tests/test_interactions.py`、`test_posts.py`、`test_publish_flow.py`、`test_post_transition.py`、`test_post_detail_dsc02.py`。
- 修改 `backend/tests/test_search.py`、`test_tenant_isolation.py`。
- 删除 `backend/tests/integration/` 下 6 个历史高级 SQL 测试模块及其 `conftest.py`。
- 新增 `AIwork/正式pytest过期契约清理任务报告.md`。

## 6. 影响范围

仅影响后端 pytest 的测试收集、测试契约和任务报告，不修改业务实现、前端、小程序、`TODO.md` 或部署配置。未执行 Git 提交。

## 7. 测试与验证

- 首次未设置 `TEST_DATABASE_URL` 的 collect 被测试库保护主动拒绝，未连接或清空任何数据库。
- 显式设置 `TEST_DATABASE_URL=postgresql+asyncpg://.../moment_campus_test` 后执行 `backend/.venv/Scripts/python.exe -m pytest tests --collect-only -q`：成功收集 957 项，无 debug/diag 测试文件、无 unknown marker。
- 执行 15 个相关测试文件：364 passed，0 failed，764 warnings，用时 305.14 秒。
- 单独复测验证统计与两项地图契约：3 passed，17 warnings，用时 6.68 秒。
- 静态搜索确认正式测试中仅剩 `test_config.py` 的环境条件 skip；五类验证字符串仅用于废弃输入拒绝测试，favorites 仅用于表不存在防回归断言。
- `git diff --check` 发现工作区既有文件存在 EOF 空行和尾随空格；本任务涉及的测试文件格式问题已修复，未修改业务无关文件。

## 8. 后续建议

后续可独立处理测试输出中的弃用与 Pydantic 序列化警告，并在阶段四最终收口时运行后端全量 pytest。若高级 SQL 对象重新纳入 Alembic 现行契约，应基于实际迁移重新建立集成测试，不应恢复本次删除的历史断言。
