# 任务报告：复赛冲刺 Web 与后端系统性完善

## 1. 任务概述

依据 `AIwork/复赛冲刺实施计划_基于用户决策.md` 和已批准的四阶段实施计划，对 Web、后端、openGauss 数据层、自动任务、测试及现行文档进行系统性完善。本轮覆盖 T1–T8，但不修改小程序；实现过程不提交 Git，不更新要求与提交绑定的 `TODO.md`。

## 2. 已完成内容

- 协同验证彻底收敛为 `confirmation/refutation` 两类，统一使用 `POST /api/v1/posts/{post_id}/validate`，支持首次投票、异类切换、同类取消和作者禁投。
- 删除重复治理路由、Schema、前端服务和过期测试，帖子详情继续返回两类聚合统计。
- 自动过期任务改为 advisory lock fail-closed，增加 60 分钟脏运行租约，平台级操作收紧为 `super_admin`，新增独立 systemd service/timer 和部署脚本集成。
- 新增 Web 统一 `LoadingState`、`EmptyState`、`ErrorState`，覆盖首页、搜索、详情与评论、通知、专题、地图、发布元数据和首用引导。
- 分类由当前学校 API 动态加载；首页、搜索和地图删除名称或固定 ID 颜色映射，统一按 `category.code` 稳定计算水墨视觉；切校立即清理旧分类、筛选和 marker。
- 新增独立 OpenAI 兼容 Embedding 配置与服务、openGauss `vector(384)` 类型、HNSW 索引、可逆 Alembic 迁移、帖子生成与更新、历史回填脚本。
- AI 搜索实现语义 35%、新鲜度 25%、验证数 20%、关键词 20% 的租户安全混合排序，向量服务或 DataVec 查询失败时自动降级关键词检索。
- 清理正式 pytest 中 debug/diag 文件、永久下线能力 skip 测试和旧高级数据库对象测试；补齐 warning、timer、Embedding 与回填脚本回归后，当前正式后端测试集合为 971 项。
- 删除前端已下线“官方发布主体”永久 skip E2E，当前活跃 Playwright 用例全部执行。
- README、作品帖和关键 docs 已统一为两类验证、动态分类、独立 timer、DataVec 混合检索与安全测试库口径。
- axe 的 critical/serious 违规已升级为测试硬门禁，五条关键流程的颜色对比度问题已修复，学校切换器触控目标已提升并强制校验为至少 44×44px。
- 前端原有 22 条 ESLint warning 已全部清理，未关闭规则或降低规则等级。
- 后端 1799 条 warning 已按根因清零：修复 Pydantic 赋值类型、UTC 时间、FastAPI lifespan、SettingsConfigDict、测试 asyncio 标记和 Pillow 文件句柄，新增 5 条回归测试。
- 自动过期 timer 已统一为启动后 5 分钟首次执行、此后每 30 分钟执行，并增加 systemd unit 静态契约测试。
- 新增管理员真实分类创建、修改、禁用到普通用户发布、搜索、地图实时同步的 Playwright E2E，并在结束后回收唯一测试分类。
- Embedding 响应新增 NaN/Infinity 拒绝；历史回填脚本新增学校、数量、dry-run、短事务和逐原因统计控制。
- 删除错误包装旧三类治理语义的重复管理员页面、伪 API 类型和菜单；旧 `/admin/governance` 地址兼容重定向到正式举报管理。
- 删除 Analytics 与平台概览中的旧问题报告指标，保留正式举报 SLA；清理现行 openGauss 运维 SQL、数据核验与报告生成器中的收藏和旧三类验证依赖。

## 3. 未完成内容

- 未完成真实 Embedding API 同义查询联调。当前运行配置经脱敏检查为 `EMBEDDING_PROVIDER=disabled`、独立 key 未配置、独立 base 未配置、维度 384；聊天 AI 虽已配置，但设计明确禁止复用聊天密钥。历史回填实跑结果为 `scanned=90, updated=0, failed=90, skipped=0`，没有写入伪造向量。按提高后的验收门槛，T7 不能标记为最终完成。
- 未在真实 Linux 目标机启动并观察 `moment-expire-posts.timer` 至少一次调度。当前 WSL Ubuntu 22.04 的 systemd 为 running，unit 静态解析已到达 ExecStart 检查，但目标部署路径 `/opt/moment-campus/backend/.venv/bin/python` 不存在；因此不能把本机静态验证冒充目标机真实触发。
- 未更新 `TODO.md`，因为项目规则要求每次更新 TODO 必须提交 Git，而本轮没有获得明确提交授权。
- 未执行 Git 提交。

## 4. 实现思路

采用风险优先、可降级和测试先行的四阶段方案。第一阶段先统一验证契约和自动任务可靠性，避免旧五类语义继续扩散；第二阶段建立共享状态组件和动态分类视觉，确保请求失败不再伪装为空数据；第三阶段通过 nullable `vector(384)` 和独立短事务接入 Embedding，使外部服务失败不阻断发帖，并在当前租户候选集中完成混合排序；第四阶段清理失效测试、同步现行文档并执行全量门禁。外部依赖未满足时保留功能降级，但不把降级结果写成真实语义检索验收通过。

## 5. 修改文件

