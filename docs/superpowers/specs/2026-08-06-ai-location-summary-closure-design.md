# AI 地点摘要完整闭环设计

> 文档属性：专项实施设计（2026-08-06）
> 适用范围：`AIwork/AI地点摘要实施方案落地_任务报告.md` 中未完成部分的补齐
> 目标：从“代码骨架已完成”推进到“迁移可运行、主链路可验证、Web/小程序可演示”。

## 1. 背景与问题边界

### 1.1 当前已完成
依据任务报告第 2 节，当前代码已实现：
- 数据模型：`location_facts`、`location_fact_proposals`、`location_summary_versions`，以及 `locations.current_summary_id` / `summary_dirty_at`。
- 业务接口：认证用户提议、管理员审核资料、摘要生成与审核、地点详情读取稳定资料与摘要。
- 异步刷新：帖子、评价、协同验证、资料批准等入口触发 dirty，worker 按快照哈希批处理。
- 前端接入：Web/小程序地点详情与管理端审核队列已接入。
- 旧入口清理：附近、定位、距离与 `nearest` 已移除并改为边界测试。

### 1.2 本轮必须解决的未完成
任务报告第 3 节和 `TODO.md` 第 7 条列出的未完成内容：
1. 后端全量 `pytest tests/ -v` 不能宣称通过（10 分钟窗口超时；即使拆开，也要先保证 Alembic 唯一 head）。
2. Alembic 图存在重复 revision / 分支未合并，`alembic current/heads` 无法解析，演示库尚未应用地点知识迁移。
3. 受迁移阻断，未完成“提交资料 → 批准 → worker → 摘要审核 → 用户查看来源”的真实 E2E。
4. 小程序本轮没有微信开发者工具编译与走查。
5. 方案文档 1.2 仍把“地点稳定资料 / AI 地点摘要”写成本轮开发 / 待开发，与代码实际状态不一致。

### 1.3 不进入本轮范围
- 首页 AI 地点卡片、地图摘要预览、质量仪表盘、两周试点运营（均属于方案后续设想）。
- 扩展新的 AI 来源类型、AI 服务端重新调优、重写摘要 UI。
- 服务器部署与对外发布（本次是本地演示环境闭环）。

## 2. 架构与修复策略

### 2.1 Alembic 历史修复（最优先）

#### 2.1.1 已发现的具体问题
- 重复 revision `a1b2c3d4e5f6`：同时出现在
  - `a1b2c3d4e5f6_t7_post_embeddings.py`（依赖 `0898a6eeb570`）
  - `a1b2c3d4e5f6_unify_edu_email_drop_campus_fields.py`（依赖 `f4b5c6d7a8b9`）
- 重复 revision `a6b7c8d9e0f1`：
  - `a6b7c8d9e0f1_drop_publisher_tables.py` 内部 revision=`a6b7c8d9e0f1`，依赖 `z5e6f7g8h9i0`
  - `a6b7c8d9e0f1_location_knowledge.py` 文件名沿用 `a6b7c8d9e0f1`，但内部实际 revision=`b8c9d0e1f2a3`，依赖 `z5e6f7g8h9i0`
- `z5e6f7g8h9i0` 之后形成两个并行分支：drop-publisher 与 location-knowledge，目前无 merge migration。

#### 2.1.2 选择的修复方案（可重建数据库前提下）
**方案 A：线性唯一 revision + 分支 merge（推荐）**

- 保留语义上的执行顺序：先 drop-publisher，再 location-knowledge。理由是 drop-publisher 清理了 publisher 系列对象，不会影响后续建表；而反过来 location-knowledge 的 FK 约束也不涉及 publisher。
- 处理方式：
  1. 给 `a1b2c3d4e5f6_unify_edu_email_drop_campus_fields.py` 分配全新的 revision（如 `m1n2o3p4q5r6`），并保留其依赖 `f4b5c6d7a8b9`。
  2. 重新定位 `a1b2c3d4e5f6_t7_post_embeddings.py` 的下游：确保任何后续 revision 不把“错误同名的 unify_edu_email 旧 revision”当成父节点。
  3. 重命名 `a6b7c8d9e0f1_location_knowledge.py` 为内部 revision 匹配的文件名（`b8c9d0e1f2a3_location_knowledge.py`），避免文件名继续误导。
  4. 新增一个 merge migration（例如 revision=`n2o3p4q5r6s7`），依赖 `(a6b7c8d9e0f1, b8c9d0e1f2a3)`，`upgrade/downgrade` 均为 `pass`（仅负责合并图，不产生额外 DDL，DDL 已在两个分支内）。
  5. 之后的最新迁移 `d6e7f8a9b0c1` 等，若其父节点在合并之前，则按顺序修正指向 merge revision 或其下游唯一 head。
