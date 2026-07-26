# 任务报告：T-A-09/10/16 改造 seed_data.py + 江南大学数据 + 填充到 openGauss

## 1. 任务概述

完成 T-A-09、T-A-10、T-A-16 三个任务：
- T-A-09：修改 `backend/scripts/seed_data.py` 初始化逻辑（移除建表、改用清空 + 重置序列）
- T-A-10：执行演示数据填充到 openGauss 容器
- T-A-16：将 seed_data.py 中的学校与地点数据从"华东师大 + 复旦"重写为"江南大学蠡湖校区"，并使全部业务数据（用户、信息、专题集合）关联到江南大学

执行环境：`APP_ENV=opengauss`，加载 `backend/.env.opengauss`，连接 openGauss 7.0.0-RC3 容器中的 `moment_campus` 数据库（21 张表已通过 Alembic 迁移创建）。

## 2. 已完成内容

### 2.1 seed_data.py 改造
- 顶部新增 `import app.db_compat  # noqa: F401`，确保 openGauss 兼容性补丁在 SQLAlchemy 引擎创建前生效
- 新增 `from sqlalchemy import text` 用于执行原生 SQL
- `init_db()` 改为只清空数据：
  - 使用 `TRUNCATE TABLE ... CASCADE` 清空 21 张业务表（按外键依赖逆序列出）
  - 因 openGauss 的 PGXC 架构不支持 `RESTART IDENTITY` 子句，改为循环执行 `ALTER SEQUENCE <table>_id_seq RESTART WITH 1` 逐表重置自增序列
  - 不再调用 `Base.metadata.create_all`（openGauss 已通过 Alembic 创建表）
- `seed_schools()`：替换为 1 所学校——江南大学（code=jiangnan，center_lat=31.483706，center_lng=120.271166，map_zoom=16）
- `seed_locations()`：替换为 15 个江南大学蠡湖校区地点，全部 `school_id=schools[0].id`，坐标基于校区中心做合理偏移（纬度±0.005，经度±0.005）
- `seed_users()`：管理员和 10 个普通用户的 `school_id` 全部指向 `schools[0].id`（原 `schools[i % 2].id` 已改）
- `seed_posts()`：`school` 由 `schools[i % 2]` 改为 `schools[0]`；`location` 由 `locations[i % len(locations)]` 改为 `random.choice(locations)`（在新 15 地点范围内随机选择）
- `seed_topic_collections()`：6 个专题的 `school_id` 全部指向 `schools[0].id`（原 `schools[1].id` 三处已改）
- 保留 comments、validation_records、notifications、reports 的现有逻辑
- `seed_data()` 主函数中 `init_db()` 调用前后的提示信息更新为"清空现有数据"

### 2.2 数据填充执行
- 命令：`$env:APP_ENV='opengauss'; backend\.venv\Scripts\python.exe backend\scripts\seed_data.py`
- 退出码：0
- 输出末尾打印 `✅ 所有演示数据填充完成！`

### 2.3 验证 SQL 执行
通过 `docker exec opengauss su - omm -c "gsql -d moment_campus -p 5432 -c '...'"` 执行了 7 项验证查询 + 1 项坐标明细查询，全部通过。

## 3. 未完成内容

暂无。

## 4. 实现思路

### 4.1 openGauss PGXC 限制处理
首次执行时使用 `TRUNCATE TABLE ... RESTART IDENTITY CASCADE`，触发错误：
```
asyncpg.exceptions.FeatureNotSupportedError: PGXC does not support RESTART IDENTITY yet
```
**原因**：openGauss 基于 PGXC（PostgreSQL-XC 集群架构）实现，未实现 `RESTART IDENTITY` 子句。
**解决方案**：拆分为两步——
1. `TRUNCATE TABLE <all_tables> CASCADE;`（清空数据，CASCADE 处理外键）
2. 对每张表执行 `ALTER SEQUENCE <table>_id_seq RESTART WITH 1;`（手动重置序列）

openGauss 默认序列命名为 `<table>_<column>_seq`，主键列名为 `id`，故序列名为 `<table>_id_seq`，与 SQLAlchemy autoincrement 列的默认命名一致。

### 4.2 坐标设计
所有 15 个地点的坐标均在校区中心 (120.271166, 31.483706) 的 ±0.005 度范围内：
- 纬度范围：31.4812 ~ 31.4863（全部在 31.4787 ~ 31.4887 内）
- 经度范围：120.2700 ~ 120.2745（全部在 120.2662 ~ 120.2762 内）

精度满足前端地图标记显示需求（地点之间最小间距约 0.0003 度，约 30 米）。

### 4.3 asyncpg 兼容性
- `app.db_compat` 模块已在 `app/database.py` 中导入，但脚本独立运行时需显式导入以确保补丁生效
- 在 `import app.database` 之前插入 `import app.db_compat  # noqa: F401`，保证 `PGDialect._get_server_version_info` 在引擎创建时已被 monkey-patch
- bcrypt 密码哈希保持原状（直接使用 bcrypt 库，未引入 passlib）