- 后端验证与路由：`backend/app/core/validation_type.py`、`backend/app/schemas/enums.py`、`backend/app/schemas/interaction.py`、`backend/app/schemas/post.py`、`backend/app/api/interactions.py`、`backend/app/api/posts.py`、`backend/app/api/router.py`。
- 删除重复治理实现：`backend/app/api/governance.py`、`backend/app/schemas/governance.py`、`frontend/src/services/governance.ts`、`backend/tests/test_governance.py`。
- 自动过期与部署：`backend/app/jobs/expire_posts.py`、`backend/app/api/admin.py`、`backend/scripts/expire_posts_worker.py`、`deploy/bare-metal/moment-expire-posts.service`、`deploy/bare-metal/moment-expire-posts.timer` 及部署脚本。
- 向量检索：`backend/app/config.py`、`backend/app/db_types.py`、`backend/app/db_compat.py`、`backend/app/models/post.py`、`backend/app/services/embedding_service.py`、`backend/app/services/ai_search.py`、`backend/scripts/generate_embeddings.py`、`backend/alembic/versions/a1b2c3d4e5f6_t7_post_embeddings.py`。
- Web 状态与分类：`frontend/src/components/state/`、`frontend/src/utils/categoryVisual.ts`、首页、搜索、地图、详情、通知、专题、发布表单和首用引导页面，以及地图/互动服务。
- Web 质量：`frontend/e2e/accessibility.spec.ts`、`tailwind.config.js`、`src/index.css`、`src/styles/tokens.ts`、`SchoolSwitcher.tsx`、`Badge.tsx`、`GlobalToast.tsx` 及 lint 报警涉及的 React 页面和组件。
- 测试：后端验证、过期、搜索、租户、Embedding、DataVec、发布流程测试；前端 `accessibility.spec.ts`、`state-components.spec.ts`、`validation-and-categories.spec.ts` 和清理后的 `business.spec.ts`。
- 文档：`README.md`、`Demo作品帖_此刻校园.md`、`docs/00_project_overview.md`、`08_community_governance.md`、`11_technical_architecture.md`、`13_api_specification.md`、`15_testing_and_acceptance.md`、`22_项目运行与开发环境说明.md`、`31_项目演示流程指南.md`、`32_TRAE_AI创造力大赛复赛优化方案.md`、`33_TRAE_AI创造力大赛复赛深度优化落地方案_2026.md`。

## 6. 影响范围

后端公开验证契约、帖子详情聚合、自动过期并发与权限、地图响应、帖子向量写入、AI 搜索排序和 openGauss 迁移发生变化。Web 的异步状态呈现、分类视觉、学校切换清理、验证交互和相关 E2E 得到统一。当前小程序代码未由本任务修改，但工作区中存在本任务开始前的小程序改动，实施过程中未回退或覆盖。旧复数治理端点和旧五类写入不再兼容，客户端必须使用单数验证端点和两类正式值。

## 7. 测试与验证

- 后端全量：显式使用独立 `moment_campus_test` 数据库和 `backend/.venv` 执行 `python -m pytest tests -q -W error`，结果 `987 passed, 0 failed, 0 warnings`，耗时 14 分 24 秒。
- openGauss 运维 SQL：专项契约扩展后 16 passed；03/04/06/07/08 脚本在独立测试库同一事务中依次执行成功并完整回滚；SQL 契约、topics、subscriptions 复现集 55 passed。
- 后端定向：验证契约 `117 passed, 1 skipped`；自动过期 `16 passed`；T7 向量链路 `14 passed`；过期契约清理相关测试 `364 passed`。
- 迁移往返：在隔离测试库执行 `stamp head -> downgrade -1 -> upgrade head` 成功，最终 revision 为 `a1b2c3d4e5f6 (head)`；`vector(384)` 列和 HNSW 索引存在。
- Web lint：清理 22 条既有 warning 后重新执行 `npm run lint`，结果 `0 errors, 0 warnings`。
- Web build：`npm run build` 通过，TypeScript 与 Vite 构建成功；保留 MapLibre 大 chunk 警告。
- axe TDD：硬门禁启用后首次运行五条关键流程为 `5 failed`，准确拦截颜色对比度和 40px 触控目标；修复后专项结果为 `5 passed, 0 failed`。
- Web 全量 E2E：删除重复治理页并补入旧 URL 重定向回归后执行 `npm run e2e`，结果 `38 passed, 0 failed, 0 skipped`，覆盖登录、注册、审核、订阅、地图、三校切换、跨租户拒绝、AI 入口、统一状态、动态分类错误恢复、管理员分类实时同步、治理入口兼容和无障碍硬门禁。
- 浏览器最小验收：本地前后端启动成功，管理员后台可加载，仪表盘、审核、举报、分类、任务记录和平台管理入口可访问；自动化全链路以 Playwright 38 项结果为准。
- 静态检查：VS Code 工作区诊断为 0；`git diff --check` 通过，仅有 Windows LF/CRLF 提示。
- 安全性：真实 Embedding key 未读取到输出、未写入文档或 Git diff；未使用开发库执行会重建 schema 的测试。
- 外部条件审计：只输出 Embedding 配置是否存在、host 和模型等脱敏元数据；确认独立 Embedding 未配置。WSL systemd 可用，但生产部署路径不存在，保留真实阻断证据而不伪造验收结果。

## 8. 后续建议

1. 在安全环境注入独立 `EMBEDDING_*` 配置，先以非敏感示例验证 384 维响应和“哪里能打印/打印店在哪”同义召回，再重新运行历史回填并确认 `embedding IS NULL` 数量归零。
2. 在目标 Linux 服务器安装并启动 timer，检查 `systemctl list-timers` 和 `journalctl -u moment-expire-posts`，保留至少一次真实过期调度成功证据。
3. 在 CI 中保持后端 `-W error` 与前端 axe critical/serious 硬门禁，防止质量指标回退。
4. 单独评估 MapLibre 产物体积和按需加载策略，消除大于 600kB 的构建提示，但不要通过单纯调高告警阈值掩盖体积问题。
5. 用户明确授权提交后，再按项目规则更新 `TODO.md` 并按阶段创建简体中文 Conventional Commits。
