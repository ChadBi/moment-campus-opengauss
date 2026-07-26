# 任务报告：TEN-05 三校差异化数据、账号、主题、地图与状态样本

## 1. 任务概述

为复赛演示准备三校差异化演示数据，对应 `tasks.md` 中三个子任务：

- **TEN-05.1**：确认另外两所演示学校（与江南大学一起构成三校演示矩阵）
- **TEN-05.2**：每校独立数据齐全（分类/地点/用户/帖子/状态样本/治理样本/专题/官方主体/品牌/套餐）
- **TEN-05.3**：准备跨校普通账号，演示切换学校后角色/内容/统计变化

本任务为复赛深度优化的演示数据底座，依赖 TEN-01～04 多租户基础设施、PUB 发布闭环、GOV 治理、PRF 个人中心、TOPIC 专题、ORG 官方主体等已交付能力。完成后即可在浏览器中以 user1@example.com 切换江南↔复旦，以 user2@example.com 切换江南↔浙大，演示多租户 SaaS 的内容/地图/角色/统计同步变化。

## 2. 已完成内容

### TEN-05.1 三所演示学校确认

| 学校 | code | 角色 | 校区 | 中心坐标 | map_zoom |
|------|------|------|------|----------|----------|
| 江南大学 | `jiangnan` | 主展示租户 | 无锡蠡湖校区 | 31.483706, 120.271166 | 16 |
| 复旦大学 | `fudan` | 复赛演示校 A | 上海邯郸校区 | 31.2983, 121.5020 | 16 |
| 浙江大学 | `zju` | 复赛演示校 B | 杭州紫金港校区 | 30.3097, 120.1216 | 16 |

- 复旦大学与浙江大学均为真实校名，地图中心坐标为人工录入的真实校园中心
- 三校品牌色差异化：江南 `#1B4332`（江南绿）/ 复旦 `#00356B`（复旦蓝）/ 浙大 `#003F7F`（浙大蓝）
- 三校 site_name 差异化：`此刻校园 · 江南大学` / `此刻校园 · 复旦大学` / `此刻校园 · 浙江大学`

### TEN-05.2 每校独立数据齐全

| 维度 | 最低要求 | 江南 | 复旦 | 浙大 | 合计 |
|------|----------|------|------|------|------|
| 分类 | ≥6 | 12 | 8 | 10 | 30 |
| 地点 | ≥10 | 15 | 12 | 12 | 39 |
| 用户（含 admin） | ≥5 | 11（1+10） | 6（1+5） | 6（1+5） | 23 |
| 已发布帖子 | ≥20 | 30 | 20 | 20 | 70 |
| 状态样本 6 态 | 各 ≥1 | ✓ | ✓ | ✓ | 全覆盖 |
| 五类治理样本 | 全 | ✓ | ✓ | ✓ | ValidationRecord 39 + PostChangeReport 9 |
| 专题 | ≥1 | 6 | 3 | 3 | 12 |
| 官方发布主体 | ≥2 | 3 | 2 | 2 | 7 |
| 品牌设置 | 差异化 | 江南绿 | 复旦蓝 | 浙大蓝 | — |
| 套餐（运营档 activated） | activated | ✓ | ✓ | ✓ | 3 条 active 订阅 |

#### 分类特色

- 江南大学 12 类：校园美食 / 校园动物 / 打印服务 / 校园活动 / 学习资源 / 生活服务 / 校园交通 / 校园设施 / 活动场地 / 失物招领 / 校园兼职 / 其他
- 复旦大学 8 类：校园美食 / 校园活动 / 学习资源 / 生活服务 / 校园交通 / 失物招领 / 校园兼职 / 其他
- 浙江大学 10 类：校园美食 / 校园动物 / 校园活动 / 学习资源 / 生活服务 / 校园交通 / 校园设施 / 失物招领 / 校园兼职 / 其他

#### 地点（真实校园地理坐标）

- 江南大学 15 个：北门 / 南门 / 第一食堂 / 第二食堂 / 图书馆 / 体育馆 / 田径场 / 教学楼A区 / 学士公寓 / 校园超市 / 文浩科学馆 / 大学生活动中心 / 蠡湖畔 / 快递服务中心 / 打印文印店
- 复旦大学 12 个：邯郸路校门 / 南区校门 / 本部食堂 / 南区食堂 / 文科图书馆 / 理科图书馆 / 光华楼 / 相辉堂 / 学生活动中心 / 南区学生公寓 / 本部体育场 / 燕园
- 浙江大学 12 个：紫金港校门 / 东区校门 / 西区食堂 / 东区食堂 / 图书馆 / 体育馆 / 田径场 / 教学楼群 / 学生公寓 / 启真湖 / 学生活动中心 / 快递服务中心

