# 此刻校园 - TODO 列表

> 依据 [AGENTS.md](AGENTS.md) 要求维护，每完成一个小点即更新本文件。
> 任务详细规划见 [docs/21_后续开发任务清单.md](docs/21_后续开发任务清单.md)。

## 当前阶段

**阶段 R：TRAE AI 创造力大赛复赛冲刺（P0）** — 进行中（目标：2026-08-09 23:59 前完成正式提交）

**阶段 A：openGauss 适配（P0）** — 已完成（T-A-01 ~ T-A-18 全部完成）

**阶段 P：数据库物理模型实现（P1）** — 主体完成（P-P-01 ~ P-P-06、P-P-08、P-P-09 完成；P-P-07 放弃：openGauss 轻量版容器无 cron 服务；P-P-08 性能测试已完成，8 查询全部达标；P-P-10 放弃：轻量版不支持 pg_trgm/zhparser）

**阶段 B：核心业务升级（P0）** — 主体完成（T-B-01/02/04/05/06 已完成；T-B-03 放弃：Service 层抽取不做；T-B-07/08 视情况补做）

**阶段 C / D：已放弃** — 按用户决策（2026-07-02），整个阶段 C（创新点）与阶段 D（扩展能力）全部放弃，按最小 MVP 交付。SQLite 已彻底移除，全面转移至 openGauss。

## 已完成

### TRAE AI 创造力大赛复赛方案（2026-07-24 完成）

- [x] 阅读官方复赛参赛指南与本地复赛详细说明
- [x] 对照评分标准盘点当前产品、技术、AI、测试、部署与材料差距
- [x] 编写 [docs/32_TRAE_AI创造力大赛复赛优化方案.md](docs/32_TRAE_AI创造力大赛复赛优化方案.md)
- [x] 明确复赛核心主线：校园信息智能发现 + AI 辅助发布 + 可验证降级链路
- [x] 任务报告：[AIwork/TRAE_AI创造力大赛复赛方案制定任务报告.md](AIwork/TRAE_AI创造力大赛复赛方案制定任务报告.md)

### 生产访问性能优化（2026-07-06 完成）

- [x] 确认生产 Nginx 缺少首页与静态资源缓存头，页面 chunk 每次需要普通请求/协商
- [x] 前端路由增加常用页面 chunk 空闲预取，地图页延后预取以降低首屏压力
- [x] 混合部署 Nginx 配置补充 gzip、`/assets/*` 长缓存与 `index.html` no-cache
- [x] 传统物理部署 HTTPS 模板同步静态资源缓存策略
- [x] 更新华为云混合部署记录，补充性能优化与上线验证项

### 管理后台与发布链路修复（2026-07-05 完成）

- [x] 隐藏管理后台“标签管理”入口：侧边栏与仪表盘快捷操作均不再展示
- [x] `/admin/tags` 旧地址改为回到管理后台首页，避免继续暴露已弃用页面
- [x] 移除信誉分主应用链路：发帖、评论不再调用 `sp_update_reputation`
- [x] 移除个人中心“校园贡献值”展示与前端类型依赖
- [x] 修复发帖/地图发帖已入审核库但前端误报失败：发帖成功后不再被信誉分附加逻辑影响
- [x] 补齐通知链路：审核通过/拒绝、评论/回复均写入通知中心
- [x] 修复批量审核状态值：通过写入 `published`，拒绝写入 `archived`

### 演示流程规划（2026-07-05 完成）

- [x] 编写 [docs/31_项目演示流程指南.md](docs/31_项目演示流程指南.md)
- [x] 4阶段7场景完整演示脚本（10-15分钟，功能为主）
- [x] 演示准备清单 + 常见问题Q&A + 应急方案
- [x] 任务报告：[AIwork/项目演示流程规划任务报告.md](AIwork/项目演示流程规划任务报告.md)

### 服务器混合部署（2026-07-05 完成）