- 验证标准：
  - `alembic heads` 结果仅一行。
  - `alembic history` 可从初始迁移打印到最新，无重复 revision 提示。
  - 空数据卷上执行 `alembic upgrade head` 成功。
  - 再执行 `alembic downgrade -1 && alembic upgrade head` 往返无错。

**不选择的替代方案：**
- 方案 B（保留冲突，只做最小修改）：revision 名冲突本身会导致 Alembic 解析失败，“只改 down_revision”无法避开重复 ID 报错，因此不选。
- 方案 C（生成全新基线迁移）：会丢失历史可追踪性，本次问题属于少数重复与分支，无需重基线。

### 2.2 数据库重建与种子数据
用户已同意“可重建数据库”，因此执行顺序：
1. `docker compose down -v opengauss`（按项目约定清数据卷）。
2. `docker compose up -d opengauss`，等待端口就绪。
3. `backend/.venv` 中执行 `alembic upgrade head`。
4. `backend/.venv` 中执行 `python scripts/seed_data.py`。
验收：`ai_invocation_logs`、`location_reviews`、`location_facts`、`location_fact_proposals`、`location_summary_versions` 与 `locations.current_summary_id/summary_dirty_at` 的列与表均存在，种子数据不报错。

### 2.3 后端测试补齐与分批执行

#### 2.3.1 新增集成测试（必须落在 `backend/tests/` 下，使用现有 async fixtures）
1. **摘要主链路 API 测试**（新建 `test_location_summary_flow.py`）
   - 场景 A：同一地点两个用户各发一个近 7 天已发布帖子 → Mock AI 返回合法双来源 claim → 生成版本状态 `pending_review`，地点 `current_summary_id` 仍为 NULL。
   - 场景 B：管理员批准该摘要版本 → `current_summary_id` 切换为新版本，旧版本若存在则 `archived`。
   - 场景 C：管理员驳回摘要 → `current_summary_id` 不变，旧版本继续可读。
   - 场景 D：AI 失败 / AI 返回虚构来源 → 生成失败或被拒绝，旧版本仍可读。
   - 场景 E：跨校来源的 POST 帖子 id 不被他校快照读取。
2. **worker 批量处理测试**（同文件或新建 `test_location_summary_worker.py`）
   - 场景 F：地点设置 `summary_dirty_at` → 运行 `run_location_summary_job` → 生成一个 `pending_review` 版本且 dirty 标记被清除。
   - 场景 G：相同 `source_hash` 的第二次执行不会重复生成新版本。
   - 场景 H：失败计数与 advisory lock 不导致抛错。
3. **测试风格约束**
   - 统一复用 `db_session`、`test_school`、`auth_headers`、`admin_headers` 等现有 fixtures。
   - AI 调用走 monkeypatch，不依赖真实网络与 `AI_API_KEY`。

#### 2.3.2 全量 pytest 执行策略
- 先执行地点相关专项：`pytest tests/test_location_knowledge.py tests/test_location_summary_unit.py tests/test_location_reviews.py tests/test_location_summary_flow.py tests/test_location_summary_worker.py tests/test_nearby.py -q`，必须全通过。
- 再按模块分批执行全量（避免 10 分钟窗口超时，同时便于定位慢测试）：
  1. 用户、认证、租户
  2. 帖子、评论、互动、治理
  3. 搜索、AI、日志、个人中心、通知
  4. 管理员端、管理统计
  5. 慢测试单独标记，必要时拆分到最后一批
- 最终每批通过即可宣称全量套件通过（单步超时但单批全部通过，不再算阻塞）。

### 2.4 Web 端真实 E2E（浏览器自动化）
在前后端真实启动的前提下，执行如下链路并保存截图与文字记录：
1. 启动后端：PowerShell 设 `$env:APP_ENV="opengauss"`，`backend/.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000`。
2. 启动前端：`frontend` 目录执行 `npm run dev -- --port 5173`。
3. 登录普通用户（`user1@example.jiangnan.edu.cn / pass123`）：
   - 访问某一江南大学地点详情页，点击“补充地点资料”并提交营业时间+服务说明。