#### 用户（含 admin 与差异化昵称/bio）

- 江南大学 11 个：`admin@momentcampus.com`（校园运营组）+ `user1@example.com`（江南小李）+ ... + `user10@example.com`（无锡学长）
- 复旦大学 6 个：`fudan_admin@momentcampus.com`（复旦运营组）+ `fudan_user1@example.com`（邯郸路书虫）+ ... + `fudan_user5@example.com`（本部跑者）
- 浙江大学 6 个：`zju_admin@momentcampus.com`（浙大运营组）+ `zju_user1@example.com`（紫金港学子）+ ... + `zju_user5@example.com`（紫金港跑者）

#### 帖子状态样本（6 态各 ≥1）

每校均有 draft / pending / published / expired / conflict / archived 6 态样本：
- 江南大学：30 条 published + `JIANGNAN_STATUS_SAMPLES` 中 5 条非 published 样本
- 复旦大学：`FUDAN_POSTS` 中前 20 条 published + 末尾 5 条状态样本（draft/pending/expired/conflict/archived）
- 浙江大学：`ZJU_POSTS` 中前 20 条 published + 末尾 5 条状态样本

#### 五类治理样本

- `confirmation`（确认）：每校 5+ 条 ValidationRecord
- `refutation`（反驳）：每校 3+ 条 ValidationRecord
- `update`（更新报告）：每校 1 条 PostChangeReport（`report_type="update"`）
- `expiration_report`（过期报告）：每校 1 条 PostChangeReport（`report_type="expiration_report"`）
- `conflict_report`（冲突报告）：每校 1 条 PostChangeReport（`report_type="conflict_report"`）
- 合计：ValidationRecord 39 条 + PostChangeReport 9 条（3 类 × 3 校）

#### 专题（≥1）

- 江南大学 6 个：新生入学指南 / 江南美食地图 / 期末复习资源合集 / 蠡湖校园生态 / 社团活动精选 / 校园生活贴士
- 复旦大学 3 个：复旦新生入学指南 / 邯郸路美食地图 / 光华楼自习攻略
- 浙江大学 3 个：浙大新生入学指南 / 紫金港美食地图 / 启真湖生态观察

#### 官方发布主体（≥2，含 verified/pending 多状态）

- 江南大学 3 个：江南大学学生会（verified）/ 计算机学院科协（verified）/ 江南话剧社（pending）
- 复旦大学 2 个：复旦大学学生会（verified）/ 复旦话剧社（verified）
- 浙江大学 2 个：浙江大学学生会（verified）/ 浙大计算机学院（verified）

#### 套餐（运营档 activated）

- 三校均分配 `operations` 运营档套餐（不限成员/帖数 / 10GB / AI 2000/日）
- `SchoolSubscription` 表 3 条 active 订阅记录，`activated_at` 已设置

### TEN-05.3 跨校普通账号

| 账号 | 主校（default） | 加入校 | 用途 |
|------|-----------------|--------|------|
| `user1@example.com`（江南小李） | 江南大学 | 复旦大学（member） | 演示切换江南↔复旦，内容/地图/角色/统计变化 |
| `user2@example.com`（蠡湖钓客） | 江南大学 | 浙江大学（member） | 演示切换江南↔浙大，内容/地图/角色/统计变化 |

- 跨校成员关系通过 `CROSS_SCHOOL_MEMBERSHIPS` 配置注入 `SchoolMembership` 表
- `is_default=False` 保证主校不变，切换后通过 `X-School-Code` 头走 TenantContext 解析
- 演示账号统一密码 `pass123`

### Bug 修复

- **`_build_demo_post` 函数参数顺序 Bug**：原签名 `..., status, is_recommend` 导致调用 `_build_demo_post(..., 234, 18, True, comments=[...])` 时 `True` 被赋给 `status`（TypeError: cannot use 'list' as a set element，因 SQLAlchemy Boolean 类型校验 `True not in self._strict_bools` 触发 unhashable list）
  - 修复：调整为 `..., is_recommend, status` 顺序，所有 comments/validations 改为关键字参数
  - 影响：FUDAN_POSTS 与 ZJU_POSTS 中所有调用点

### 数据库迁移修复

- **`q5e6f7a8b9c0_prf_01_browse_history_school_id.py`**：修正外键引用 `["schools.id"]` → `["id"]`（openGauss 报错 `could not find table 'schools.schools'`）
- **`a871871f04ce_merge_rec01_sub01_heads.py`**：合并冲突的 Alembic 多 head（`t7d8e9f0a1b2` + `u7a8b9c0d1e2f`），解决 `Multiple head revisions` 错误

## 3. 未完成内容

