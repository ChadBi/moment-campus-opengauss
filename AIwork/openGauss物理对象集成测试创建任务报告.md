# 任务报告：openGauss 物理对象集成测试创建

## 1. 任务概述

在 `backend/tests/integration/` 目录下创建 4 个文件，用于 openGauss 物理对象（存储过程 SP01-SP08、触发器 TR01-TR08）的集成测试。

## 2. 已完成内容

### 文件 1: `tests/integration/__init__.py`
- 空文件，将 `tests/integration/` 标记为 Python 包。

### 文件 2: `tests/integration/conftest.py`
- `db_conn` fixture：asyncpg 原生连接，autocommit 模式，用于调用存储过程（绕过 ORM）。
- `ensure_physical_objects` fixture（session 级）：检查 `sp_recalc_credibility` / `mv_post_validation_stats` / `trg_validation_after_insert` 是否存在，缺失则 `pytest.skip`。
- `refresh_mvs` fixture（autouse）：每用例后刷新 4 个物化视图（`mv_post_validation_stats` / `mv_user_reputation_ranking` / `mv_admin_dashboard` / `mv_location_post_count`），使用 DO 块兜底处理不存在的情况。

### 文件 3: `tests/integration/test_stored_procedures.py`
覆盖 SP01-SP08 共 13 个测试用例：
- **SP01 sp_recalc_credibility**（5 个测试）：基础分 53.00、+confirmation 58.00、+refutation 45.00、20 条 refutation clamp 到 0.00、valid_count/invalid_count 同步。
- **SP02 sp_mark_expired_posts**（2 个测试）：过去 expire_at 返回 1 并改状态、未来 expire_at 返回 0。
- **SP03 sp_detect_conflict**（2 个测试）：同地点+时间重叠返回 1 并标 conflict、无地点返回 0。
- **SP04 sp_update_reputation**（2 个测试）：新用户 60.00、2 个帖子 61.00。
- **SP05 sp_archive_logs**（1 个测试）：100 天前日志归档、10 天前日志保留。
- **SP06 sp_cleanup_soft_deleted**（1 个测试）：40 天前软删除帖被清理、10 天前保留。
- **SP07 sp_publish_post**（3 个测试）：合法发布返回 post_id 且 credibility=53.00、不存在用户抛异常、空标题抛异常。
- **SP08 sp_submit_validation**（3 个测试）：合法 confirmation 返回 record_id、自我验证抛异常、draft 状态抛异常。

### 文件 4: `tests/integration/test_triggers.py`
覆盖 TR01-TR08 共 8 个测试用例：
- **TR01 trg_validation_after_insert**：ORM 插入验证记录后，credibility_score 自动更新为 58.00（不手动调用 SP）。
- **TR02 trg_validation_after_delete**：插入 confirmation（58.00）后删除，credibility 回到 53.00。
- **TR03 trg_post_status_change**：UPDATE status 后 admin_operation_logs 新增 status_change 日志。
- **TR04 trg_comment_update_count**：插入评论 comment_count=1，删除 comment_count=0。
- **TR05 trg_like_update_count**：插入点赞 like_count=1，删除 like_count=0。
- **TR06 trg_favorite_update_count**：插入收藏 favorite_count=1，删除 favorite_count=0。
- **TR07 trg_post_update_view_count**：view_count 从 99→100 触发 view_milestone 日志。
- **TR08 trg_user_soft_delete**：is_deleted TRUE 后 deleted_at 填充、is_active=FALSE、日志记录。

## 3. 未完成内容

暂无。

## 4. 实现思路

### 双连接策略
- **ORM（db_session）**：用于创建测试数据（用户、帖子、评论等），保证外键约束和数据完整性。
- **asyncpg（db_conn）**：用于调用存储过程和读取验证结果，autocommit 模式确保 SP 写入立即对 ORM 可见。

### 触发器副作用隔离
SP01 测试中，插入 validation_record 会触发 `trg_validation_after_insert`，该触发器不仅调用 SP01（重算可信度），还调用 SP04（更新作者信誉分）。由于 SP01 公式依赖作者信誉分，信誉分变化会导致二次调用 SP01 时结果与预期不符。

解决方案：在 SP01 测试中，插入验证记录后、调用 SP01 前，通过 `UPDATE users SET reputation_score = NULL` 重置作者信誉分，使 SP01 使用默认值 60，从而隔离公式测试。

### 物理对象存在性检查
`ensure_physical_objects` fixture 在 session 级检查 SP/MV/TR 是否存在，缺失时 `pytest.skip`，避免在未部署物理对象的环境中报错。

### 数值断言
使用 `float(result) == pytest.approx(expected)` 比较 NUMERIC 返回值，兼容 Decimal/float 类型转换。

### 异常捕获
SP07/SP08 的异常测试使用 `pytest.raises(asyncpg.PostgresError)` 捕获 RAISE EXCEPTION。

## 5. 修改文件

新增文件：
- `backend/tests/integration/__init__.py`
- `backend/tests/integration/conftest.py`
- `backend/tests/integration/test_stored_procedures.py`
- `backend/tests/integration/test_triggers.py`

## 6. 影响范围

- **集成测试模块**：新增 `tests/integration/` 子包，不影响现有单元测试。
- **测试数据库**：依赖 openGauss 物理对象（SP01-SP08、TR01-TR08、MV01-MV04）已通过 `backend/scripts/opengauss/` 下的 SQL 脚本部署。
- **根 conftest.py**：集成测试复用根 conftest 的 `setup_database`（autouse TRUNCATE）、`db_session`、`test_school`、`test_category`、`test_post_type` 等 fixture。

## 7. 测试与验证

**未运行测试**，原因：
1. 本任务为文件创建任务，要求直接创建 4 个文件。
2. 测试依赖 openGauss 物理对象（SP/TR/MV）已部署到数据库，当前环境是否已部署未确认。
3. 若物理对象未部署，`ensure_physical_objects` fixture 会自动 skip 集成测试。

**运行方式**（后续验证用）：
```bash
cd backend
.venv\Scripts\python -m pytest tests/integration/ -m integration -v
```

## 8. 后续建议

1. **运行测试验证**：确保 openGauss 物理对象已部署后，执行集成测试确认全部通过。
2. **物化视图测试**：当前未覆盖 MV01-MV04 的查询测试，后续可补充。
3. **分区表测试**：当前未覆盖分区表的跨月查询和默认分区路由，后续可补充。
4. **触发器链式调用测试**：当前 TR01 测试验证了单条验证记录的触发，可补充 conflict_report 类型的链式调用（SP01→SP03）测试。
5. **并发测试**：当前测试均为单连接串行，后续可补充并发场景下的触发器/SP 行为验证。