4. 登录管理员（`admin@momentcampus.com / pass123`）：
   - 进入管理后台“地点资料待审”，批准上一条提议。
5. 在后端 console 手动触发一次摘要 worker（直接调用函数或执行 `scripts/location_summary_worker.py`），确认生成 `pending_review` 版本。
6. 管理员进入“AI 摘要待审”，查看摘要正文、来源卡片和结论，然后批准。
7. 普通用户重新进入地点详情：
   - 必须看到“此刻摘要”、结论、来源数量、来源卡片（可点击原帖/评价），且稳定资料区显示刚批准的营业时间。
8. 记录控制台与网络错误，若有 5xx/4xx 异常，修复后重来。

执行方式：使用当前可用的浏览器 MCP `integrated_browser` 的 `browser_navigate / browser_click / browser_type / browser_snapshot / browser_take_screenshot / browser_console_messages / browser_network_requests`，而不是虚构 `integrated_code_mode`。

### 2.5 小程序最小验证（wechatide-skill）
根据项目内存约束，凡涉及小程序编译/预览/页面自动化必须先调用 `wechatide-skill`：
1. 跑 `check_wechatide_status` 门禁。
2. 以项目 `project.config.json` 打开小程序。
3. 触发编译并查看是否有错。
4. 自动打开地点详情页：
   - 空摘要状态展示“暂无足够近期信息”且稳定资料区正常。
   - 认证用户可看到“补充地点资料”表单。
   - 若已有数据：摘要卡片、来源数、冲突或空态文案正确。
5. 记录截图与 console。若小程序需要后端地址调整，按项目现有配置改为本地 8000 端口。

## 3. 数据与接口一致性核对
- 模型字段核对：`Location.current_summary_id`、`summary_dirty_at`、`LocationFact`、`LocationFactProposal`、`LocationSummaryVersion` 与迁移列定义一一对应，不得出现迁移未建列但 ORM 在引用。
- 详情接口核对：`GET /locations/{id}` 返回 `facts/summary/reviews` 三个区块；`GET /locations/{id}/summary` 在无证据时返回 `insufficient`。
- 审核接口核对：管理员批准资料后一定触发 `mark_location_summary_dirty`；批准摘要时必须切换 `current_summary_id` 并归档旧版本。
- 学校隔离核对：跨校地点 ID 读取必须命中学校上下文校验，不可泄漏。

## 4. 文档与交付一致性
- 方案文档第 1.2 节修正口径：“地点稳定资料 / AI 地点摘要”从“本轮开发 / 待开发”改为“已实现”，并在“已核实状态”栏注明实现时间为 2026-08-06、待升级项见后续设想。
- `TODO.md` 当前任务勾选项更新：
  - 勾上 Alembic 迁移应用、全量 pytest 分批通过、Web 完整 E2E、小程序微信开发者工具编译与走查。
  - 第 22-28 行的补充验收区同步改为完成，或明确剩余限制（如两周试点不在本轮）。
- `CHANGELOG.md` 新增版本条目：记录 Alembic 修复、新增测试、E2E 完成、文档口径统一。
- 原任务报告：在第 3 节逐项标明本次已完成项；在第 7 节补充真实执行的测试与 E2E 数据。
- 新增本次中文任务报告：按模板在 `AIwork/` 目录输出。
- Git 提交：本次设计文档、实施计划、代码/测试/文档变更、更新后的任务报告与 TODO/CHANGELOG 最后统一用 `git-commit` 技能生成 Conventional Commits。

## 5. 验收清单（Spec Self-Review）
- 所有重复 revision 是否变成唯一？`alembic heads` 是否 1 行？
- 空库 `upgrade head` 是否成功？种子数据是否成功？
- 新增 6 类集成测试是否通过？
- 分批次的全量 pytest 是否全部通过？
- 浏览器自动化是否跑通 7 步 Web E2E？
- 小程序门禁+编译+地点详情是否通过？
- 方案文档、TODO、CHANGELOG、原任务报告、新任务报告是否全部更新？
- 是否有任何环节未通过却写成完成？（禁止）
