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
- 启动：后端 `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`（需 `$env:APP_ENV = "opengauss"`；--host 0.0.0.0 用于微信小程序真机调试同局域网访问）；前端 `npm run dev`；小程序走微信开发者工具 + 确认「详情 → 本地设置 → 不校验合法域名」勾选。
- 微信小程序开发环境局域网地址：当前电脑 Wi-Fi 段 `192.168.3.x` 时 `DEV_LAN_HOST=192.168.3.10` 已在 [miniprogram/config/env.ts](miniprogram/config/env.ts) 配置；若换 Wi-Fi/网段，更新该常量并重编译小程序即可。配套需放行 Windows 防火墙 8000/TCP 入站（见下 PowerShell 命令）：
  ```powershell
  # 管理员 PowerShell 执行一次即可（持久生效，已存在则安全忽略）：
  New-NetFirewallRule -DisplayName 'MomentCampus Backend :8000' -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private,Domain | Out-Null
  ```
- 演示账号（与 [seed_data.py](backend/scripts/seed_data.py) 对齐）：
  - **平台级超管（跨三校可见，角色 `super_admin`）**：手机号 `13900000001 / pass123`
  - **江南大学（主演示校，code=`jiangnan`）**：校管理员手机号 `13900000000 / pass123`（角色 `admin`，昵称「江南大学运营组」）；普通用户手机号 `13900000002 ~ 13900000011 / pass123`，其中 `13900000002/04/05/07/08/10/11` 已完成校园认证。
  - **复旦大学（多租户演示校 A，code=`fudan`）**：校管理员手机号 `13900000101 / pass123`（角色 `admin`）；普通用户手机号 `13900000102 ~ 13900000106 / pass123`，其中 `13900000102/03/05` 已完成校园认证。
  - **浙江大学（多租户演示校 B，code=`zju`）**：校管理员手机号 `13900000201 / pass123`（角色 `admin`）；普通用户手机号 `13900000202 ~ 13900000206 / pass123`，其中 `13900000202/04/05` 已完成校园认证。
  - **微信手机号登录演示账号**：`13800138000`，江南大学，未认证，默认无密码；Mock 微信身份为 `MOCK_OPENID_STATIC_20260808_LOCAL_DEV`，登录后可在个人中心设置密码。
  - 所有普通用户密码统一为 `pass123`；教育邮箱仅用于校园认证，不参与登录；历史 `users.email` 字段在 seed 后全部为空。

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