## 5. 修改文件

- **修改**：`backend/scripts/seed_data.py`（核心改造，详见第 2.1 节）
- **修改**：`TODO.md`（标记 T-A-09、T-A-10、T-A-16 完成；标记 J1、J3 已确认）
- **新增**：`AIwork/T-A-09_10_16_改造seed_data与江南大学数据填充.md`（本报告）

## 6. 影响范围

- **直接影响**：演示数据全部围绕江南大学蠡湖校区展开，原华东师大、复旦相关数据已彻底清除
- **后续影响**：
  - 前端地图页（MapPage）默认中心点仍为上海坐标，需在 T-A-17 中调整为无锡坐标
  - 前端首页信息流的地点名将显示江南大学相关地点（北门、第一食堂、图书馆等）
- **不影响**：
  - 数据库表结构（21 张表字段未变）
  - API 接口定义
  - 认证逻辑、业务规则
  - 演示账号（admin@momentcampus.com / user1~10@example.com，密码 pass123）

## 7. 测试与验证

### 7.1 数据填充脚本执行
```
$env:APP_ENV='opengauss'; backend\.venv\Scripts\python.exe backend\scripts\seed_data.py
```
退出码 0，关键输出：
```
✓ 创建了 1 所学校
✓ 创建了 12 个分类
✓ 创建了 3 个信息类型
✓ 创建了 11 个用户（包含1个管理员）
✓ 创建了 15 个地点
✓ 创建了 30 条信息
✓ 创建了 66 条评论
✓ 创建了 33 条有效性确认记录
✓ 创建了 14 条通知
✓ 创建了 6 个专题集合
✓ 创建了 10 条举报记录
✅ 所有演示数据填充完成！
```

### 7.2 SQL 验证结果

| # | SQL 查询 | 结果 | 期望 | 结论 |
| - | -------- | ---- | ---- | ---- |
| 1 | `SELECT COUNT(*) FROM schools;` | 1 | 1 | ✓ |
| 2 | `SELECT name, code, center_lat, center_lng FROM schools;` | 江南大学 / jiangnan / 31.483706 / 120.271166 | 江南大学 | ✓ |
| 3 | `SELECT COUNT(*) FROM locations;` | 15 | 15 | ✓ |
| 4 | `SELECT name FROM locations ORDER BY id;` | 北门、南门、第一食堂、第二食堂、图书馆、体育馆、田径场、教学楼A区、学士公寓、校园超市、文浩科学馆、大学生活动中心、蠡湖畔、快递服务中心、打印文印店 | 15 个江南大学地点 | ✓ |
| 5 | `SELECT COUNT(*) FROM users;` | 11 | 11（1 管理员 + 10 普通用户） | ✓ |
| 6 | `SELECT COUNT(*) FROM posts;` | 30 | 30 | ✓ |
| 7 | `SELECT COUNT(*) FROM comments;` | 66 | 30+ | ✓ |

### 7.3 坐标合理性验证
额外执行 `SELECT id, name, latitude, longitude FROM locations ORDER BY id;`：
- 所有纬度 ∈ [31.4812, 31.4863]，均位于校区中心 ±0.005 度范围内
- 所有经度 ∈ [120.2700, 120.2745]，均位于校区中心 ±0.005 度范围内
- 序列已重置：`schools.id=1`，`locations.id` 从 1 递增到 15

### 7.4 asyncpg 兼容性
- 连接：通过（gaussdb 用户，DSN 中 `@` 已 URL 编码为 `%40`）
- 版本探测：通过（`app.db_compat` 补丁正常解析 openGauss 7.0.0-RC3 版本串）
- TRUNCATE CASCADE：通过
- ALTER SEQUENCE RESTART WITH 1：通过
- 批量 INSERT（insertmanyvalues）：通过
- 唯一发现的兼容性问题：`RESTART IDENTITY` 子句不被 PGXC 支持，已通过 `ALTER SEQUENCE` 绕过

## 8. 后续建议

1. **T-A-17 前端地图适配**：将 `frontend/src/pages/MapPage.tsx` 的默认中心点从上海坐标改为无锡坐标 `[120.271166, 31.483706]`，缩放级别设为 16
2. **T-A-18 文档同步**：更新 README、docs/18_项目现状说明.md 中涉及"华东师范大学"、"复旦大学"的描述
3. **真实坐标核对**：当前 15 个地点坐标是基于校区中心的合理偏移，后续若需更精确，可通过百度/高德地图拾取器获取真实坐标替换
4. **幂等性**：当前 `init_db()` 已使用 TRUNCATE + ALTER SEQUENCE，可重复执行 seed_data.py 而不会出现主键冲突
5. **后端启动验证**：T-A-11 可启动后端（`uvicorn app.main:app`）并通过 API 查询验证江南大学数据可正常返回
6. **DELETE 备选方案**：若未来遇到 TRUNCATE 在某些 openGauss 版本上的兼容问题，可降级为按外键逆序 `DELETE FROM` + `ALTER SEQUENCE`