- [x] 确认华为云服务器环境：Ubuntu 22.04.5 LTS / ARM64 / Docker 29.1.3
- [x] 安装 Docker Compose v2，并导入 ARM64 openGauss 镜像 `opengauss:7.0.0-RC3`
- [x] 克隆项目到服务器 `/opt/moment-campus`
- [x] 切换为混合部署方案：openGauss 容器 + 后端 systemd 物理部署 + 前端 Nginx 静态部署
- [x] openGauss 容器仅绑定 `127.0.0.1:5432`，避免数据库公网暴露
- [x] 服务器安装 Python/Nginx 运行依赖，后端使用 `backend/.venv`
- [x] 上传本地构建通过的前端 `dist/` 到服务器
- [x] 修复生产迁移链路缺失字段：`users.reputation_score`、`posts.credibility_score`
- [x] 修复生产迁移链路旧字段残留：删除 `favorites` 表、`posts.favorite_count`、`posts.is_top`
- [x] 修复生产迁移链路缺失字段：`validation_records.is_deleted`、`validation_records.deleted_at`
- [x] 服务器完成 Alembic 迁移与江南大学演示数据初始化
- [x] 服务器内部验证通过：`moment-backend`、`nginx` active，`/health`、首页、`/api/v1/posts` 本机链路正常
- [x] 公网 HTTP 验证通过：`http://123.60.101.165/` 可访问前端，`/api/v1/posts` 返回数据
- [x] 公网 HTTPS 验证通过：`https://campus.chaina1.com/health`、首页、`/api/v1/posts` 正常
- [x] 申请并部署 Let's Encrypt 证书，证书有效期至 2026-10-03，certbot 自动续期已启用
- [x] 管理员登录接口验证通过：`admin@momentcampus.com / pass123`

### 超大规模检查与Bug修复（2026-07-04 完成）

- [x] 修复评论创建500错误（MissingGreenlet：Comment.replies 关系未预加载）
- [x] 修复非匿名帖子/评论全部显示"匿名用户"（author 字段 alias="user" 导致API返回user而非author）
- [x] PostListResponse/CommentResponse 移除 alias="user"，所有返回点手动映射 author 字段
- [x] PostListResponse 补充 user_id、is_anonymous 字段
- [x] 修复 user.py 中 LoginResponse 重复定义
- [x] 删除数据库中 is_top 字段及置顶逻辑
- [x] 修复时区问题（Asia/Shanghai）
- [x] 完善校园贡献值（reputation_score）在登录/个人中心返回
- [x] 清理测试垃圾数据（123123帖子及评论）
- [x] API验证全部通过（帖子列表/详情/评论/回复 author字段正确）
- [x] 前端UI验证通过（首页正确显示作者昵称）

### 前端UI重新设计（水墨风优化）（2026-07-05 完成）

- [x] 更新设计令牌 tokens.ts：规范色彩、字体、圆角（减少过度圆角）、阴影
- [x] 更新 tailwind.config.js：扩展水墨风主题配置
- [x] 更新 index.css 全局样式：增强宣纸纹理、优化墨线分割
- [x] 重构 UI 基础组件（Button/Card/Badge/Input/Avatar/Modal/Toast/Table）
- [x] 重构 PostDetailPage 详情页为长卷式布局，减少卡片碎片化
- [x] 重构 HomePage 首页信息流，统一卡片样式与间距
- [x] 调整 Header/MainLayout/Sidebar 布局组件
- [x] 更新 Login/Register/Publish 表单页，统一表单样式
- [x] 更新 Profile/Search/Notifications 列表页，标准化列表布局
- [x] 更新 MapPage 地图页与侧边面板
- [x] 统一 Admin 后台样式与设计系统
- [x] npm run build 构建验证通过

### 管理员后台重构收尾（2026-07-04 完成）

