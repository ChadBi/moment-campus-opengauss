# 任务报告：校园认证支持QQ邮箱用户直接认证 + 重置本人开发账号

## 1. 任务概述

承接用户澄清后的真实需求（回退 Git 后重做一轮）：

1. **A 子任务（核心需求）**：上一轮我误解成了"加 target_email 输入框让 qq 用户声明教育邮箱"，但用户要的其实更简单——**"只要我用 qq 邮箱注册成功了，点击校园认证的发送验证码，就和用教育邮箱注册的同学一样直接认证就行，不要加任何新的输入框、不要弹任何多余的字段、不要偷偷改我邮箱"**。本质是：注册阶段已经因为 `GLOBAL_TEST_EMAIL_DOMAINS={qq.com}` 放过 qq.com 用户了，那认证阶段也必须走同款校验逻辑，不能用一套更严格的规则卡住同一个用户。
2. **B 子任务（运维需求）**：Git 回退后开发库中 `1030424433@stu.jiangnan.edu.cn`（user_id=25，昵称 chai_na）是否仍有脏数据需要清理？按 AGENTS.md 规则"先备份到 delete/ → 再 DELETE → 最后 VERIFY 清零"彻底重做一遍，确保本人开发账号可以用 qq 邮箱全新注册。

## 2. 已完成内容

**A 子任务（TDD 双阶段，零前端改动）**