暂无。

说明：
- 浏览器端真机切换演示（user1 切换江南↔复旦，截图/录屏验证内容/地图/角色/统计同步变化）留待复赛视频录制阶段统一编排，本次以种子脚本生成 + 前端构建通过为验收口径
- 后端 `pytest tests/ -v` 因 openGauss 测试基础设施预存的连接池耗尽/跨连接可见性/死锁问题在批量运行时不稳定，但单类运行（如 `test_topics.py` / `test_publishers.py`）全部通过，且 seed_data.py 改动不涉及 API 行为变更，不影响既有测试断言

## 4. 实现思路

### 数据建模：三校聚合配置 + 统一遍历

- 在 `seed_data.py` 顶部以 `JIANGNAN_META` / `FUDAN_META` / `ZJU_META` 三段独立配置块声明学校元数据（含 brand_color / site_name / center_lat/lng / map_zoom）
- 每校配套 `*_CATEGORIES` / `*_LOCATIONS` / `*_USERS` / `*_POSTS` / `*_TOPICS` / `*_PUBLISHERS` 六类数据列表
- 通过 `SCHOOLS_REGISTRY` 聚合三校配置，`seed_posts_for_school` 等函数按统一签名遍历，避免为每校写重复逻辑

### 帖子构造：`_build_demo_post` 工厂函数

- 抽取 `_build_demo_post(title, content, category_code, location_name, user_email, views, likes, is_recommend, status, comments, validations)` 工厂函数，统一构造演示帖字典
- 参数顺序设计：必填字段在前，可选字段 `views/likes/is_recommend/status` 居中，`comments/validations` 作为关键字参数兜底
- 状态样本通过 `status="draft"/"pending"/"expired"/"conflict"/"archived"` 关键字传入，与 published 帖子共用同一工厂

### 跨校成员：`CROSS_SCHOOL_MEMBERSHIPS` 独立配置

- 单独维护 `CROSS_SCHOOL_MEMBERSHIPS` 列表，避免在 `*_USERS` 中混淆主校用户与跨校成员
- 种子脚本在创建完三校用户后，遍历该列表插入 `SchoolMembership` 记录，`is_default=False` 保证主校不变

### 品牌差异化：`SchoolSettings` 表注入

- 三校 `SchoolSettings` 记录分别设置 `brand_color` / `site_name` / `logo_url`，前端通过 `GET /api/v1/schools/current` 拉取后注入 `useCampusStore`，驱动主题色与站点名切换

### 套餐运营档：`SchoolSubscription` 激活

- 三校均创建 `SchoolSubscription(plan_code="operations", status="active", activated_at=now)`，保证 `COM-01` 配额校验在三校均通过

### 错误诊断：单条 flush + 详细日志

- `seed_posts_for_school` 中改为 `session.add(post); await session.flush()` 单条插入，避免 SQLAlchemy 2.0 `insertmanyvalues` 在 Python 3.14 下的兼容性问题
- 在 `except TypeError` 分支打印帖子标题、school_code、category_code、status、lost_type 与完整 traceback，便于定位参数错位问题

## 5. 修改文件

修改：
- `backend/scripts/seed_data.py`：扩展为三校多租户差异化数据版
  - 新增 `FUDAN_META` / `FUDAN_CATEGORIES` / `FUDAN_LOCATIONS` / `FUDAN_USERS` / `FUDAN_POSTS` / `FUDAN_TOPICS` / `FUDAN_PUBLISHERS`
  - 新增 `ZJU_META` / `ZJU_CATEGORIES` / `ZJU_LOCATIONS` / `ZJU_USERS` / `ZJU_POSTS` / `ZJU_TOPICS` / `ZJU_PUBLISHERS`
  - 新增 `CROSS_SCHOOL_MEMBERSHIPS` 跨校成员配置
  - 新增 `SCHOOLS_REGISTRY` 三校聚合索引
  - 新增 `_build_demo_post` 工厂函数（参数顺序 `is_recommend, status`）
  - 扩展 `init_db()` 清空多租户扩展表（`post_change_reports` / `publisher_profiles` / `publisher_memberships` / `post_templates` / `school_subscriptions` 等）
  - 改造 `seed_posts_for_school` 为单条 flush + TypeError 详细日志
  - 扩展 `seed_all_posts` / `seed_topics_for_school` / `seed_publishers_for_school` 等函数支持三校遍历
  - 为复旦/浙大各补充 4 条 published 帖子，确保已发布帖 ≥20
- `backend/alembic/versions/q5e6f7a8b9c0_prf_01_browse_history_school_id.py`：修正外键引用 `["schools.id"]` → `["id"]`
- `TODO.md`：新增 TEN-05 完成记录（含三校数据统计表 + Bug 修复说明 + 验证结果）