- [x] WS9 AdminTagsPage 新建：列表+搜索+筛选+编辑+官方切换+软删除+合并面板
- [x] WS10a AdminLogsPage 新建：5 维筛选（admin_id/action/target_type/date_from/date_to）+ JSON 详情解析
- [x] WS10b AdminSettingsPage 修复：localStorage 持久化 + "前端本地配置"标注 + 恢复默认
- [x] 路由更新：routes.tsx 追加 categories/tags/logs 三个子路由
- [x] V1-V6 后端验证全部通过（stats/logs/categories CRUD/tags CRUD+merge/批量操作）
- [x] V7 前端构建验证通过（npm run build exit 0）
- [x] 登录页自动跳转：检测到 admin/super_admin 角色登录后直接跳 `/admin`，普通用户跳 `/`

### 文档梳理阶段（2026-06-29 完成）

- [x] 完整阅读项目（根目录 / 后端 / 前端 / docs）
- [x] 编写 [docs/18_项目现状说明.md](docs/18_项目现状说明.md)
- [x] 编写 [docs/19_Base项目与目标项目差异说明.md](docs/19_Base项目与目标项目差异说明.md)
- [x] 编写 [docs/20_openGauss适配分析.md](docs/20_openGauss适配分析.md)
- [x] 编写 [docs/21_后续开发任务清单.md](docs/21_后续开发任务清单.md)
- [x] 编写 [docs/22_项目运行与开发环境说明.md](docs/22_项目运行与开发环境说明.md)
- [x] 编写 [docs/23_江南大学模拟核心决策说明.md](docs/23_江南大学模拟核心决策说明.md)（追加决策）
- [x] 任务报告：[AIwork/项目梳理与改造文档补充任务报告.md](AIwork/项目梳理与改造文档补充任务报告.md)

### 数据库课程设计前期工作（2026-06-29 完成）

- [x] 编写 [docs/24_需求分析与数据字典.md](docs/24_需求分析与数据字典.md)（任务指导书第 1 项）
  - 组织机构图 3 张、数据流图（顶层+0层+1层 4 张）、判定表 3 张、判定树 2 张、数据字典（22 数据项/6 结构/15 流/21 存储/8 处理）
- [x] 编写 [docs/25_数据库概念模型设计.md](docs/25_数据库概念模型设计.md)（任务指导书第 2 项，必须项）
  - 21 个实体、35 个联系、5 个 E-R 图、6 大功能模块、实体与功能矩阵
- [x] 编写 [docs/26_数据库逻辑模型设计.md](docs/26_数据库逻辑模型设计.md)（任务指导书第 3 项）
  - 21 张关系模式完整 SQL、15 个视图、完整性约束、3NF 规范化分析
- [x] 编写 [docs/27_数据库物理模型设计.md](docs/27_数据库物理模型设计.md)（任务指导书第 4 项）
  - 4 表空间、Astore/Ustore 双引擎、66 索引（含 8 新增部分索引）、8 存储过程、8 触发器、4 物化视图、7 分区表、7 定时任务、性能估算
- [x] 生成数据库设计产物（[docs/design/](docs/design/)）
  - Excel 表结构文档（21 张表，每表一个 Sheet + 总览 Sheet，PK/FK 高亮）
  - ER 图 SVG（总体 + 5 个子系统：用户/信息/互动/治理/管理）
  - ER 图 DOT 源码（供 Graphviz 渲染）
  - 生成脚本：[backend/scripts/generate_db_design.py](backend/scripts/generate_db_design.py)

### 历史已完成（Base 项目）

- [x] 后端 API 全部 11 个模块实现
- [x] 前端核心页面实现（首页、详情页、发布页、地图页、搜索页、用户中心、管理后台等）
- [x] 数据库 21 个模型建立
- [x] 演示数据填充脚本（seed_data.py）
- [x] 前后端联调通过

## 待办（按优先级）

### P0 — 阶段 R：TRAE AI 创造力大赛复赛冲刺