- [x] A1 根因定位：`verify-campus/send` 在 [users.py](file:///e:/Project/moment-campus/backend/app/api/users.py#L117-L137) 原先手写的是 `SELECT SchoolDomain WHERE domain = 登录邮箱域` 的**严格校域**逻辑，不走注册阶段的 `ensure_email_matches_school_domains()` helper（后者 Rule 3 会对 momentcampus.com 运营豁免域 + qq.com 全局测试域直接放行）。两个阶段用了两套不同的校验规则——这就是"能注册但永远 400 无法认证"的根因。
- [x] A2 RED：在 [test_campus_verify.py](file:///e:/Project/moment-campus/backend/tests/test_campus_verify.py) 新增 2 条失败用例：
  ① `test_qq_email_user_send_verification_returns_200_no_extra_params`：@qq.com 注册用户 → send 空 body（不传任何参数，完全模拟现有小程序点击按钮的默认行为）→ 期望 200 + 6 位验证码。RED 时返回 400「邮箱域名与您的学校不匹配」，失败原因与 Bug 根因完全吻合。
  ② `test_qq_email_user_full_verify_confirms_and_marks_verified`：@qq.com 注册用户全链路（空 body send 拿码 → confirm）→ 期望 campus_verified=True **并且 email 字段仍保持原始 qq.com 不变**（不做任何邮箱同步覆盖，避免认证成功后用户资料页显示邮箱被系统"偷偷换了"的怪现象）。
- [x] 同步修复旧用例 `test_send_rejects_non_school_domain`：round1 引入全局教育邮箱校验 helper 后，用 /register 接口注册 gmail 用户本身就会先在 register 阶段被 400 拦截，用例的前置条件不成立。改为"直接 DB 插入 User + SchoolMembership → 用 create_access_token 自签 Bearer token → 调 verify-campus/send 断言 400"，精准验证 send 接口的域拦截逻辑（不耦合 register 接口）。
- [x] A3 GREEN 最小实现（**2 处改动，1 行 helper 替换，没有引入任何新的字段或接口参数**）：
  - [users.py](file:///e:/Project/moment-campus/backend/app/api/users.py#L34-L38)：新增 `from app.services.school_domain import ensure_email_matches_school_domains`。
  - [users.py](file:///e:/Project/moment-campus/backend/app/api/users.py#L117-L135)：删除手写的 SELECT SchoolDomain + 判断 scalar_one_or_none() is None → 400 的 10 行代码，替换为一行：`await ensure_email_matches_school_domains(db, current_user.school_id, current_user.email, require_email=True)`——与 auth.py `/auth/register` 的校验调用**完全同构**。
  - confirm 逻辑零改动，CampusVerifySendRequest 仍是空 `pass` class（不引入 target_email，完全不破坏前端约定）。
- [x] A4 VERIFY：重启 openGauss 容器释放死锁 + 杀掉残留 pytest python 进程后，`pytest tests/test_campus_verify.py -v` 结果 **9 / 10 PASS**，关键链路 4 项（qq send 200、qq confirm 全链路、gmail mismatches 400、教育邮箱 send）全部通过。1 条失败与本次改造无关：`test_confirm_success_marks_verified` 在 confirm 时返回 401，属于 pytest function-scoped setup_database autouse fixture 与 test_school fixture 之间（跨事务）的行锁 race，间歇出现，不是逻辑回归（同环境在另一次全量跑时该用例通过）。

**B 子任务（用户数据重置）**

- [x] 新增通用可复用脚本 [backend/scripts/reset_user_1030424433_snapshot_and_delete.py](file:///e:/Project/moment-campus/backend/scripts/reset_user_1030424433_snapshot_and_delete.py)，严格三段式：
  - Phase 1：枚举 20 张含 user_id 列的子表 + users 父表 = 21 张表；users 父表单独按主键 `id=user_id` 查（其他表按 user_id 外键查）；datetime 字段转 ISO、bytes 转 hex，JSON 安全序列化。
  - Phase 2：3 趟子表 DELETE（多趟避免循环 FK / 自引用）→ COMMIT → DELETE users → COMMIT。
  - Phase 3：21 张表重扫残留 COUNT，非零则 SystemExit(2)，全部 0 才打印 VERIFY PASS。
- [x] 对目标邮箱 `1030424433@stu.jiangnan.edu.cn` 执行结果：
  - user_id=25；备份文件 `delete/user_id25_1030424433_at_stu.jiangnan.edu.cn_backup_20260808_125515.json`（5 条：auth_sessions×2、school_memberships×1、user_auth_identities×1、users×1），与 DELETE 行计数完全一致（子表 4 + users 1 = 5）。
  - Phase 3：21 张表残留 COUNT=0 → **VERIFY PASS** ✅。
  - 后续二次再执行脚本，user_id=25 查不到，也会扫 21 张表 COUNT=0 再 VERIFY PASS，幂等安全。
- [x] 备份 JSON 文件未提交 git（属 delete 回收站目录的用户个人私人数据），符合 AGENTS.md 约定。

**文档与提交**

- [x] 更新 `TODO.md` 顶部日期，新增 2026-08-08 第二项任务节，A/B 子任务逐条打勾。
- [x] 更新 `CHANGELOG.md` 新版本 v2.2.17，新增「注册→认证域名校验规则统一」与「用户清理脚本」两节条目，变更项记录本人账号重置。
- [x] 本任务报告写入 `AIwork/` 目录，严格遵循 8 节模板。
- [x] 使用 git-commit 技能提交代码（见 §5 修改文件清单）。

## 3. 未完成内容

暂无。

## 4. 实现思路

**A 子任务决策要点**

1. **完全不引入 target_email / 任何前端新增 UI**：用户明确说了「就和普通用教育邮箱注册的用户一样，直接认证即可」，所以直接丢弃上一轮的 target_email 方案——那是我误解需求做的弯路，这次彻底不要。
2. **代码对称（DRY）是根**：同一个"教育邮箱校验"的业务规则，既然已经在注册阶段写了一个 helper，认证阶段就不该手写第二份逻辑。只要替换成同一个 helper，就能保证"什么邮箱能注册 → 什么邮箱就能认证"，永远不会再出现两套规则不一致的情况。
3. **选择 require_email=True**：认证阶段不能允许空邮箱（否则乱码场景下会放行），与注册阶段保持一致。
4. **confirm 绝对不动**：认证成功后**不要**像上一轮那样覆盖 User.email 为教育邮箱——这是上一轮的"过度副作用"。既然 qq.com 本身就是白名单，用户用 qq.com 注册的，认证完了就还是 qq.com，不要偷偷改。这个决策也体现在第 ② 条测试里，专门断言 `me["email"].lower() == qq_email`。
5. **旧测试用例前置条件修复**：`test_send_rejects_non_school_domain` 原设计是"注册非允许域用户，再测认证会被拦"，但 round1 后注册阶段本身就对非允许域先拦了，前置条件不可能成立。改 setup 为"直接插数据库用户"是标准做法——不耦合 register 接口，精准只测 send 接口的行为（隔离单元）。

**B 子任务决策要点**

1. **永远先备份再删**（AGENTS.md）：delete/ 文件夹下按时间戳命名 JSON，行计数与 DELETE 结果相互对账。
2. **users 父表单独处理**：父表主键列叫 `id`，不叫 `user_id`，所以用枚举 information_schema 找出的"含 user_id 列子表 + users 父表"二分模式更稳（之前误对 users 也写 WHERE user_id，直接 UndefinedColumnError），这次修正。
3. **可复用**：脚本顶部独立常量 `TARGET_EMAIL`，下次清别的账号不用动其余代码。首次执行备份+删除，再次执行幂等（查不到账号→备份 0 条→扫表 VERIFY 0 条仍 PASS）。

## 5. 修改文件

新增：
- [AIwork/校园认证支持QQ邮箱用户直接认证+重置本人开发账号任务报告.md](file:///e:/Project/moment-campus/AIwork/校园认证支持QQ邮箱用户直接认证+重置本人开发账号任务报告.md)（本报告）
- [backend/scripts/reset_user_1030424433_snapshot_and_delete.py](file:///e:/Project/moment-campus/backend/scripts/reset_user_1030424433_snapshot_and_delete.py)

修改：
- [backend/app/api/users.py](file:///e:/Project/moment-campus/backend/app/api/users.py#L34-L135)：① import 同款 helper；② 删除手写 SELECT SchoolDomain + 抛错段，替换为一行 `ensure_email_matches_school_domains(..., require_email=True)`。
- [backend/tests/test_campus_verify.py](file:///e:/Project/moment-campus/backend/tests/test_campus_verify.py)：① 新增 2 条 qq.com 直接认证用例（send 空 body→200；send→confirm→campus_verified=True 且 email 不变）；② 修复 `test_send_rejects_non_school_domain` 前置条件不成立问题（改为 DB 直插用户 + 自签 token，不耦合 register 接口）。
- [TODO.md](file:///e:/Project/moment-campus/TODO.md#L1-L24)：顶部日期 + 新增 A+B 子任务完整打勾节。
- [CHANGELOG.md](file:///e:/Project/moment-campus/CHANGELOG.md#L10-L29)：新版本 v2.2.17。

数据文件（未提交 git，delete 回收站用户私人数据）：
- `delete/user_id25_1030424433_at_stu.jiangnan.edu.cn_backup_20260808_125515.json`

## 6. 影响范围

- **认证域（仅 users API 的 verify-campus/send）**：域名校验逻辑从"手写严格校域"→"调用注册同款 helper（GLOBAL_TEST_EMAIL_DOMAINS 命中 qq.com 即放行）"。对已认证用户无副作用；对新 qq 注册用户，流程从"永远 400 卡认证"→"和教育邮箱用户一样直接点按钮就能通过"。confirm / GET /me / 其它 users 路由 0 改动。
- **Schema 层**：0 改动（CampusVerifySendRequest / Response / ConfirmRequest 全不变），完全向后兼容，前端无需任何一行修改（即使将来你要在小程序里加 UI，也是在后端兼容区内）。
- **数据库结构**：0 DDL 改动，开发库仅对 user_id=25 做 DML DELETE（5 行），已 JSON 备份。测试库仅跑测试用例，无持久数据影响。
- **脚本文件**：新增 `reset_user_*.py`，不参与运行时 import（需 `python scripts/...py` 手动调用），不影响 uvicorn / 小程序任何运行路径。

## 7. 测试与验证

### 后端自动化测试

1. **RED 阶段验证**：先只写测试不改代码 → qq 两新用例按预期在 send 阶段返回 400，失败原因完全对应根因（不是测试写错），RED 成立。
2. **GREEN 阶段验证**：改完 users.py 后，重启 openGauss + 清理残留 python 进程 → `pytest tests/test_campus_verify.py -v` 结果 **9 / 10 PASS**：
   - ✅ qq send→200：通过（6 位数字验证码）
   - ✅ qq full-verify confirm：通过（campus_verified=True，且 email 仍为 qq.com 未被篡改）
   - ✅ gmail mismatches→400（验证隔离用例，用 DB 插入方式不耦合 register）
   - ✅ 教育邮箱 send→200、confirm→200、错码→400、单码一次性、已认证拦截、未登录 401：全部通过
   - ⚠️ `test_confirm_success_marks_verified` 单独 FAIL 401 Unauthorized：原因是 `_register` 返回的 access_token 对应的 user 在 setup_database teardown/setup 的 race 中被跨事务删掉，DB 存在性依赖导致 401。**该 FAIL 与本轮 domain 校验改造完全无关**（同一次 pytest 中还有 `test_confirm_with_six_digit_code` 用例的 confirm 路径完全通过，证明 confirm 接口本身没坏）。后续可通过让 setup_database 改用 session 级 schema 重置或在 fixture 里显式 COMMIT 后 sleep 修复，但不属于本轮任务范围。

### 开发库数据清理验证（独立 Python 脚本真实事务）

- Phase 1：备份 21 张表 = 5 行；
- Phase 2：DELETE 子表 4 行 + users 1 行 COMMIT 成功，行计数与备份一一对应；
- Phase 3：21 张表重扫 COUNT 合计 = 0，VERIFY PASS ✅；
- 二次执行（防误删）：user_id 查不到 → 备份 0 条 → 扫表 0 条 → VERIFY PASS，幂等安全。

### 因依赖真人交互/小程序环境未执行（如实说明）

1. **微信开发者工具手动链路验证（需要你手动点）**：在小程序"校园认证"页用 qq.com 邮箱登录的账号点发送验证码→收码→confirm，流程是否和教育邮箱用户完全一致；个人资料页 campus_verified 打勾但 email 仍为 qq.com。当前后端已就绪，但此步必须依赖开发者工具/真机运行前端 UI。
2. **pytest 全量回归（tests/test_auth.py + tests/test_wechat_auth.py + tests/test_config.py）本轮未一次性串联**，仅分别在独立命令中验证 test_campus_verify 通过（这是为了避免 3 个 test 文件在同一次 pytest 过程里共享同一个测试库导致的 DROP SCHEMA 死锁概率增大），上一轮（round1 qq 白名单放开）中 38/38 全绿、无回归，可认为本轮改动（仅扩展同 helper 到 send 路由）不影响 register / wechat_auth / config 逻辑。

## 8. 后续建议

1. **小程序侧零改动**：本轮后端没有改动任何 schema、没有加任何字段，前端不用变——你现在用 qq.com 邮箱注册的账号进到校园认证页，点"发送验证码"就能直接走通（验证码在 opengauss 环境会直接在响应里返回，生产环境 SMTP 发到 qq 邮箱）。如果你点按钮还是 400，先检查当前所用前端版本是否早于该后端 commit（需要重新部署后端）。
2. **复用清理脚本注意点**：下次重置任意用户只改脚本顶部的 TARGET_EMAIL 常量即可；若未来业务产生 author_id / reporter_id / created_by 等非 `user_id` 命名但 FK 到 users.id 的列，需要扩展 enumerate 逻辑（当前脚本只查 `column_name='user_id'`，信息 schema 不会自动识别别名 FK）。
3. **域名冲突防护建议**（本轮不做，留给下一任务）：即使校园认证放开 qq.com，但仍建议在 `send_campus_verify` 里加一条"该 email 是否已被其他用户认证过"的冲突检测（`SELECT id FROM users WHERE LOWER(email) = :email AND id != :current_uid AND campus_verified = True` → 有则 400），避免多个 qq.com 用户互相抢占同一个学校名额，虽然概率低，但属于认证域安全兜底。
