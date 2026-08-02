# AGENTS.md

- Python 项目必须使用 `backend/.venv` 虚拟环境。
- 项目根目录：`moment-campus/`
- 项目文档：`docs/`
- 根目录两个 HTML 文件为早期演示 Demo。
- 每完成一个小点就更新 `TODO.md`。
- 每次更新 `TODO.md` 都必须提交 Git 代码，提交信息说明完成了什么功能、修复了什么 Bug、更新了哪些文档或配置。
- 删除数据库时，把数据库文件移动到 `delete/` 文件夹统一处理；openGauss 容器用 `docker compose down -v opengauss`。
- 数据库唯一：openGauss 7.0.0-RC3 轻量版（已彻底移除 SQLite）。
- 演示学校：江南大学为主（code=`jiangnan`，map\_zoom=16），附带 fudan/zju 两所学校用于多租户演示（共 3 校，详见 docs/project-audit/此刻校园项目全量排查报告.md §6.2）。
- Post 状态机：6 态（draft/pending/published/expired/conflict/archived）；协同验证：2 类（confirmation/refutation，互斥且可切换或取消）。
- 权限：user < admin < super\_admin，统一通过 `app/core/permissions.py` 的 `require_role()` 校验。
- 启动：后端 `uvicorn app.main:app --reload`（需 `$env:APP_ENV = "opengauss"`）；前端 `npm run dev`。
- 演示账号：管理员 `admin@momentcampus.com / pass123`；普通用户 `user1@example.com ~ user10@example.com / pass123`。

## 工作原则

1. 开始任务前，先阅读 `docs/` 中与任务相关的文档。
2. 遇到问题时，优先查找并使用相关 Skill；无可用 Skill 时再查阅项目文档。
3. 修改代码前先理解现有实现，避免重复开发或擅自改变既定设计。
4. 每次只完成当前任务涉及的内容，不进行无关重构。
5. 每次完成一个任务之后，都需要使用 `git-commit`技能进行git提交

## 完成标准

任务完成后必须：

1. 检查代码，修复已发现的问题。
2. 运行相关测试（后端 `pytest tests/ -v`，前端 `npm run build`），确认主要功能和完整链路正常。
3. 使用 MCP 工具 `integrated_code_mode`进行端到端自动化操作测试：前后端启动后，通过 `run_mcp` 调用浏览器工具模拟真实用户操作，验证登录、发布 Post、协同验证、权限校验等关键链路的 UI 与交互正常。结果写入任务报告"测试与验证"一节。
4. 更新相关文档及 `TODO.md`。
5. 在 `AIwork/` 目录新增中文命名的任务报告（8 节模板见 `.trae/rules/AIWORK_RULES.md`）。

未经测试、链路未跑通或存在已知 Bug 时，不得将任务标记为完成。任务报告必须真实记录，不能把未完成内容写成已完成。