- [ ] **R-01** 统一代码、全部对外文档、演示可见页面和作品帖的功能事实口径
- [ ] **R-02** 修复过期后端测试并恢复可运行的当前质量基线
- [ ] **R-03** 实现 AI Gateway、结构化输出校验、超时与基础模式降级
- [ ] **R-04** 实现具有统一结果契约的自然语言校园信息智能搜索，并联动信息流与地图
- [ ] **R-05** 修复发布字段端到端一致性后，实现 AI 辅助发布的分类、标签、地点与有效期建议
- [ ] **R-06** 增加 AI 调用可验证证据、健康检查与脱敏日志
- [ ] **R-07** 优化搜索 N+1 查询并执行复赛规模性能验证
- [ ] **R-08** 建立发布审核闭环、智能搜索和 AI 降级核心 E2E
- [ ] **R-09** 完成移动端、异常态、加载态和线上稳定性检查
- [ ] **R-10** 完成复赛版产品说明书、真实产品截图和 TRAE 过程截图
- [ ] **R-11** 录制并校验 1–5 分钟完整产品演示视频
- [ ] **R-12** 为复赛新增核心能力整理不少于 3 个关键 Session ID 及对应成果证据
- [ ] **R-13** 发布社区复赛作品说明帖，不公开体验入口和测试账号
- [ ] **R-14** 完成全量提交演练后，提交飞书问卷私密材料并保存最终提交凭证

### P0 — 阶段 A：openGauss 适配

- [x] **T-A-01** openGauss 镜像准备（确认本地已导入 `opengauss:7.0.0-RC3`）
- [x] **T-A-02** 启动 openGauss 容器并验证端口
- [x] **T-A-03** 编写最小连接测试脚本验证 asyncpg 兼容性
- [x] **T-A-04** 修复 21 个模型主键类型（Integer → BigInteger）
- [x] **T-A-05** 更新后端依赖（新增 asyncpg）
- [x] **T-A-06** 新建 openGauss 环境配置文件（.env.opengauss）
- [x] **T-A-07** 修改后端配置加载逻辑支持环境切换
- [x] **T-A-08** 重写 Alembic 初始迁移
- [x] **T-A-09** 修改 seed_data.py 初始化逻辑
- [x] **T-A-10** 执行演示数据填充到 openGauss
- [x] **T-A-11** 启动后端验证 openGauss 连接
- [x] **T-A-12** API 链路验证（openGauss 环境）
- [x] **T-A-13** 前后端联调验证（openGauss 环境）
- [x] **T-A-14** openGauss 兼容性回归测试
- [x] **T-A-15** 阶段 A 文档与提交（含 README 修正）
- [x] **T-A-16** 重写 seed_data.py 学校与地点数据为江南大学（详见 [docs/23_江南大学模拟核心决策说明.md](docs/23_江南大学模拟核心决策说明.md)）
- [x] **T-A-17** 调整前端地图默认中心点为江南大学
- [x] **T-A-18** 同步更新文档与截图

### P1 — 数据库物理模型实现（依据 [docs/27_数据库物理模型设计.md](docs/27_数据库物理模型设计.md)）

- [x] **P-P-01** 表空间创建脚本（01_create_tablespaces.sql，4 个表空间）
- [x] **P-P-02** 索引迁移脚本（04_create_indexes.sql，汇总现有 50 + 新增 8 个部分索引）
- [x] **P-P-03** 存储过程实现（07_create_functions.sql，SP01-SP08 共 8 个 PL/pgSQL）
- [x] **P-P-04** 触发器实现（08_create_triggers.sql，TR01-TR08 共 8 个）
- [x] **P-P-05** 物化视图实现（06_create_materialized_views.sql，MV01-MV04）
- [x] **P-P-06** 分区表迁移（09_create_partitions.sql，7 张大表 RANGE 分区）
- [~] **P-P-07** 定时任务配置（cron 文件，7 个 JOB）— **放弃**：openGauss 轻量版容器无 cron 服务，按 MVP 原则不实现
- [x] **P-P-08** 性能测试（EXPLAIN ANALYZE 关键查询，8 查询全部达标，详见 [AIwork/P-P-08_性能测试执行与数据记录报告.md](AIwork/P-P-08_性能测试执行与数据记录报告.md)）
- [x] **P-P-09** 归档表创建（admin_operation_logs_archive）
- [~] **P-P-10** zhparser 中文分词扩展安装（全文搜索增强）— **放弃**：轻量版不支持 pg_trgm/zhparser，按 MVP 原则不实现