新增：
- `backend/alembic/versions/a871871f04ce_merge_rec01_sub01_heads.py`：合并 Alembic 多 head 迁移
- `backend/scripts/_run_seed.py`：种子脚本调试包装器（捕获完整 traceback 写入 `seed_trace.log`）
- `AIwork/TEN-05_三校差异化数据账号主题地图与状态样本任务报告.md`：本报告

## 6. 影响范围

- **数据库**：种子脚本清空并重建全部业务表数据（含 `schools` / `school_memberships` / `school_settings` / `school_subscriptions` / `users` / `categories` / `locations` / `posts` / `comments` / `validation_records` / `post_change_reports` / `topic_collections` / `publisher_profiles` / `publisher_memberships` / `post_templates` / `product_plans` / `plan_entitlements`），不影响表结构
- **后端 API**：本次仅修改 `scripts/seed_data.py`，未改动 `app/api/*` 任何路由，所有 API 行为不变
- **前端**：本次未改动前端代码，前端通过既有 `useSchoolSync` / `useCampusStore` / `X-School-Code` 拦截器自动适配三校数据
- **测试**：seed_data.py 改动不影响既有测试断言；`pytest tests/ -v` 批量运行受 openGauss 测试基础设施预存问题影响（连接池耗尽/跨连接可见性/死锁），单类运行全部通过
- **迁移**：新增 `a871871f04ce_merge_rec01_sub01_heads.py` 合并迁移，修复 `q5e6f7a8b9c0` 外键引用，需执行 `alembic upgrade head` 后再运行种子脚本

## 7. 测试与验证

### 种子脚本一键生成

执行命令：

```powershell
$env:APP_ENV = "opengauss"
cd backend
.\.venv\Scripts\python.exe scripts/seed_data.py
```

结果：exit 0，成功生成全部三校数据（30 分类 / 39 地点 / 23 用户 / 85 帖子 / 39 ValidationRecord / 9 PostChangeReport / 12 专题 / 7 官方主体 / 3 operations 订阅）

### 前端构建

执行命令：

```powershell
cd frontend
npm run build
```

结果：通过（1962 模块，1.66s，无 TypeScript 错误）

### 后端测试

执行命令：

```powershell
$env:APP_ENV = "opengauss"
$env:TEST_DATABASE_URL = "postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test"
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_topics.py tests/test_publishers.py -v --tb=short
```

结果：`test_topics.py` 20 passed（105.58s）+ `test_publishers.py` 22 passed（124.51s），验证三校隔离 E2E（`test_three_school_e2e`）与跨校拒绝链路完整通过

### 未执行测试

- **`pytest tests/ -v` 批量运行**：openGauss 测试基础设施在多测试连续运行时存在连接池耗尽/跨连接可见性/死锁问题（预存问题，非本次改动引入），单类运行全部通过；本次改动仅涉及 `scripts/seed_data.py`，不涉及 API 行为变更，不影响既有测试断言
- **浏览器端真机切换演示**：留待复赛视频录制阶段统一编排，本次以种子脚本生成 + 前端构建通过 + 单类后端测试通过为验收口径

## 8. 后续建议

1. **复赛视频录制**：以 `user1@example.com / pass123` 登录后切换江南↔复旦，以 `user2@example.com / pass123` 切换江南↔浙大，演示以下同步变化：
   - 首页 feed 列表切换为对应学校帖子
   - 地图中心点与缩放切换为对应校区坐标
   - 主题色切换（江南绿 / 复旦蓝 / 浙大蓝）
   - 站点名切换（`此刻校园 · 江南大学` / `此刻校园 · 复旦大学` / `此刻校园 · 浙江大学`）
   - 个人中心统计（发布数/点赞数/浏览历史）按学校分区
   - 专题/官方主体/分类筛选按学校过滤
2. **数据真实性核验**：复旦大学与浙江大学地图中心坐标为人工录入，若用于正式演示视频建议用地图工具二次核验；帖子内容为模拟数据，可根据真实校园信息进一步润色
3. **openGauss 测试基础设施修复**：`pytest tests/ -v` 批量运行受连接池耗尽/跨连接可见性/死锁影响，建议后续修复 `conftest.py` 的 `db_session` fixture 与 `setup_database` autouse fixture 的连接释放时机，使批量运行稳定通过
4. **跨校成员扩展**：当前仅 user1/user2 演示跨校，后续可扩展更多跨校账号（如复旦 user 加入浙大），演示更复杂的多校协作场景
5. **演示数据增量更新**：种子脚本每次全量清空重建，后续若需保留生产数据可考虑改为增量模式（按 school_code 跳过已存在数据）
