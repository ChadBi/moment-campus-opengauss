# 任务报告：现行 SQL 与报告生成契约收敛

## 1. 任务概述

排除历史迁移脚本，修复现行 openGauss SQL、`verify_data.py`、`generate_db_design.py` 与 `generate_full_report.py` 对旧收藏、置顶、旧状态和旧三类协同验证的依赖，并通过静态契约及独立测试库事务执行验证。

## 2. 已完成内容

- 现行 SQL 统一使用 6 态 Post 状态、点赞互动及 confirmation/refutation 两类互斥验证。
- `verify_data.py` 移除已删除的 `Favorite` 模型导入，恢复脚本可执行性。
- `generate_db_design.py` 与 `generate_full_report.py` 不再生成收藏结构、收藏文案或旧三类验证内容。
- 新增静态源文件契约，覆盖现行 SQL、四个生成/核验脚本、表空间说明及分类多租户唯一索引。
- 03/04/06/07/08 五个现行 SQL 在独立测试库的同一事务中依次执行成功，并完成回滚。

## 3. 未完成内容

暂无。

## 4. 实现思路

采用 RED→GREEN：先扩展 `test_opengauss_sql_contract.py`，确认 `verify_data.py` 的 `Favorite` 导入和全量报告旧依赖导致测试失败；再做最小修复。静态契约明确排除历史迁移脚本，只扫描当前可执行 SQL。动态验证使用 `moment_campus_test`，将五个 SQL 放入单一事务执行并在断言后回滚，避免污染测试库。

## 5. 修改文件

- `backend/scripts/opengauss/04_create_indexes.sql`
- `backend/scripts/opengauss/06_create_materialized_views.sql`
- `backend/scripts/opengauss/07_create_functions.sql`
- `backend/scripts/opengauss/08_create_triggers.sql`
- `backend/scripts/opengauss/09_create_partitions.sql`
- `backend/scripts/opengauss/performance_test.sql`
- `backend/scripts/verify_data.py`
- `backend/scripts/_check_db.py`
- `backend/scripts/generate_db_design.py`
- `backend/scripts/opengauss/01_create_tablespaces.sql`
- `scripts/generate_full_report.py`
- `backend/tests/test_opengauss_sql_contract.py`
- `AIwork/现行SQL与报告生成契约收敛任务报告.md`

## 6. 影响范围

影响数据库课程设计现行脚本、数据库设计产物生成、课程设计全量报告生成和演示数据核验工具；不修改 Alembic 历史迁移、业务 API、数据库现存数据或前端交互。

## 7. 测试与验证

- RED：定向契约首次运行 11 PASS / 2 FAIL，准确捕获 `verify_data.py` 的 `Favorite` 导入和全量报告旧依赖。
- 首轮 GREEN：`tests/test_opengauss_sql_contract.py -v` 14 PASS，包含独立测试库单事务执行并回滚验证。
- 最终残留扫描再次发现全量报告中的 Favorite、关键表检查中的 post_change_reports 和表空间注释中的 favorites；扩展契约后 RED 为 3 FAIL，修复后最终 16 PASS。
- `verify_data.py` 在本地 openGauss 执行成功：3 校、15 分类、34 用户、90 帖子、42 条验证记录等查询正常。
- 三个 Python 脚本执行 `py_compile` 通过；相关文件 `git diff --check` 通过，仅有 Git 行尾转换提示。
- 前端 `npm run build` 通过，Vite 保留一个既有大 chunk 警告。
- 首次后端全量运行出现 981 PASS / 1 FAIL / 5 ERROR；随后将 SQL 契约、topics、subscriptions 组合为复现集，结果 55 PASS，确认 SQL 事务未泄漏。
- 清理一次性测试库污染后使用 `pytest tests -q -W error` 重跑全量，结果 987 PASS / 0 FAIL / 0 WARNING，耗时 14 分 24 秒。
- 本任务没有修改前端行为；综合流程仍会重跑完整 Web E2E，并在总任务报告中记录。
- 实施代理曾错误更新 `TODO.md`、`CHANGELOG.md` 并创建提交；主流程已撤销提交且保留代码改动，完整回退 TODO/CHANGELOG 内容，最终未提交 Git。

## 8. 后续建议

在 CI 中保留 `test_opengauss_sql_contract.py` 的静态契约和独立测试库事务执行门禁，防止维护 SQL 或报告生成器重新引入已删除契约。