### P0 — 阶段 B：核心业务升级

- [x] **T-B-01** Post 状态机字段扩展（6 态流转）
- [x] **T-B-02** 协同验证类型扩展（5 类）
- [~] **T-B-03** Service 层初步抽取（Post 业务）— **放弃**：按用户决策不做 Service 层抽取
- [x] **T-B-04** API 改造：状态机与协同验证接口
- [x] **T-B-05** 前端信息详情页改造
- [x] **T-B-06** 前端发布页改造
- [ ] **T-B-07** 阶段 B 联调验证
- [ ] **T-B-08** 阶段 B 文档与提交

### P1 — 阶段 C：创新点实现（**整阶段放弃**）

- [~] **T-C-01 ~ T-C-09** — **放弃**：按用户决策（2026-07-02），整个阶段 C 不做，按最小 MVP 交付

### P2 — 阶段 D：扩展能力（**整阶段放弃**）

- [~] **T-D-01 ~ T-D-04** — **放弃**：按用户决策（2026-07-02），整个阶段 D 不做

### P0 — 阶段 E：测试与交付

- [x] **T-E-01** 单元测试补全 — 详见 [AIwork/T-E-01_单元测试补全任务报告.md](AIwork/T-E-01_单元测试补全任务报告.md)
- [x] **T-E-02** 集成测试（openGauss SP/TR/MV/分区/索引/表空间，64 项通过）— 详见 [AIwork/T-E-02_集成测试任务报告.md](AIwork/T-E-02_集成测试任务报告.md)；**E2E 放弃**（按用户决策 2026-07-03，Playwright 未安装）
- [x] **T-E-03** 文档完善 — 详见 [AIwork/T-E-03_文档完善任务报告.md](AIwork/T-E-03_文档完善任务报告.md)
- [x] **T-E-04** 课程设计报告 — 详见 [docs/课程设计报告.md](docs/课程设计报告.md)（13 章节 + 附录，约 28000 字符）

### 横切关注点

- [x] **T-X-01** 权限与认证矩阵完善（贯穿阶段 B）— 详见 [AIwork/T-X-01_权限矩阵完善任务报告.md](AIwork/T-X-01_权限矩阵完善任务报告.md)
- [ ] **T-X-02** 文档持续维护（贯穿全程）
- [ ] **T-X-03** Git 提交规范（贯穿全程）

## 待确认事项

- [ ] **C7** 课设是否要求使用 openGauss 触发器/存储过程/视图（需与指导老师沟通；doc 27 已设计完整方案，待老师确认实现深度）
- [x] **C8** 是否保留 SQLite 作为开发备选 — 已确认**不保留**，彻底删除 SQLite，全面转移至 openGauss（2026-07-02 用户决策）
- [x] **C4** openGauss 镜像是否已本地导入 — 已确认（T-A-01 完成，本地已导入 `opengauss:7.0.0-RC3`）
- [x] **J1** 江南大学地点的真实坐标（15 个地点）— 已确认（使用校区中心±0.005偏移，T-A-16 已填入）
- [ ] **J2** 是否保留"复旦大学"等其他学校作为对比（推测不保留）
- [x] **J3** 学校 code 字段使用 `jiangnan` 还是 `jnu`— 已确认 `jiangnan`
- [x] **J4** 江南大学是否需建模多个校区 — 已确认只建蠡湖校区
- [x] **J5** map_zoom 是否仍为 15 — 已确认使用 16（T-A-17 实施）

## 备注

- 任务详细规划、涉及文件、验收标准、风险提示见 [docs/21_后续开发任务清单.md](docs/21_后续开发任务清单.md)
- 每完成一项任务后，将对应 `[ ]` 改为 `[x]`，并在 [AIwork/](AIwork/) 新增任务报告
- 严格遵循 [AGENTS.md](AGENTS.md) 与 [.trae/rules/AIWORK_RULES.md](.trae/rules/AIWORK_RULES.md)
