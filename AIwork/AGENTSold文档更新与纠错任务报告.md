# 任务报告：AGENTSold.md 文档更新与纠错

## 1. 任务概述

用户要求快速阅读整个项目后，更新根目录下的 `AGENTSold.md` 文件，并纠正文档中的所有错误。原 `AGENTSold.md` 内容过于简略（仅 33 行），且未反映项目从 SQLite 迁移到 openGauss、6 态状态机、5 类协同验证、RBAC 权限矩阵、混合部署等当前事实，需要依据仓库实际代码与配置重写。

## 2. 已完成内容

- 完整阅读项目根目录、`backend/`、`frontend/`、`docs/`、`deploy/`、`scripts/`、`AIwork/`、`.trae/` 结构
- 阅读关键文件：`README.md`、`TODO.md`、`backend/app/main.py`、`backend/app/config.py`、`backend/requirements.txt`、`backend/pyproject.toml`、`frontend/package.json`、`docker-compose.yml`、`backend/.env.opengauss.example`、`backend/app/api/router.py`、`CHANGELOG.md`、`DEVELOPMENT_TASKS.md`、`docs/00_project_overview.md`、`docs/18_项目现状说明.md`、`docs/21_后续开发任务清单.md`、`docs/22_项目运行与开发环境说明.md`、`.trae/rules/AIWORK_RULES.md`、`.gitignore`
- 重写 `AGENTSold.md`，分为 8 个章节：
  1. 项目基本信息
  2. 技术栈
  3. 目录结构
  4. 数据库与连接
  5. 常用命令
  6. 工作原则
  7. 完成标准
  8. 关键文档索引

## 3. 未完成内容

暂无。

## 4. 实现思路

通过实际读取仓库代码与配置文件（而非依赖可能过时的文档描述）确认当前事实，再以原 `AGENTSold.md` 的简洁风格为基础扩展。重点纠正与补充：

| 原 AGENTSold.md 问题 | 处理方式 |
| -------------------- | -------- |
| 未说明技术栈 | 新增"技术栈"表，列出前端 / 后端 / 数据库 / 认证 / 部署 |
| 未说明数据库实际为 openGauss | 明确"openGauss 7.0.0-RC3 轻量版，唯一数据库，已彻底移除 SQLite" |
| 未给出连接串与演示账号 | 补充连接串（含 `%40` 转义）、host/port/db/user、演示账号、演示学校 |
| 未给出目录结构 | 新增目录树，标注每个目录用途 |
| 未给出常用命令 | 新增后端 / 前端 / 测试常用命令 |
| 未提及 `AIwork/` 任务报告规则 | 在"完成标准"中新增第 4 条，引用 `.trae/rules/AIWORK_RULES.md` |
| 未提及 6 态状态机 / 5 类协同验证 / RBAC | 在"工作原则"中新增 3 条强约束 |
| 未提及江南大学唯一演示学校 | 在"工作原则"中明确禁止恢复 Base 项目学校数据 |
| "数据库删除约定"未覆盖容器场景 | 补充 openGauss 容器数据卷的删除命令 |
| 未提供关键文档索引 | 新增"关键文档索引"表，列出 13 份核心文档 |
| 完成标准未明确测试命令 | 补充 `pytest tests/ -v` 与 `npm run build` |

## 5. 修改文件

- `AGENTSold.md`（重写，由 33 行扩展至 165 行）
- `AIwork/AGENTSold文档更新与纠错任务报告.md`（新增，本报告）

## 6. 影响范围

- 仅影响项目根目录的 AI 协作规范文档 `AGENTSold.md`，不涉及任何业务代码、配置、数据库迁移或前端资源
- 后续 AI 协作时会以更新后的 `AGENTSold.md` 为准，减少误用 SQLite / 旧学校数据 / 缺失任务报告的概率
- 不影响运行时行为，无回归风险

## 7. 测试与验证

未执行自动化测试，原因：本任务为纯文档更新，不涉及代码或配置变更，无对应测试用例。

已执行的人工验证：

- 通读重写后的 `AGENTSold.md`，核对每条事实与仓库实际一致：
  - 技术栈版本号与 `frontend/package.json`、`backend/requirements.txt` 一致
  - 数据库连接串与 `backend/app/config.py`、`backend/.env.opengauss.example` 一致
  - API 模块数量（11 个）与 `backend/app/api/router.py` 注册的路由数量一致
  - 目录结构对照 `LS` 输出核对
  - 演示账号与 `README.md`、`docs/22_项目运行与开发环境说明.md` 一致
  - 演示学校（江南大学，code=`jiangnan`，map_zoom=16）与 `README.md`、`TODO.md`（J5 已确认）一致
- 确认所有文档链接指向的文件在 `docs/` 目录下实际存在

## 8. 后续建议

- 项目根目录同时存在 `AGENTSold.md`（旧版，本次已更新）与 `.trae/rules/AIWORK_RULES.md`（任务报告规则），建议后续确认是否需要将 `AGENTSold.md` 重命名为 `AGENTS.md` 或与 `.trae/rules/` 下的规则合并，避免两份规范并存造成歧义
- `DEVELOPMENT_TASKS.md` 仍停留在 2026-06-18 的阶段一状态，阶段二至九全部为 `[ ]`，与 `TODO.md` 记录的实际进度（阶段 A/B/E 已完成）严重不符，建议后续同步更新或归档
- `docs/22_项目运行与开发环境说明.md` 仍大量引用 `d:/Project/database-class/moment-campus/` 旧路径与 SQLite 内容，与当前 `e:\Project\moment-campus\` 实际路径和 openGauss 唯一数据库事实不符，建议后续统一修订
- `CHANGELOG.md` 最新版本仅到 `[0.1.1] - 2026-07-04`，7 月 5 日之后的混合部署、性能优化、UI 重构、状态机升级等变更未记录，建议后续补齐
