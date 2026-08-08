# 更新日志

本文件记录"此刻校园"项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

> **说明**：自 2026-07-26 起，详细的任务级变更追踪改由 `TODO.md` + `AIwork/` 任务报告维护，本文件仅保留版本级里程碑摘要。

## [2.2.28] - 2026-08-09

### 修复

- 修复已绑定微信账号退出后再次登录仍进入手机号和学校绑定页的问题。
- 新增微信 OpenID 快速登录接口；同一微信身份已绑定手机号后直接复用原账号和学校，不重复创建账号。
- 修复微信登录 code 只能使用一次导致短信绑定失败重试失效的问题。

### 验证

- 后端手机号认证定向测试 8/8 通过。
- 小程序 TypeScript 类型检查、格式检查和登录页 WXML 局部编译通过。

## [2.2.27] - 2026-08-09

### 变更

- 完全重写测试数据生成脚本，支持三所学校共150用户（每校50人）、1500帖子（每校500帖）的大规模演示数据生成。
- 新增口语化内容素材库，帖子标题/正文/评论/地点评价全部采用自然口语表达，无Markdown格式，加入随机语气词扰动提升真实感。
- 互动数据采用幂律分布生成，点赞/评论/协同验证数量模拟真实社区热度分层。
- 集成Embedding自动生成，数据导入完成后自动为所有已发布帖子批量生成512维向量，AI语义搜索立即可用。
- 修复预置手机号硬编码位数错误，改用学校手机号前缀+序号动态生成。
- 修复互动数据时间计算边界问题，避免帖子创建时间过近时随机数范围为空异常。

### 验证

- seed脚本完整运行成功，统计验证：150用户、1500帖子（覆盖全部6态）、22369点赞、4231评论、1105协同验证、582地点评价、1410条Embedding向量。
- 每个地点评价数≥10条，满足演示要求。

## [2.2.26] - 2026-08-09

### 变更

- 游客切换学校时只更新本地浏览学校，不修改账号绑定关系；登录用户继续使用原有绑定学校切换流程。
- 游客点击小程序底部“发布”按钮时只弹窗提示登录，不执行页面跳转；登录用户正常进入发布页。
- 修复真实推理模型因发帖 AI 输出 token 上限不足而返回空 JSON 的问题，并将发布建议降级文案与搜索场景区分。
- 小程序发帖 AI 请求补齐分类、地点、联系方式、失物类型和截止时间；修复手机号被重复识别为 QQ 号，并保留用户已选分类。

### 验证

- 小程序 `npm run typecheck`、`npm run test:format` 通过。
- 微信开发者工具局部 WXML/WXSS 编译请求因微信侧 `-80408` 频率限制未完成，未虚报为通过。
- 发帖 AI 定向后端测试 52/52 通过；真实 8000 接口返回 `fallback=false` 的结构化建议，手机号敏感检测仅命中 `phone`。

## [2.2.25] - 2026-08-09

### 新增

- 新增 `POST /auth/wechat/sms-login`，支持微信会话通过真实手机号短信验证码绑定或复用手机号账号并登录。
- 统一微信手机号授权与短信绑定登录的账号创建、OpenID 绑定及历史无手机号壳账号合并规则。
- 小程序登录页改为“微信登录 → 输入手机号 → 短信验证码 → 绑定并登录”两阶段流程，不再依赖受主体认证限制的手机号授权弹窗。
- 登录第二阶段增加学校选择器；新账号初始绑定所选学校，已有账号仍使用服务端绑定学校，只有个人主页切校会修改绑定；首页监听学校变化并绕过刷新节流重载学校作用域数据。
- 学校选择页增加实时搜索栏，支持按学校名称、城市、地区、描述和 code 筛选，并优化卡片选中态与底部确认交互。

### 文档

- 同步 README、用户流程、API、认证路线图、小程序契约矩阵、上线指引和现行产品文案，并新增中文任务报告。

### 验证

- 后端手机号认证定向测试 `tests/test_phone_auth.py` 7/7 通过；按任务要求未执行后端全量测试。
- 小程序 `npm run typecheck`、`npm run test:format` 通过，登录页 WXML/WXSS 已通过微信开发者工具编译且控制台无错误。
- 运行中后端已加载 `/api/v1/auth/wechat/sms-login`；真实手机号收码和最终登录留给用户真机验收，未发送测试短信或虚构通过结果。
- 后续补齐虚拟环境阿里云号码认证 SDK 后，已向 `153****0630` 成功发送真实 `login` 短信并确认正式库落入 `provider=aliyun` 流水；未读取或记录用户验证码。
- 更新后的手机号认证定向测试 7/7、小程序类型/格式检查、`pip check`、登录页 WXML/WXSS 编译和控制台检查通过；微信 automator 仍因当前真机调试会话占用而超时。
- 学校选择页 WXML/WXSS 编译、模拟器打开和截图视觉复核通过；自动输入搜索词仍受 automator 会话占用限制，未虚构为已通过。

## [2.2.24] - 2026-08-08

### 变更

- **账号安全卡片收窄**：个人中心「账号安全」改为默认折叠不展开输入框，标题弱化（outlined 样式 + 小字号 + 灰色文字 + 右箭头），点击才展开设置密码/解除教育邮箱绑定表单；整体位置从校园认证之后移到页面最底部（我的发布之后），更隐蔽不易误触。
- **发布页移除新增地点联动**：发帖页地点下拉框删除「✚ 新增地点」选项及对应的地图选点/新地点名称/场所类型/描述虚线表单卡片；PostForm 状态与类型同步清理，发布时仅可选择已有核验地点或不选地点。

### 验证

- `frontend npm run build` 全量 TS 类型检查 + Vite 生产构建 0 错误 0 warning（仅 maplibre 体积提示不影响）。

## [2.2.23] - 2026-08-08

### 变更

- 重构三校 `seed_data.py`：用户、帖子、评论、协同验证、专题、通知和举报全部按手机号关联。
- 新生成用户的历史 `users.email` 全部为空；教育邮箱与校园认证状态保持一致并受唯一约束。
- 增加 `13800138000` 无密码微信手机号登录演示账号及固定 Mock `wechat_miniprogram` 身份。
- 清库时显式处理认证身份、会话、短信验证和绑定票据表，并更新当前演示指南、E2E helper 与手工验证脚本。
- 根目录 README 同步手机号/短信/微信手机号登录说明及三校演示账号。
- 本地 openGauss 环境增加阿里云短信和微信真实登录配置入口；未填写凭据时不启动真实服务链路。
- 阿里云短信模板按注册、登录、设置密码和解绑教育邮箱用途分别配置，保留旧通用模板兼容能力。

### 验证

- 完成一次 openGauss seed 清空重建及定向数据校验；手机号登录和 Mock 微信手机号登录均可复用预置账号。
- 仅执行改动相关后端测试与前端/小程序定向检查，未执行后端全量测试。

## [2.2.22] - 2026-08-08

### 变更

- 将业务登录身份切换为手机号：Web 支持短信验证码/密码登录和手机号注册，密码可空以支持微信新账号。
- 小程序改为微信手机号授权自动登录/建号，保留微信身份记录并按手机号复用账号。
- 教育邮箱独立用于校园认证，增加邮箱唯一绑定、邮件验证码认证和手机号短信确认解绑。
- 新增 Mock/阿里云短信 Provider 与 `sms_verifications` 验证记录；密钥只从环境变量读取。

### 验证

- 后端手机号认证定向测试 4/4 通过；Web 构建、小程序类型/格式检查、微信开发者工具编译通过。
- 本版本按任务要求未执行后端全量测试。

## [2.2.21] - 2026-08-08

### 新增

- **Web 端新增地点双入口方案（修复 E2E 问题 3）**：
  - **LocationPage 顶部按钮**：校园地点页页头右侧新增蓝色主按钮「新增地点」+ Plus 图标，未登录跳转登录页并 Toast 提示，登录后直接打开 CreateLocationModal；创建成功后刷新地点列表并打开该地点详情弹窗。
  - **MapPage 浮动圆形 FAB**：地图页右下角（绝对定位 `bottom-5 right-5`，`z-index=60`）新增湖蓝渐变圆形加号浮动按钮（48×48），不遮挡地图缩放控件，点击打开同一 CreateLocationModal；创建成功后 invalidateQueries 刷新列表 + Toast 成功提示并自动跳转 `/locations/{id}` 地点详情页。
- **可复用 CreateLocationModal 通用组件**：完整 5 字段表单——① 地图选点按钮 + 状态提示（`尚未选择位置` / `已选位置 · lat, lng`）② 地点名称必填输入框 ③ 场所类型 7 枚举下拉框（`LOCATION_TYPE_OPTIONS` SSOT）④ 描述 textarea + `0/480` 字数计数器 + placeholder 引导填写营业时间/入口/规则 ⑤ 取消 + 提交新增地点双按钮；提交接口 `POST /api/v1/locations`，创建成功后 `onCreated(createdId)` 回调交给父页面自定义链路。
- **发布页 PostForm 联动创建地点两字段补齐（修复 E2E 问题 4）**：PostForm 地点下拉框选「✚ 新增地点（地图选点，提交后进入核验队列）」后展开的 locationCreateSection，与 CreateLocationModal 字段 SSOT 对齐——新增【场所类型】7 枚举可选下拉框 +【描述】textarea（`maxLength={480}`，placeholder 引导填写开放时间/使用规则/联系方式），连同原有的名称 + 地图选点按钮共 4 字段形成完整创建闭环。
- **SSOT（Single Source of Truth）基建（避免未来两端字段漂移）**：
  - `frontend/src/constants/locationTypes.ts`：统一 `LOCATION_TYPE_OPTIONS` 7 项常量（教学楼 / 食堂 / 宿舍 / 运动场 / 服务点 / 公共空间 / 其他），CreateLocationModal 和 PostForm 发布页同引用，修改一处两端同步。
  - `frontend/src/utils/buildLocationDescription.ts`：统一地点描述拼接函数——格式「场所类型：{type}\\n{description}」（留空字段跳过，不会残留空行），CreateLocationModal 和 PostForm 发布页同样调用入库，保证格式一致性。

### 验证

- 前端硬门禁三验零 error：`npm run typecheck`（TS 静态检查 16 警告 0 错误）、`npm run lint`（ESLint 11 警告 0 error）、`npm run build`（Vite 生产构建 3.25 MB 产物一次性通过）。
- 3 条浏览器 E2E 链路全通过：
  ① MapPage 浮动 FAB → 填 5 字段 → 成功创建 ID=42「E2E_北区运动场馆」，地图弹窗显示拼接后的场所类型+描述 ✅
  ② LocationPage 顶部按钮 → 弹出 CreateLocationModal，5 字段完整渲染无异常跳转 ✅
  ③ PublishPage 选新增地点选项 → locationCreateSection 展开后两字段完整渲染 ✅
- 后端定向回归 pytest：`tests/test_auth.py` 16 + `tests/test_wechat_auth.py` 22 = **38/38 全绿**（45.26s，零回归）

## [2.2.20] - 2026-08-08

### 修复

- 修复小程序注册页邮箱 Tab「立即注册」永远 400 失败的 P1 级 Bug：`pages/register/register.ts` 错误地调用 `wechatRegister` 并传入空 `binding_ticket`，改为调用正确的 `emailRegister` 接口（无需 binding_ticket），邮箱注册链路一次通过。
- 修复教育邮箱注册后未自动通过校园认证（`campus_verified` 始终为 False）的体验缺陷：在 `services/school_domain.py` 新增 `auto_verify_campus_domain_match()` 统一 Helper，当邮箱域名命中该校任一 `SchoolDomain`（官方主域名或 addl_domains 附加域名）时，自动标记 `campus_verified=True` 并记录认证时间；运营邮箱 `@momentcampus.com` 与测试通用邮箱 `@qq.com` 仍保持需手动走验证码流程。`/auth/register` 与 `/auth/wechat/register` 两个注册接口在创建用户 flush 后统一调用。

### 新增

- 阶段七 四流程闭环 E2E：使用 wechatide-skill automation_evaluate 与 browser_use 子智能体完成小程序端 + Web 端注册 × 登录 × 发布 × 新增地点四条核心链路的端到端验证，并做对照找差异。

### 测试

- 后端定向回归 auth + wechat_auth：`pytest tests/test_auth.py tests/test_wechat_auth.py -v` 共 38 项全通过（修复前 2 条预期 False 失败 → 修复后对齐新行为改为 True，零回归）。
- 覆盖场景：江南大学 / 浙大 addl_domains 附加域名自动认证、qq.com 与 momentcampus.com 不自动认证保持原行为、域名拦截 400、微信绑定冲突 409、会话管理、身份管理、登录懒建身份。

## [2.2.19] - 2026-08-08

### 变更

- 校园身份认证仅对注册时选择的学校开放；切换学校不会使原认证失效，切回注册学校后继续有效。
- 普通用户切换到其他学校后进入只读模式，后端统一拦截发布、评论、点赞、协同验证、地点评价、资料提议和新增地点等写操作；管理员权限保持兼容。
- Web 与微信小程序在非注册学校隐藏校园认证入口和个人资料“已认证”标识，并显示当前学校仅支持浏览的提示。
- 新增 `users.registration_school_id` 及数据库迁移，历史用户按原 `school_id` 回填。

### 测试

- 定向后端校园认证/只读测试：17 passed、1 skipped。
- Web `npm run build`、小程序 `npm run typecheck`、`npm run test:format` 通过。

## [2.2.18] - 2026-08-08

### 新增

- 地图页和全部地点页新增校园地点入口，认证用户可提交名称、坐标及补充资料，管理员用户可直接提交，地点默认进入核验队列。

- **微信小程序真机调试切局域网模式**（解决模拟器正常、真机永远"连接超时/请求失败"的问题）：
  真机环境"localhost/127.0.0.1"指向的是手机自身而非开发电脑，此前**业务代码走 `config/env.ts`（已是局域网 IP），但 AI Skills 的两张 util 仍硬编码 `http://localhost:8000`**，导致真机上图片渲染 404 + 技能内 API 直接 request:fail。本次统一 3 处 DEV_LAN_HOST 常量（当前网段=192.168.3.x → `192.168.3.10`）：
  - [miniprogram/config/env.ts](file:///e:/Project/moment-campus/miniprogram/config/env.ts) 顶部注释列出「换 Wi-Fi 必改 3 件套清单」+ PowerShell 一行式查本机 IP
  - [miniprogram/skills/moment-campus/utils/util.js](file:///e:/Project/moment-campus/miniprogram/skills/moment-campus/utils/util.js) resolveImageUrl 不再 replace 为 localhost，改用 `DEV_API_HOST + url`
  - [miniprogram/skills/moment-campus/utils/request.js](file:///e:/Project/moment-campus/miniprogram/skills/moment-campus/utils/request.js) BASE_URL 从硬编码 localhost 改为模板字符串 `${DEV_LAN_HOST}:8000`

### 移除

- 移除小程序和 Web 用户可见的内容订阅入口、订阅服务、订阅偏好开关及相关死代码；保留后端兼容接口、历史通知数据和平台商业订阅管理。

### 变更

- 修复小程序地图页和全部地点页“新增地点”按钮文字偏移：移除未注册且不可见的 plus 图标占位，确保文字在按钮内水平、垂直居中。

- 优化小程序新增地点流程：移除地图顶部“已更新”状态并将新增地点入口放到原位置；全部地点页按钮统一居中；新增地点弹窗改为地图点击选点，去除手填经纬度并在未选点时阻止提交。

- 优化新增地点表单字段：移除楼栋、区域和楼层输入，增加可选场所类型；保留地点描述并引导填写开放时间、使用规则和联系方式，类型信息兼容写入现有描述字段。

- 彻底修复小程序自定义 TabBar 跨页闪烁：源页面在路由完成前保持原高亮，目标页面仅由自身生命周期同步一次高亮；同时移除高亮过渡、点击态滞留和模糊合成层。地图首次进入不再重复请求/清空标记，个人页短时间返回复用已有数据，减少页面白屏和重绘。

- 收敛小程序 TabBar 导航状态：切换前同步目标高亮，各页面仅通过统一函数同步自己的 TabBar 实例，统一页面内 Tab 跳转入口，修复高亮在目标页与首页之间来回闪动。

- 修复小程序真机首次进入页面白屏：关闭 `requiredComponents` 组件懒加载，并将页面淡入改为首帧可见的轻微位移动画，降低 TabBar 切换闪烁。

- 修复小程序自定义 TabBar 切换时高亮跳动和失败回首页问题，增加重复点击保护；首页返回改为保留现有内容并按 60 秒窗口刷新。

- 微调小程序发布页 AI 助手卡片的背景、边框、文字层级和建议按钮间距，提升窄屏下的可读性与操作感。

- AI 辅助发布建议新增标题与正文优化结果；小程序支持一键应用，Web 支持逐项采纳，原有分类、摘要、有效期和提醒功能保持兼容。

- 修复小程序发布页底部操作栏被自定义 TabBar 遮挡的问题，操作栏改为跟随页面内容滚动，并在页面末尾预留安全空间。
- 发布页 AI 辅助发布建议移至顶部并补充用途说明；操作栏取消外层白色填充，草稿按钮改为单行显示。

- 地点详情页将补充资料表单改为“已审核资料”旁的小按钮和底部编辑弹窗，地图地点信息卡同步增加快捷入口。

- 注册和校园身份认证统一允许使用 `qq.com` 邮箱；同步更新小程序与 Web 的输入提示和域名校验提示。

- 地图地点标记改为常驻显示地点名称和评分，暂无评分的地点显示“暂无评分”。

- 修复小程序校园动态帖子点击时原生 `tap` 与自定义事件冲突导致的“参数错误”，统一改用 `posttap` 并增加帖子 ID 防护。

- 后端启动命令（[AGENTS.md](file:///e:/Project/moment-campus/AGENTS.md#L14-L19)）升级为局域网模式：
  `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`，新增对应防火墙放行规则说明。
- [miniprogram/project.config.json](file:///e:/Project/moment-campus/miniprogram/project.config.json#L32-L40) `"urlCheck": false` 上方增加中文注释，精准对应微信开发者工具
  「详情 → 本地设置 → ✅ 不校验合法域名、web-view、TLS 版本以及 HTTPS 证书」复选框，帮助新环境快速定位开关。

## [2.2.17] - 2026-08-08

### 新增

- **校园认证阶段与注册阶段域名校验规则统一**（解决 qq.com 注册用户"能注册但不能认证"的矛盾）：
  `POST /users/me/verify-campus/send` 的域名校验从原先手写 `SELECT SchoolDomain WHERE domain = 登录邮箱域`，替换为调用注册阶段同款 `ensure_email_matches_school_domains()` helper。
  自此，运营豁免域 momentcampus.com / 全局测试域 qq.com / 学校配置的允许域，**在注册和认证两个阶段的放行条件完全一致**。
  - 结果：使用 `@qq.com` 注册的用户，在小程序里点"校园认证→发送验证码"的交互与 `@example.jiangnan.edu.cn` 教育邮箱用户**完全相同**——直接发送，无需任何新增输入框
  - `CampusVerifySendRequest` 保持空 body 兼容，未引入 target_email；confirm 逻辑零改动
  - TDD：新增 2 条 qq.com 端到端用例（send 空 body→200+6 位码、send→confirm→campus_verified=True 且 email 保持 qq.com 不被篡改），修复 `test_send_rejects_non_school_domain` 原先用 /register 建 gmail 用户的方式（round1 后 register 对 gmail 本身就 400，前置条件不成立），改为 DB 直接插入用户 + 自签 access_token 精准校验

- **可复用的用户数据清理脚本**：
  `backend/scripts/reset_user_1030424433_snapshot_and_delete.py`——严格遵循 AGENTS.md 备份→删除→验证三段式流程，
  仅改顶部 TARGET_EMAIL 常量即可复用到任意账号重置。自动枚举 20 张子表 + users 父表 = 21 张表，JSON 安全序列化（datetime→ISO，bytes→hex）输出到 delete/。

### 变更

- 本人开发账号 `1030424433@stu.jiangnan.edu.cn`（user_id=25）已按规则重置：
  备份 `delete/user_id25_1030424433_at_stu.jiangnan.edu.cn_backup_20260808_125515.json`（5 条：auth_sessions×2、school_memberships×1、user_auth_identities×1、users×1），
  DELETE 后重扫 21 张表残留 = 0，VERIFY PASS。备份 JSON 未入 git（delete/ 属私人数据回收站）。

## [2.2.16] - 2026-08-08

### 新增

- **全局测试邮箱白名单域 GLOBAL_TEST_EMAIL_DOMAINS**：
  在 `app/services/school_domain.py` 新增独立于运营豁免域的全局测试域集合，默认包含 `qq.com`，所有学校的 B-01 教育邮箱校验一律放行。
  解决测试阶段校园邮箱账号数量不足问题，注册者可使用任意 `@qq.com` 邮箱在任意学校注册。
  - 新增常量 `GLOBAL_TEST_EMAIL_DOMAINS: frozenset[str] = frozenset({"qq.com"})`，未来若需放 163.com/gmail.com 等只要在此集合追加域名即可
  - `ensure_email_matches_school_domains` Rule 3 放行条件扩展为「运营豁免域 ∪ 全局测试域」命中即直出
  - Rule 5 的 400 错误文案同步更新，明确提示「或使用测试通用邮箱域（@ qq.com）」

- **注册阶段强制教育邮箱校验（B-01 统一 helper + 双接口接入）**：
  解决用户在注册邮箱时可以填任意 gmail/outlook 等非教育邮箱绕过「校园身份」的问题。

  核心 helper（新增文件）：
  - `app/services/school_domain.py`：
    - `ALLOWED_NON_CAMPUS_DOMAINS = frozenset({"momentcampus.com"})` 运营豁免域白名单（`admin@momentcampus.com` 等平台账号不受学校域名限制）
    - `parse_email_domain(email) -> Optional[str]`：统一邮箱→小写域名解析（空/无 @ 返回 None）
    - `ensure_email_matches_school_domains(db, school_id, email, *, require_email=True)`：6 条规则流水线——①空邮箱+require_email→400「请填写所选学校的教育邮箱」②非法格式→400「请输入有效的邮箱地址」③命中豁免域→放行 ④学校不存在→400「所选学校不存在」⑤有配置域名但不匹配→400 长提示（列出允许域名 + 运营邮箱说明 + 联系校管理员路径）⑥未配置任何域名（配置期极端场景）→放行避免死锁

  接入点：
  - `app/api/auth.py` `/auth/register`：确定 school_id 后、检查邮箱是否已存在前插入 B-01 校验（require_email=True）
  - `app/api/wechat_auth.py` `/wechat/register`：**删除** 旧的"空邮箱时 secrets.token_hex 生成 `wx_xxx@momentcampus.local` 临时邮箱"分支（这是 B-01 前的逃生舱，现在必须强校验）；改为调用 helper（require_email=True）；同步删除单独做的 SELECT School 存在性检查（helper 内部已覆盖，避免重复查询）

  测试修复：
  - `tests/test_auth.py` `_seed_school_with_domains`：`School.code` 长度为 varchar(20)，原 `test-school-{suffix}-{time_ns()}` 生成超长 → 改为 `t{suffix}{time_ns()%10000000:07d}` （≤ 12 字，唯一合规）
  - `tests/test_wechat_auth.py` `_seed_wechat_school_with_domains`：同构修复 → `w{suffix}{time_ns()%10000000:07d}`

### 校验

- `$env:APP_ENV=opengauss ; $env:TEST_DATABASE_URL=postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test ; backend/.venv/Scripts/python -m pytest tests/test_auth.py tests/test_wechat_auth.py tests/test_campus_verify.py -v`：**44/44 全绿**（15 + 21 + 8 = 44），耗时 50.63s
- 7 条新增目标用例 TDD RED→GREEN 完整闭环：
  RED 阶段（helper 未接入）→ 3 FAIL（`domain_mismatch_*`×2 + `empty_email_*`×1，均 expect 400 / got 200） + 4 PASS（合法域名/豁免域/空配置期）
  GREEN 阶段（helper 接入 + 临时邮箱分支删除）→ 7/7 全过
- 覆盖场景枚举：
  ✅ 邮件注册 4 条：gmail 域名不匹配→400「官方教育邮箱」+ 校名 | @example.jiangnan.edu.cn 附加域命中→200 campus_verified=False | @momentcampus.com 运营豁免域→200 | test_school 未配置任何 SchoolDomain→允许任意邮箱注册（空配置期放行不 400 死锁）
  ✅ 微信注册 3 条：不传 email 字段→400「请填写所选学校的教育邮箱」| gmail 域名→400 官方教育邮箱 + 校名 | @example.zju.edu.cn 合法附加域→200 campus_verified=False + access_token
  ✅ 回归 37 条：注册成功/冲突、微信 bind 成功/错密码/过期 ticket/双单向 409 冲突、identity 增删、session 管理、校园认证 send/confirm/错码/一次性/已认证拦截/鉴权

### 修复

- **本地开发模式「微信直接登录」永远失败 Bug 修复（MOCK 模式 openid 恒常化）**：
  后端未配置 `WECHAT_APPID`/`WECHAT_APPSECRET` 时，`exchange_wechat_code` 的 mock 分支将 openid 从 `f"mock_openid_{code[:16]}"`（派生自 wx.login() 临时 code，每次点击都变）改为**固定常量** `MOCK_OPENID_STATIC_20260808_LOCAL_DEV`，模拟真实微信 code2Session 行为：同一微信用户无论传什么临时 code，openid 都稳定不变。
  - 修复前：同一开发者反复点微信登录，会在 `user_auth_identities` 表不断堆积 `mock_` 开头的身份记录，但下次点击永远匹配不上，永远跳注册页（链路从未跑通过）
  - 修复后：绑定一次即可，后续所有「微信 Tab → 一键登录」直接命中 `authenticated` 分支，直接进首页
  - 修改文件：`app/services/wechat.py`（新增常量 + mock 分支改为常量返回）、`tests/test_wechat_auth.py`（同步更新 `test_wechat_exchange_bound` 用例，从代码推导 openid 改为直接引用导出的常量）
  - 数据库清理：删除所有旧规则下 `identity_key LIKE 'mock_openid_%'`（小写前缀）的垃圾身份共 4 条（其中 2 条属于账号 `1030424433@stu.jiangnan.edu.cn`），避免再次误命中
  - 回归：`pytest tests/test_wechat_auth.py -v` → **21/21 全绿**，无任何回归

- **小程序三页面密码框交互修复（默认隐藏小圆点 + 眼睛图标切换明文/密文）**：
  原错误写法 `<input type="password">` 在小程序部分版本/真机中降级为明文显示（密码裸奔），统一改为官方推荐 `<input type="text" password="{{布尔值}}">` + 右侧眼睛图标按钮切换。

  修改范围：
  - 修复登录页（pages/login）：1 个密码框 + 新增 `showPassword` 状态/切换方法 + `.pwd-toggle` 眼睛按钮样式
  - 修复注册页（pages/register）：密码 + 确认密码 2 个密码框 + 双独立状态 + `.pwd-input-wrap` 容器 + `.pwd-toggle` 样式
  - 修复找回密码页（subpackages/pages/forgot-password）：新密码 + 再次输入 2 个密码框 + 双独立状态 + 眼睛按钮
  - icon 组件新增 `eye-off`（闭眼）图标，与 `eye` 配对，保证隐藏态不显示空白图标

  验证：
  - wechatide-skill `check_wechatide_status` 门禁通过（chai_na 登录未过期）
  - `compile_wxml` / `compile_wxss` 分别编译 3 页面 6 份文件全部 success：0 语法错误 / 0 样式错误
  - grep 全量巡检：20 处 showPassword 相关引用（字段/方法/绑定/图标）完全对应，5 个密码框 password 属性绑定齐全

## [2.2.15] - 2026-08-08

### 修复

- **微信登录链路规范化：首次微信→注册→自动绑+登录；绑定已存在账号冲突 409 双单向校验**：
  明确三条标准链路（对应新登录页三个主路径/两个 Tab 组合），解决"登录后不自动登进""账号/微信重复绑定却无提示""注册后没把微信绑上去"三个逻辑问题。

  后端：
  - `app/api/wechat_auth.py` `wechat_bind_existing` 新增账号侧冲突检查（该账号本身是否已绑了另一个微信？）→ 409 `"该账号已绑定其他微信，不能重复绑定"`；与原 openid 侧冲突检查形成双向唯一校验（1 账号 ↔ 1 微信）
  - `app/schemas/wechat_auth.py` `WechatBindExistingResponse` / `WechatRegisterResponse` 新增 `user: dict` 字段（与 `LoginResponse` 保持同构）
  - `app/api/wechat_auth.py` `wechat_bind_existing` / `wechat_register` 响应拼装时补 `user = UserResponse.model_validate(user).model_dump()`
  - `tests/test_wechat_auth.py` 新增 `test_bind_existing_account_already_has_wechat_identity_fails`；现有 15+ 用例同步断言响应 body 包含 `user` 字段

  前端：
  - `store/auth.ts` `setAuth` 改异步：优先读响应里的 `user` 直落；只有 `user_id` 没有 `user` 时调 `services/users.ts` 的 `getMe()` → `GET /users/me` 兜底拉一次
  - `services/users.ts` 新增 `export async function getMe(): Promise<User>`
  - `pages/login/login.ts`：① onWechatLogin / onEmailLogin / onBindExistingTap 三处成功分支统一 `wx.switchTab('/pages/profile/profile')`；② 新增 `onBindExistingTap`（wx.login → exchange 判 authenticated→直登 / binding_required→调 bind-existing；exchange 其他状态抛错）；③ bindErrorMsg 独立状态（红色），409/含"已绑定"等关键字自动加"绑定失败："前缀
  - `pages/login/login.wxml` 邮箱 Tab 主按钮下插入：`divider-or` 分割线（── 或 ──）+ `bind-info-text` 说明文案 + 描边「绑定该微信并登录」次级按钮 + form-links 保留
  - `pages/login/login.wxss` 新增 `submit-btn-secondary`（白底湖蓝描边次按钮）+ `bind-info-text`（24rpx muted 文案）+ `divider-or`（两侧线段 + 中间"或"字）
  - `pages/register/register.ts` 两处成功分支 `setTimeout(() => wx.switchTab({ url: '/pages/profile/profile' }), 500)`；catch 409 或"已绑定/已被注册"类错误加"绑定失败："前缀

### 校验

- `$env:APP_ENV opengauss + TEST_DATABASE_URL postgres` → `backend/.venv/Scripts/python -m pytest tests/test_wechat_auth.py tests/test_auth.py -v`：**29/29 全通过（17+12）**，耗时 30.21s
- HTTP 链路仿真（ASGITransport AsyncClient）3 CASE 全过：
  ✅ CASE A（新微信→binding_required→register 新用户 C）：响应含 `access_token + refresh_token + user(campus_verified=False, email=新注册)`
  ✅ CASE B（同 CASE A 同一 code 再次 exchange）→ `status=authenticated` 且 `user.email` 与 CASE A 新邮箱一致
  ✅ CASE C-1 新 code FLOW_C_WECHAT_FOR_USER_A → 绑定 userA → 200 id=26；C-2 新 code FLOW_C_WECHAT_DIFFERENT 去绑同一 userA → **409 `该账号已绑定其他微信，不能重复绑定`**；C-3 已绑 openid 再次 exchange → authenticated
- `wechatide simulator_refresh`：编译通过；`simulator_open_page pages/login/login` 成功；365×787 截图登录页正常；`get_simulator_console grep -i error/fail/warn/ts` 空字符串（无运行时异常）

## [2.2.14] - 2026-08-08

### 修复

- **小程序个人中心页未登录态改为「点击登录」统一卡片**：
  用户反馈"未登录时顶部不应该是'未命名用户'，要直接统一为点击登录之类的引导，且身份认证/我的帖子/浏览历史/推荐隐私/编辑资料/通知偏好/退出登录全部隐藏"。原实现还有一个问题：`onShow` 里调 `guardPageLogin` 会强制弹 Modal 打断游客浏览（用户只想看学校选择或用户协议也会被跳去登录）——一并解决。

  按经验 322067 单一 `isLoggedIn` 布尔驱动渲染（不做占位补丁）+ 经验 344553 同一判据驱动展示与行为：

  - `profile.ts`：`onShow` 移除 `guardPageLogin` 强制 Modal；未登录分支主动 setData 清空用户残留数据避免闪烁；移除无用的 `guardPageLogin` import；新增 `onGoLoginTap` → `wx.navigateTo('/pages/login/login')`
  - `profile.wxml`：顶层 `<block wx:if="{{!isLoggedIn}}">` 渲染独立「点击登录」卡片（左 user 圆形图标 + 中 38rpx/700 标题 + 副文案 + 右 chevron-right 箭头），并保留「当前学校」卡片（学校选择游客也可以用）；`<block wx:else>` 包裹原 user-card + 统计卡 + 当前学校卡 + 校园身份认证 + 我的帖子/浏览历史 + 推荐隐私。settings-section 7 个条目中，编辑资料/通知偏好/退出登录 3 条单独加 `wx:if="{{isLoggedIn}}"`，用户协议/隐私政策/关于保留。
  - `profile.wxss`：新增 `.login-entry-card`（湖蓝背景与原 user-card 一致）+ `.login-entry-icon-wrap/.login-entry-text/.login-entry-title/.login-entry-desc/.login-entry-arrow/.login-entry-card-hover` 共 6 选择器。

### 校验

- `wechatide simulator_refresh`：编译通过，无 WXML/WXSS/TS 报错
- `wechatide simulator_open_page pages/profile/profile`：直达个人中心 Tab
- 截图（365×787 JPEG）验证：
  ✅ 顶部湖蓝「点击登录」大卡片 + 圆形 user 图标 + 标题副文案 + 右箭头 正确显示
  ✅ 「未命名用户」和「这个人很懒...」占位 彻底消失
  ✅ 身份认证 / 4 列统计 / 我的帖子 / 浏览历史 / 推荐隐私 7 项全部隐藏
  ✅ 设置列表仅保留：用户协议、隐私政策、关于（编辑资料/通知偏好/退出登录已隐藏）
  ✅ 当前学校卡片仍正常保留：江南大学 + 切换学校按钮
- `get_simulator_console grep -i error/fail/warn`：空字符串，无运行时异常

## [2.2.13] - 2026-08-08

### 修复

- **小程序校园地点页原生🏠主页按钮改为统一返回箭头**：
  问题：当校园地点页（`subpackages/pages/locations`）通过分享卡片/扫码/系统菜单等「栈空入口」进入时，微信原生导航栏左上角会强制显示🏠返回首页图标；而从 navigateTo 常规入口进入时则显示<返回，入口间显示不一致且用户偏好返回语义。
  由于原生导航栏的🏠图标不可通过 JSON 静态配置替换（经验 ID 310587），采用策略B——自绘自定义导航栏并统一为返回箭头：
  - `locations.json`：删除 `navigationBarTitleText`，切换 `navigationStyle: custom`
  - `locations.ts` onLoad：精确计算 `statusBarHeight + navBarHeight`（基于 `getSystemInfoSync + getMenuButtonBoundingClientRect` 胶囊尺寸推导，默认回退 20+44）并注入 data
  - `locations.wxml`：页面最顶端插入 `.custom-nav`（sticky top0 + z999）→ `.custom-nav-status` 状态栏占位 + `.custom-nav-content` 左返回按钮 + 中央绝对居中标题 + 右对称占位 + `.custom-nav-shadow` 底部分割阴影
  - `onBackTap` 双分支：`getCurrentPages().length > 1` → `wx.navigateBack({delta:1})`；否则 → `wx.switchTab('/pages/home/home')`（与原🏠行为等价但视觉始终是返回←）
  - `locations.wxss`：补 `.custom-nav-*` 5 个选择器，返回按钮圆形 64rpx、hover 缩放 0.92 变湖蓝；背景使用 `--paper` 与品牌色一致；.locations-page padding-top 改为 0，内容下移 24rpx padding 由 locations-content 承载
  - `components/icon/icon.ts`：ICON_PATHS 补齐 `chevron-left` 路径（lucide 标准），避免箭头空白

### 校验

- `wechatide simulator_refresh`：编译通过，无 WXML/WXSS/TS 报错
- `wechatide simulator_open_page subpackages/pages/locations/locations`：直达校园地点页
- 截图（365×787 JPEG）验证：① 左上角显示 ← 返回圆形按钮（不再是🏠主页图标）；② "校园地点"标题加粗居中；③ 状态栏与内容不重叠；④ 搜索胶囊与7张地点卡片正常渲染；⑤ 点击返回后返回首页（栈空 switchTab 行为符合预期）
- `get_simulator_console grep -i error/fail/warn`：空字符串，无运行时异常

## [2.2.12] - 2026-08-07

### 修复

- **小程序校园地点页搜索栏看不清**（用户反馈"有点看不清吧"）：根本原因是 `subpackages/pages/locations/locations.wxml` 引用了 `location-search-wrap` class，但对应 WXSS 文件中完全没有定义该选择器，导致搜索区无背景、无边框、无 padding，图标与文字与 mist 背景混色。修复：
  - WXSS 补齐 `.location-search-wrap`：88rpx 高度 + 999rpx 胶囊圆角 + 纯白 `var(--paper)` 背景 + 湖蓝描边 `rgba(23,77,94,0.18)` + 淡阴影 `0 8rpx 22rpx`
  - focus/active 态自动加强为湖蓝描边 + 加深阴影
  - WXML 同步加强对比度：搜索图标 `color="#6a7d81"→"#174d5e"`，size 28→30rpx；input 字号 28rpx + 500；placeholder 专用 `location-search-ph` 为 `#8a9a9e`（更清晰但仍保留占位语义）；键盘确认按钮改为 `confirm-type="search"`

### 校验

- 微信开发者工具 `simulator_refresh` 编译成功，`simulator_open_page subpackages/pages/locations/locations` 直达目标页
- 最终截图（365×787 JPEG）验证：搜索框呈现清晰白色胶囊形态——白底、圆角、湖蓝放大镜图标、深灰占位文字，与卡片列表和 mist 背景对比度明显，一眼可识别
- 运行时 console 无 error/warn 新增

## [2.2.11] - 2026-08-07

### 修复

- **小程序地图页地点详情弹层点击全部无反应**：根本原因是外层 `scroll-view` 绑定了 `catchtouchstart/catchtouchmove/catchtouchend`，以 `catch` 前缀捕获型事件阻止了所有内部元素的 `bindtap` 事件冒泡（包括 `post-card` 帖子卡片、`goto-detail-btn`「查看完整详情」按钮、星级评分、提交/撤回按钮等所有可交互元素）。修复方式：
  1. 改为 `bindtouch*`（冒泡型），不再无条件吞掉触摸事件
  2. 手势处理函数新增 `_sheetGestureBlocked` 状态变量，仅当用户确实在进行面板拖拽时才处理，其余点击/轻触正常放行
  3. expanded 态新增 `_sheetPullFromExpanded` 下拉判定逻辑，已滚动时不误触发面板收起

### 新增

- **小程序地图页地点详情补齐评分界面（与 Web 端 LocationPage 对齐）**
  - **评分汇总卡片**（详情最顶部）：顶行左侧大星级 + 评分分数，右上角放置「查看完整详情」主按钮；下方展示评分人数/评价条数、地点描述、位置标签
  - **我的评价卡片**：遵循 Web 端统一布局约束——
    - 常态只读：显示作者「我」+ 星级 + 评分 + 文字评价，顶行右上角为「更新评价」主按钮
    - 编辑态展开：星级选择器（5 档可选）+ 文本输入（最多 500 字）+ 提交主按钮（顶行右上角），底部右对齐放置「取消编辑/撤回评价」次要按钮
    - 未登录态：显示登录引导 + 「去登录」按钮；未校园认证态：显示提示文案并禁用提交（与 Web 权限口径一致）
  - **逻辑层补齐**：`submitReview` / `withdrawReview` 在提交/撤回成功后自动并行重新拉取地点详情与评价列表，就地刷新 `selectedLocation.location`、`scoreText`、`averageStarsText`、`myReview`

### 校验

- 微信开发者工具：`check_wechatide_status` 通过（登录未过期），`open_project_window` 复用既有窗口，`simulator_refresh` 编译成功
- `get_simulator_console grep -i -E 'error|fail|warn'` 返回空字符串，无运行时异常
- 地图页 simulator_screenshot 验证：Header 显示「江南大学」+「已更新」，地图标记正常渲染，TabBar 选中「地图」

## [2.2.10] - 2026-08-07

### 新增

- **历史帖子 PostImage.thumbnail_url 批量补写脚本（两入口）**：
  解决 v2.2.9 之前发布的图片帖子 `PostImage.thumbnail_url IS NULL` 导致详情页缩略图仍加载原图的遗留问题（与 v2.2.9 thumbnail_url 入库修复配套，形成完整闭环）。
  - `backend/scripts/fix_post_image_thumbnails.py`：独立运维脚本，支持 `--dry-run` 预估行数，单条 UPDATE + 1 次 COMMIT 原子完成，幂等（仅改 NULL 行，绝不覆盖已有缩略图）、安全（仅作用于 image_url 前缀 `/uploads/` 且文件名非空的行）
  - `backend/scripts/seed_data.py --only-fix-thumbnails`：seed 工具内置同一套补写能力（SQL 完全同构、结果与独立脚本等价），支持 `--dry-run` 只 COUNT 不 UPDATE；`--no-fix-thumbnails` 可临时关闭默认补写；完整 seed 运行时默认在写入侧 commit 前自动执行一次补写，保证新 seed 环境直接缩略图带宽优化生效

### 实现（与 upload.py 命名规则严格对齐）

- 补写规则（openGauss / PostgreSQL 兼容语法）：
  `thumbnail_url = '/uploads/thumb_' || substring(image_url FROM '/uploads/(.*)$')`
  与 `backend/app/api/upload.py` 缩略图生成命名
  `thumb_{uuid}{ext}` 完全一致，不会出现"DB 有 thumbnail_url 但磁盘文件不存在"的错配
- WHERE 四重过滤：`thumbnail_url IS NULL AND image_url LIKE '/uploads/%' AND char_length(image_url) > 10 AND substring(...) IS NOT NULL`，
  避免误伤非托管 URL、空文件名和异常路径
- **seed_data.py 结构优化**：新增顶层 `fix_missing_thumbnails(session, dry_run=False) -> int` 独立函数，可被其他脚本或管理端定时任务直接 import 复用；CLI 从裸 `asyncio.run(seed_data())` 扩展为 `argparse` 三参数结构，带 4 条常用使用示例 docstring

### 校验

- `py_compile scripts/seed_data.py scripts/fix_post_image_thumbnails.py`：0 Error 0 Warning
- `--help` 输出正常（两脚本独立跑通，示例说明与实现一致）
- 纯 Python 等价模拟补写推导：`/uploads/abc123.jpg → /uploads/thumb_abc123.jpg ✅`；`/uploads/`、非 `/uploads/` 前缀、空 basename 全部安全 SKIP ✅

## [2.2.9] - 2026-08-07

### 修复

- **thumbnail_url 永远为 null 导致缩略带宽优化未生效的 Bug**：上传接口 `POST /upload/image` 已返回 `{url, thumbnail_url}` 两个 URL，但之前从「前端表单 → 后端 Schema → 写入 DB」整条链路只传递了 `image_url`（原图），导致 `PostImage.thumbnail_url` 列一直为 NULL，详情页缩略图缩略即使代码层面写了「优先 thumbnail_url」实际仍回退加载原图（浪费 90% 带宽）。本次彻底打通全链路：

  1. **后端 Schema 升级兼容两种输入**：新增 `app/schemas/post.py PostImageInput(image_url, thumbnail_url?)` 数据结构；`PostCreate` / `PostUpdate` 同时保留旧 `image_urls: string[]` + 新 `images: PostImageInput[]` 两字段，通过 `@model_validator(mode='after') normalize_images_fields` 自动把旧版字符串数组归一化为新版对象数组（images 优先，避免冲突），对旧前端和 API 调用方 100% 向后兼容
  2. **后端写入双字段入库**：`create_post` 遍历 `post_data.images[]` 同时写入 `PostImage.image_url + PostImage.thumbnail_url`；`update_post` 兼容三种输入（`string[]` 旧前端 / `PostImageInput[]` 新 Schema / `dict[]` 极端场景）全删后按 idx 顺序重建，保证新前端传的 thumbnail_url 不丢
  3. **前端 services**：`CreatePostRequest` 新增 `images: Array<{image_url,thumbnail_url?}>`，同时保留 `image_urls` 做兼容，`updatePost` 复用同一 Partial 类型
  4. **前端 PostForm 表单全链路升级**：① `PublishFormState.image_urls → images[]`（带 thumbnail_url）；② `handleImageChange` 上传成功后 push `{image_url: resp.url, thumbnail_url: resp.thumbnail_url}` 对象数组；③ 编辑态回显保留 DB 里已有的 thumbnail_url；④ 提交 payload 传新版 images 字段；⑤ 预览条缩略图缩略优先用 thumbnail_url，预览加载更流畅；⑥ `DRAFT-MIGRATION-1`：旧本地草稿只有旧 image_urls 数组时，`loadDraft` 自动迁移到新结构并删除旧字段，用户再次打开发布页草稿无缝过渡

### 一致性保证（不破坏旧版本）

- 旧前端（仍传 `image_urls` 字符串数组）：后端 validator 自动转 images[]，**发布/编辑正常无任何报错**，但由于旧前端不传 thumbnail_url，PostImage.thumbnail_url 仍为 NULL（回退加载原图），是"安全降级"不是 Bug
- 新版前端：整条链路 thumbnail_url 完整传递，详情页缩略图缩略加载 thumb_xxx.jpg（约 30-80KB/张 vs 原图 2-5MB/张），**9 张缩略节省约 20-40MB 单次访问流量**

### 校验

- 后端 `import app.api.posts / schemas.post` 静态通过
- `PostCreate.model_validate(旧 image_urls=)` / `(新 images=)` / `PostUpdate.model_validate(旧/新)` 4 组样例归一化后 images 长度与原始输入一致
- 前端 `npx tsc -p tsconfig.json --noEmit` 0 错误

## [2.2.8] - 2026-08-07

### 修复

- **帖子列表页 cover_image 顺序不一致 Bug**：原 `GET /posts` 列表接口取 `post.post_images[0].image_url` 作为封面，依赖 selectinload 默认的主键自增顺序，未按 `sort_order` 排序；当用户更新帖子时重新排序图片（全部删除再按新顺序重建）或图片 sort_order 非连续时，封面可能取到非第一张图；本次修复为**封面取图与详情页 images 顺序统一**：先 `sorted(post.post_images, key=lambda i: i.sort_order)` 再取 `[0].image_url`，与详情页 8 张缩略图顺序严格对齐
- **PostDetail 缩略图浪费带宽 Bug**：后端 `upload.py` 已生成 `thumb_xxx.jpg`（300×300）缩略缩略，但原 `PostDetailPage` `<img src={img.image_url}>` 直接加载原图（可能 2~5MB）；本次修复：缩略缩略图 `src={img.thumbnail_url \|\| img.image_url}`，优先使用后端生成的缩略图，节省约 90% 带宽 + 首屏缩略加载时间
- **图片加载失败时显示破损图标**：原 PostDetail 主图和缩略图缺少 onerror 兜底，图片缺失或链接损坏时会显示浏览器默认破图图标；本次新增 `brokenImgUrls Set` + `handleImgError(src)` 统一 fallback：① 主图加载失败 → 切换为 `<ImageIcon size=40>` 灰色占位；② 缩略图失败 → 单张缩略图显示 `<ImageIcon size=20>` 占位；③ 所有 img 统一加 `loading="lazy"` 懒加载，首屏大图不阻塞页面渲染

### 链路静态检查结论（上传→入库→渲染完整 8 步）

1. 前端发布上传 `PostForm.handleImageChange` → `POST /upload/image` → 返回 `/uploads/<uuid>.<ext>`，前端追加 `formData.image_urls` ✅
2. 提交发布/更新 → 后端 `POST /api/v1/posts` / `PUT /api/v1/posts/{id}`：create 时按 idx 写 PostImage.sort_order；update 时全删后重建 ✅
3. `backend/uploads/` 目录与 `/uploads` URL 双向挂载：① `backend/app/main.py` L142 `StaticFiles(directory=UPLOAD_DIR)` 直接提供；② `frontend/vite.config.ts` L22 Vite dev 代理 `/uploads` → 127.0.0.1:8000 ✅
4. 列表接口 cover_image 按 sort_order 取第一张 ✅（已修复）
5. 详情接口 images 按 sort_order 排序列出 ✅（L302-308）
6. PostDetail 轮播主图切换/序号显示 ✅
7. PostDetail 缩略图缩略优先 thumbnail_url ✅（已修复）
8. 图片 onerror fallback + loading="lazy" ✅（已修复）

### 校验

- 后端 posts / identity_mask / schemas.post 静态 `__import__` 通过
- 前端 `npx tsc -p tsconfig.json --noEmit` 0 错误（PostDetailPage.tsx 新增 35 行无 TS 报错）

## [2.2.7] - 2026-08-08

### 修复

- **匿名发布身份泄露漏洞**：原实现中，匿名帖子/评论的 `user_id` 仍为真实作者 ID（仅 `author` 对象置空），前端若直接读取 `user_id` 可唯一反查作者身份；本次将 `PostResponse` / `PostListResponse` / `CommentResponse` / `LocationReviewResponse` 的 `user_id` 全改为 `Optional[int]`，匿名时统一返回 `null`；引入 `app/core/identity_mask.py` 工具模块，`should_reveal_identity` / `build_author_brief` / `apply_author_mask` 三个函数统一处理脱敏口径——**非匿名 / 本人 / 管理员**三类情形豁免显示真实身份，其余一律 `author=null + user_id=null`；替换 `posts/comments/locations/recommendations/search/topics` 六个模块内分散的手写 `if is_anonymous` 分支，避免不同接口口径不一致
- **location summary AI 证据卡片口径不一致**：原 `load_summary_sources()` 对摘要证据来源卡片的 `author_name` 匿名一刀切隐藏，管理员与本人无法看到真实昵称；本次新增 `current_user` 参数与 `should_reveal_identity()` 豁免判断，与帖子详情页脱敏口径对齐

### 新增

- **学校设置级匿名发布开关校验（写入侧）**：`POST /api/v1/posts` 创建帖子与 `PUT /api/v1/posts/{id}` 更新帖子两处写入口，当请求 `is_anonymous=true` 时读取 `school_settings.allow_anonymous`；学校关闭匿名发布时返回 400（管理员 / `super_admin` 豁免，便于发布匿名演示帖）
- **公开学校 settings 接口**：`GET /api/v1/schools/current/settings`（对游客开放，无需登录），返回对普通用户可见的学校公共设置（`allow_anonymous` / `allow_comments` / `publish_frequency` / `image_limit` / `default_validity_days` / `require_review`），供前端发布页做禁用控制和限额提醒
- **前端匿名徽章（Badge）**：`HomePage`（推荐列表 + 卡片列表）和 `PostDetailPage`（帖子作者行 / 顶级评论 / 子评论）共 5 处，`is_anonymous=true` 时在认证徽标旁显示浅灰胶囊「匿名」徽章，作者本人和管理员（豁免看到真名的人）可明确知道：「这条内容对外是匿名的，别人看不到作者身份」
- **useCampusStore publicSettings 缓存**：新增 `PublicSettings` 状态 / `fetchPublicSettings()` 方法；初始化（init）、切校（setCurrentSchool / setCurrentSchoolById）、fallback 分支都会清空并重新拉取 `GET /api/v1/schools/current/settings`；`publicSettings` 不做持久化（设置会变，每次刷新/切校重拉）；暴露 `allowAnonymousSelector`（缺省 `true`，避免接口失败误禁用）
- **PostForm 匿名 checkbox 禁用控制**：当学校 `allow_anonymous=false` 且当前登录用户不是 admin / super_admin 时，`is_anonymous` 复选框 disabled + 下方显示灰色小字「当前学校已关闭匿名发布」；同时新增 `useEffect` 兜底：切校或设置变更时，不允许匿名的环境下自动把 `formData.is_anonymous` 回退为 `false`

### 校验

- 后端所有修改模块的静态 import 检查通过（identity_mask + schemas + 6 个 API 模块 + services/location_summary，全部 `__import__` 正常）
- 前端 TypeScript 类型检查通过（`npx tsc -p tsconfig.json --noEmit`，0 错误）

## [2.2.6] - 2026-08-07

### 变更

- `AGENTS.md` 演示账号清单从单行简表扩展为江南大学 + 复旦大学 + 浙江大学完整三校清单，与 `backend/scripts/seed_data.py` 中 `JIANGNAN_USERS` / `FUDAN_USERS` / `ZJU_USERS` 三组常量对齐；标注各校已 `campus_verified=True` 的用户编号，并明确 `@momentcampus.com` 为平台运营专用域名（不受学校 `domain`/`addl_domains` 校验，不参与校园身份认证）
- `backend/tests/manual/` 7 个手动验证脚本（verify_comments / verify_e2e_extra / verify_governance / verify_notifications / verify_profile / verify_subscription_fix / verify_subscription_flow）中 15 处 `login("user1~3@example.com")` 统一替换为 `login("user1~3@example.jiangnan.edu.cn")`，避免使用与 seed 不一致的旧邮箱，7 个脚本 `py_compile` 语法编译全部通过

### 前端

- `Header.tsx`：移除学校切换按钮（桌面端 + 移动端两处 `<SchoolSwitcher />`），简化页头布局并避免切换入口与"一对一绑定"设计割裂
- `MapPage.tsx`：地图地点侧滑面板（`<aside>`）改为评价可点击展开/收起查看完整评价列表；内嵌评分表单（5 星点击 + 500 字可选正文 + 提交/撤回 + 未认证 `VerifyGate` 门禁）；打开面板时并行拉取 reviews + my_review + detail；提交/撤回后自动回写 `avg_score` / `rating_count` / `review_count`；与 `LocationPage` 表现一致；**评分表单常态防误触**：已有评价时常态只显示我已提交的只读摘要卡片 + 「更新评价」按钮，点击后才展开星星编辑器 + 文本框 + 撤回/取消编辑/更新按钮，避免常态裸露编辑器误点；**布局紧凑化**：常态卡片从「外层 border + 内层 bg-mist 嵌套 + 标题/按钮两行」重构为「单层 border 卡片，标题与更新按钮同排 + 我/认证/星级/评分横向 1px 竖线合并 + 正文直接平铺」，padding p-3 → p-2.5；**未评价/编辑态与常态彻底统一**：主按钮（提交/更新）移到顶行右侧与标题同排对齐，仅次按钮（取消编辑/撤回）放在底部，主按钮统一 h-8 px-3 text-[11px] rounded-[8px]
- `LocationPage.tsx`：在地点列表容器上方新增搜索框（bg-paper 卡片 + Search 图标 + 一键清除），前端按「名称/描述/楼栋/楼层」四字段过滤，无匹配时 EmptyState 友好提示；评分表单**常态防误触**同步改：已有评价时常态只读摘要卡片 + 「更新评价」按钮展开编辑态；新增 `editingReview` 状态，提交/撤回/关闭详情/取消编辑 后自动重置为 false；**布局紧凑化**与 MapPage 同步：常态去掉内层 bg-mist 嵌套卡片，标题与更新按钮同排；padding p-4 → p-3.5；我/认证/星级/评分用 1px 竖线横向合并；**未评价/编辑态与常态彻底统一**：主按钮（提交评价/更新评价）移到顶行右侧与标题同排对齐，仅次按钮（取消编辑/撤回评价）放底部，主按钮统一 h-[34px] px-3.5 text-[12px] rounded-[9px]
- `ProfilePage.tsx`：移除已废弃的 `<SubscriptionsCard />` 订阅模块卡片与对应 import，避免展示不存在的订阅功能造成用户困惑
- `PostForm.tsx`：发布页新增地点交互重做——地点下拉新增独立选项「✚ 新增地点（地图选点，提交后进入核验队列）」（value=`__new__`）；下方虚线边框整块（含新地点名称、地图选点按钮、已选坐标显示）改为「只在选中『新增地点』时才显示」，默认隐藏不再裸露；删除「纬度（GCJ-02）/ 经度（GCJ-02）」两个手填输入框，改为「在地图上选择位置 / 重新选点」按钮统一触发 MapLocationPicker 弹窗；选点后用 2 枚只读 chip 徽章（圆角 8px + 地图图标 + GCJ-02 经纬度保留 4 位小数）展示坐标；未选点时显示虚线占位提示「尚未选点 —— 请点击右上角『在地图上选择位置』完成选点」；validate() 校验改为「新增地点请填写名称 / 请先在地图上选好位置」；submit 创建地点分支的判定从「三件套非空」改为「isNewLocationSelected 且三件套齐备」，与 UI 状态严格对应；同时兼容 MapPage 侧滑发帖面板（variant='panel'）通过 `defaultLocationLat/Lng/Name` 传入的地图点选坐标——这些情况下即使未显式切换下拉，也视为进入「新增地点」模式，虚线 div 自动出现并预填 name + chip 展示坐标；**Bugfix：引入显式 `newLocationMode` 状态**，解决「下拉选新增地点但字段为空时立刻跳回空值显示，像选不中」的受控值回退问题；`handleLocationSelect`、草稿恢复（handleRestoreDraft）、切校清理、编辑模式回读（getPost）四处同步维护该状态
- `index.css` + 全站 `<select>`：**全局原生 select 外框统一美化**——新增两档通用工具类 `.select-nice`（40px / 圆角 10px / 纸面白底 / 内嵌 SVG ChevronDown 替换默认箭头 / 湖蓝 focus ring / hover 边框加深 / disabled 灰显）与 `.select-nice-sm`（紧凑 36px / 圆角 8px，供 admin 列表筛选）；覆盖 PostForm 2 处（地点/失物类型）、LocationPage 1 处、SearchPage 筛选区 3 处、admin 后台 8 处（ActivationFunnel / AdminLogs / AdminTopics / Analytics / PlatformOverview / PlatformPlans 3 / PlatformSchools / SchoolImport）共 14+ 原生 select；**明确放弃自定义展开面板方案**（因原生 `<option>` 弹窗由 OS 渲染，CSS 无法覆盖，经评估改造成本与收益不匹配后回滚，仅保留外框美化）
- `routes.tsx` + `Sidebar.tsx` + `MobileNav.tsx`：**地图升级为主页**——导航顺序从「首页→地图→地点…」改为「地图→首页→地点…」；默认路由 `/` 改为 `<Navigate to="/map" replace />` 重定向，原 HomePage 改挂 `/home`；Sidebar 顶部 Logo 方块 `to="/map"`（不再 `/`）；`commonRouteLoaders` 预加载顺序 `loadMapPage` 移至首位（用户最常打开的页面优先准备）
- `Header.tsx`：**页头新增当前学校名称徽章**——Logo「此刻校园」右侧新增 ≥sm 可见的学校徽章（`School` 图标 + 校名，`bg-lake/8` 浅湖蓝底胶囊 + `text-lake` 湖蓝字 + 1px 湖蓝描边）；数据取自 `useCampusStore().currentSchoolName`，未选校/游客态 `&&` 短路不渲染；避免旧 `<SchoolSwitcher />` 移除后用户「不知道自己在看哪个学校」的上下文缺失问题
- `PostDetailPage.tsx`：**修复点击证实/证伪后整页闪一下的感知 Bug**——原 `handleValidate()` 成功后 `void loadPost(true)` 会在 `loadPost` 里触发 `setLoading(true)`，进而命中 L391 `if (loading) return <LoadingState />` 整页骨架屏 Early Return，用户感知为「页面重新加载」；修复方案：给 `loadPost()` 新增第 2 参 `silent=false`（为 true 时跳过 `setLoading` 切换），`handleValidate()` 改为 `loadPost(true, true)` 静默刷新 governance 数据；首屏加载 / ErrorState onRetry 仍保持 `silent=false`（需显示骨架屏加载态）
- `Sidebar.tsx` + `MobileNav.tsx`：**「首页」菜单项重命名为「帖子」**——因地图已升级为主页（`/` → `/map`），原首页 `/home`（帖子信息流 + 话题聚合页）继续叫「首页」语义歧义，改为更贴切的「帖子」；两处导航的 `path` 同步从 `/` 改为 `/home`，与 `routes.tsx` 路由定义保持一致，避免走 `/` → `/map` 的重定向链路

## [2.2.5] - 2026-08-06

### 修复

- `alembic`：消除重复 revision（`a1b2c3d4e5f6` 在两处迁移同时使用），把 `unify_edu_email_drop_campus_fields.py` 的 revision 改为 `m1n2o3p4q5r6`，并新增 `n2o3p4q5r6s7_merge_drop_publisher_and_location_knowledge.py` 作为唯一 merge head，`alembic heads` 输出单 head
- `location_summary`：修复 `GET /api/v1/locations/{id}/summary` 手动录入简化格式触发的 500 错误；新增 `_normalize_claim()` / `_normalize_conflict()` 兼容简化 `{type,value,confidence,sources}` 与原生 `{claim_id,text,confidence_level,source_refs}` 两种 claim 结构；`load_summary_sources()` 对 `source_refs_json` 中缺失 `source_type` / `source_id` 的引用做合法性过滤，避免 `KeyError: 'source_type'`
- `CORS`：在 `app/config.py` 与 `.env.opengauss` 中补充 `http://127.0.0.1:5173/5174/5175` 允许源，修复前端使用 `127.0.0.1` 访问时的跨域预检失败

### 测试

- 新增 `tests/test_location_summary_flow.py` 8 项地点摘要主链路集成测试（Scenario A~H：生成待审、批准回写、驳回、证据不足、跨租户隔离、冲突、来源哈希去重、管理员刷新标记）
- 全量 `pytest tests/ -v` 拆分为 auth/users/schools/posts/location/others 5 批次在本地环境依次执行，合计约 1021 项全部通过；原 10 分钟单次窗口超时问题在分批策略下解除
- Web 7 步真实 E2E（browser_use + integrated_browser）7/7 通过：登录、管理员跳转后台、地图渲染、图书馆 AI「此刻摘要」展示、网络层无 4xx/5xx + API 返回 `approved`、管理员审核队列空状态、普通用户登录后摘要可见

### 验证

- 小程序 wechatide-skill：`check_wechatide_status` 通过（登录未过期），`simulator_refresh` 编译通过，`simulator_open_page` 成功导航 `pages/map/map` 与 `subpackages/pages/locations/locations?id=5`；静态走查确认 `locations.wxml:117-133` / `locations.ts:129` / `locations.wxss:268-335` AI 摘要板块完整接入

## [2.2.4] - 2026-08-06

### 变更

- 新增 AI 地点摘要实施方案中文任务报告，真实记录专项测试、全量测试超时、Alembic 图和 E2E 阻塞
- 更新 `TODO.md` 验收状态，区分已通过的 Web/小程序静态门禁与待完成的全量回归/真实试点

## [2.2.3] - 2026-08-06

### 变更

- 清理新手引导中的旧 `handleGoNearby` 命名，并将历史 TODO 方案明确标注为已废弃
- 将附近回归测试改为接口不可访问边界测试，演示检查脚本改用有效的最近发布排序

## [2.2.0] - 2026-08-06

### 新增

- `location_knowledge`：地点稳定资料提议、管理员审核、AI 地点摘要版本、来源卡片和摘要审核接口
- `location_summary_worker`：按来源快照异步生成待审核摘要，失败时保留最近一次已批准版本
- Web/小程序地点详情展示稳定资料、AI“此刻摘要”、冲突与证据不足状态，并提供认证用户资料提议入口

### 变更

- 地点摘要引入 7 天动态帖子、30 天评价、双用户证据门槛、虚构来源拒绝和服务端可信层级计算
- 删除实时定位、距离字段、Haversine/`/locations/nearby` 和 `nearest` 产品入口，保留静态校园地图与地点坐标
- 重写评委反馈文档为六部分 AI 地点摘要内部实施方案，并标注历史方案废弃口径

## [2.2.1] - 2026-08-06

### 修复

- `Location.current_summary_id` 外键改为 `use_alter`，解除地点与摘要版本的循环依赖，避免 openGauss 测试清理时先删学校导致外键错误

### 运维

- 新增地点摘要 worker 的 systemd service/timer，并接入安装、更新和混合部署脚本

## [2.2.2] - 2026-08-06

### 测试

- 新增地点资料提议审核、摘要证据门槛、虚构来源拒绝和来源快照稳定性测试；专项测试 5 项通过
- 修正摘要来源归一化逻辑，证据不足的结论不会把来源计入公开来源集合

## [2.1.12] - 2026-08-06

### 变更

- `auth` **统一教育邮箱**：登录邮箱 = 教育邮箱 = 认证邮箱（同一字段 `email`），消除"登录邮箱 ≠ 认证邮箱"的割裂体验。删除 `users.campus_email`、`users.student_id` 字段（Alembic 迁移 `a1b2c3d4e5f6`），认证改为向当前登录邮箱发码验证，无需单独提交学号/认证邮箱
- `auth` 校园认证接口收敛：`POST /users/me/verify-campus/send` 去掉 `student_id`/`campus_email` 入参，直接用登录邮箱校验域名并发码；`confirm` 同理仅需 `token`/`code`
- `auth` 演示账号改为教育邮箱并加 example 域名：`user1@example.jiangnan.edu.cn`（fudan→`example.fudan.edu.cn`、zju→`example.zju.edu.cn`），各校 `addl_domains` 追加 example 域使演示账号能过域名校验但 example 域不会真实发邮
- `web` 注册页收窄为教育邮箱：邮箱域名须命中目标学校允许域名，否则提示"请使用学校官方邮箱注册"；`CampusVerifyCard` 移除学号输入框，认证邮箱只读展示当前登录邮箱
- `miniprogram` 我的页校园认证 UI 收敛：移除学号/校园邮箱输入框，改为只读展示登录邮箱 + "向我的邮箱发送验证码"，与 Web 端一致；注册模式邮箱保持选填（微信首登可先建号，认证时要求教育邮箱）

## [2.1.11] - 2026-08-06

### 移除

- 移除小程序和 Web 用户可见的内容订阅入口、订阅服务、订阅偏好开关和相关死代码；保留后端兼容接口与平台商业订阅管理。

- `miniprogram` 从 `app.json` 路由注册中移除 `pages/topics/topics` 与分包 `topic-detail/topic-detail` 两个专题页；同步删除首页 `home.wxml` 专题入口按钮与对应样式、`goToTopics` 方法，满足用户"早就说已经删除了专题和收藏功能"的要求（订阅管理 bookmark 图标属正常订阅功能，予以保留）

### 变更

- `miniprogram(tabbar)` 底部 tabBar 由原生样式升级为自定义 `custom-tab-bar` 组件：深湖蓝浮动胶囊底色 + 毛玻璃 backdrop-filter + 柔阴影 + 安全区适配，发布按钮高亮为橙色圆形主操作；五个 tab 页 `onShow` 时同步 selected 索引修复高亮不同步
- `miniprogram(avatar)` 新增 `resolveAvatar()` 与 `defaultAvatar()` 默认头像工具，使用内联 SVG data:image（蓝灰渐变圆形 + 白色人形剪影）替代不存在的 `/assets/default-avatar.png`；覆盖 `post-card`、`profile`、`post-detail`、`search` 四页的作者/评论作者头像显示

## [2.1.10] - 2026-08-06

### 新增

- `map` 地图页统一地点数据源：发帖地点与评分地点同为 `locations` 表，地图页只渲染「带评分的地点标记」，移除「附近」按钮与帖子标记（小水滴），信息全部集成在每个地点上——点击地点打开面板展示评分/描述/楼层与相关帖子（`GET /posts?location_id=`）
- `miniprogram` 小程序正式版 M2 功能完善：新增 `components/empty-state`、`components/skeleton` 空态/骨架屏组件；新增 `utils/auth-guard.ts`（`requireLogin` 写操作引导 + `guardPageLogin` 页面守卫）；新增 `subpackages/pages/about` 关于页（品牌展示、版本号、检查更新）；`subpackages/sub-pages.json` 分包 5 个低频页面
- `miniprogram` 小程序正式版 M3 性能优化：`components/post-card` 图片 `lazy-load`；新增 `utils/cache.ts` 按 schoolCode 分区 10 分钟缓存；`app.ts` 启动时 auth/campus store 首屏预恢复
- `miniprogram` 小程序正式版 M4 兼容性：`app.wxss` iOS 安全区 `.safe-bottom-*` 适配；老基础库 `wx.getUpdateManager` 类型保护
- `miniprogram` 小程序正式版 M5 安全加固：上传前 5MB 大小 + jpg/png/gif 格式 + 5 张数三重预检；Token 存储用 `wx.setStorageSync` 隔离沙盒 + 请求日志脱敏；发布二次确认；举报 6 种 Reason 枚举对齐后端 enums
- `miniprogram` 小程序正式版 Task 14 测试脚本：新增 `scripts/test-format.mjs` formatCount/truncateText/formatDate/getRemainingTime 单测；`typings/global.d.ts` 补齐 `URLSearchParams` 类型声明
- `feedback` 用户反馈模块（前后端）：后端 `feedback.py` 路由 + `feedback` 模型 + schema + Alembic 迁移 `f4b5c6d7a8b9_fdb_01_feedbacks.py`；前端 `AdminFeedbackPage.tsx` 管理端处理页；小程序 `services/feedback.ts`
- `miniprogram` 小程序分包：`miniprogram/subpackages/pages/about/about.*` 关于页 4 件套

### 变更

- `map` 增强 `GET /locations` 返回评分汇总（avg_score/rating_count/review_count/post_count），前端新增 `locationsApi.getLocations()` 复用，地图页与地点页共用同一份地点数据
- `rev` 地点页（/locations）移除定位按钮、半径筛选与距离显示，改为展示学校全部地点（看评分做选择）
- `home` 移除首页「附近好去处」区块，不再显示「几公里内」与距离
- `auth` 为江南大学补充允许的校园邮箱域名 `stu.jiangnan.edu.cn`（seed 支持 `addl_domains` 多域名写入），使 `@stu.jiangnan.edu.cn` 教育邮箱可通过校园身份认证
- `auth` 配置 QQ 邮箱 SMTP（smtp.qq.com:465，授权码存 `.env.opengauss` 不进 Git），实测向 `1030424433@stu.jiangnan.edu.cn` 成功发送验证邮件
- `miniprogram(app)` `app.ts` 移除 `onLaunch/onShow` 强制登录跳转，游客可直接浏览首页/地图/搜索/详情/专题/地点
- `miniprogram(request)` `services/request.ts` 401 分支分场景处理：游客场景（无 refreshToken）401 只抛异常不 `reLaunch` 跳登录，由页面调用方 `try/catch` 静默；登录过期场景才清 Token 并跳转
- `miniprogram(publish)` `pages/publish/publish.ts` 新增 `onShow` 守卫（`guardPageLogin('请先登录后再发布帖子')`），避免游客填半天表单才发现不能发布
- `miniprogram(auth)` 登录页新增「以游客身份继续浏览」链接入口
- `miniprogram(upload)` `services/upload.ts` 上传 URL 从硬编码 `http://localhost:8000/api/v1/uploads` 改为 `${BASE_URL}/upload/image` 与后端路由一致
- `miniprogram(ts)` `typings/types/wx/lib.wx.app.d.ts` 修复 `GetApp<T>` 泛型约束：由 `<T = IAnyObject>` 改为 `<T extends IAnyObject = IAnyObject>`，解决 TypeScript 编译错误
- `miniprogram(notifications)` `pages/notifications` onShow `guardPageLogin('请先登录后查看通知')` 守卫生效
- `miniprogram(profile)` `pages/profile` onShow 守卫生效 + 关于页入口
- `miniprogram(post-detail)` 点赞/验证/举报/评论 4 种写操作统一 `requireLogin(具体文案)`，双按钮（再看看 / 去登录）给用户选择权

## [2.1.9] - 2026-08-06

### 新增

- `UC-01` 用户-学校严格一对一绑定：`school_memberships` 新增部分唯一索引 `idx_membership_user_active`，一个用户同一时刻只能有 1 个 active membership；`POST /schools/join` 语义升级为"切校"（leave old + join new 原子操作）；super_admin 保留跨校静默切换特权（platform 管理需要）
- `UC-02` 教育邮箱验证系统：后端 `email_service.py` 接入 SMTP（SSL，支持 `smtp.qq.com` 等主流服务商，授权码经环境变量 `SMTP_*` 注入）；`school_domains` 后台管理端点（`GET/PUT/POST /admin/school-domains`）支持管理员配置学校邮箱后缀；`/verify-campus/send` 返回 `verify_link` 供 SMTP 未配置时的 dev 模式使用；verify 凭据支持双通道（6 位验证码或 24 位 token 哈希），token 落地页 `/verify-campus?token=xxx` 自动跳转个人中心完成认证
- `UC-03` 学校切换功能：个人中心新增"切换学校"浮窗 `SwitchSchoolModal`（搜索学校→后果确认→执行切换）；切校后 `school_switch.py` 原子执行：原校 membership 置 inactive + 新校 membership 建/激活 + 重置 `campus_verified=false` + 清空 student_id/campus_email + 将原校 posts/comments/location_reviews 匿名化为「已离校用户」；SchoolSwitcher 普通用户选择未加入学校时打开切换浮窗
- `D-04` 地点页面与地图整合：`MapPage` 地图地点标记（MAP_LOCATION_LAYER_ID）点击弹出地点侧面板，展示地点名称/类别/评分/评价数/距离，并并行拉取该地点相关帖子（`GET /posts?location_id=`，最多 5 条），可跳转地点详情页；保留 `/locations` 独立页面并支持深链 `?location={id}` 自动打开对应地点详情
- `D4-gate` 未认证用户只读门禁：后端所有写入端点（发帖/评论/点赞/证实/证伪/举报/评分/订阅/回复）统一加 `require_campus_verified()` 依赖，返回 403；前端 `VerifyGate` 组件提供大卡/紧凑两种门禁模式；发布页/评论区/评分区均由 VerifyGate 包裹；PostDetailPage 点赞/协同验证/举报/回复按钮仅对已认证用户渲染；未认证已登录用户有明显"去认证"引导
- `UX` 认证链接落地页 `/verify-campus`：读取 URL `token` 参数存 sessionStorage 后重定向个人中心，CampusVerifyCard 自动读取 token 完成确认

### 变更

- `perf(ui)` 修复 PostDetailPage 未认证已登录用户可见点赞/协同验证/举报/回复按钮的遗漏（补充 `canInteract = isAuthenticated && campusVerified` 判断）
- `fix(schema)` CampusVerifyConfirmRequest.code 字段长度由 6 放宽到 128，以支持 24 位 token 凭据（此前 token 提交返回 422）
- `test` 测试 fixture 全面适配 UC-01 一对一约束：普通用户仅保留 1 个 active membership（通过 super_admin 测试多校场景）；默认 fixture 用户标记 `campus_verified=True`（D4 门禁默认放行，未认证场景由 `test_campus_gate.py` 专项覆盖）
- `test` 新增 `test_campus_gate.py` 覆盖未认证写入 403 场景
- `fix(ui)` LocationPage 挂载 effect 读取 useCallback 定义的 openDetail 顺序导致的 `react-hooks/immutability` 警告，将 effect 移到 openDetail 定义之后；set-state-in-effect 警告统一用 `Promise.resolve().then(...)` 包裹
- `chore(config)` config.py 新增 SMTP 配置字段（SMTP_HOST/PORT/USER/PASSWORD/USE_SSL/FROM_EMAIL/FROM_NAME）+ APP_BASE_URL 用于构造 verify_link

## [2.1.8] - 2026-08-06

### 新增

- `auth` 新增校园身份认证能力（B-01/B-02）：`User` 增 campus_verified/student_id/campus_email/campus_verified_at；新建 `campus_verify_tokens` 表（一次性、限时、哈希存储）；`POST /users/me/verify-campus/send` 提交学号+校园邮箱并校验域名命中 `school_domains`，`POST /users/me/verify-campus/confirm` 校验验证码后置为已认证；`GET /users/me` 返回 campus_verified
- `auth` 帖子/评论/评价作者信息（author）新增 `is_verified` 认证标识（B-03），前端可据此展示「已认证」徽标
- `auth` 前端 Web 校园身份认证（B-05）：新增 `VerifiedBadge` 已认证徽标组件与 `CampusVerifyCard` 认证流程卡片（学号+校园邮箱发送验证码→确认认证，dev 环境直接展示验证码）；个人中心接入认证入口，帖子/评论区作者昵称旁展示「已认证」徽标
- `rev` 小程序校园地点页（A-07）：新增 `pages/locations/locations`（附近地点列表按距离+半径筛选+星星评分；详情弹层含评分汇总/我的评价/全部评价，登录后可提交/更新/撤回评价）；地图页新增「帖子/附近」模式切换，附近地点渲染为带评分的 marker 并可跳详情；首页新增「校园地点·附近评分」入口；封装 `services/locations.ts`
- `auth` 小程序校园身份认证（B-06）：`pages/profile` 新增认证卡片（学号+校园邮箱发送验证码→确认认证，dev 展示验证码，成功切已认证态）；post-card / post-detail（帖子与评论）/ search / topic-detail 作者昵称旁「已认证」徽标；`services/auth.ts` 封装 send/confirm；is_verified 字段归一化对齐后端嵌套 author
- `seed` 演示数据 seed 支持校园认证域名（B-01）：为三校写入 `school_domains`（jiangnan.edu.cn / fudan.edu.cn / zju.edu.cn）
- `seed` 演示数据为部分用户标记校园身份认证（B-07）：`seed_users` 依据用户清单 `campus_verified` 标记，为已认证用户写入 campus_email（学校域名）/student_id/campus_verified_at，使前端与小程序展示「已认证」徽标（江南 8/10、复旦 3/5、浙大 3/5）
- `miniprogram` 小程序 API 指向公网 HTTPS（C-01）：`services/request.ts` API_HOST 设为 `https://campus.chaina1.com`，`resolveImageUrl` 统一把 `/uploads/` 相对路径解析到生产域名
- `docs` 新增小程序上线落地指引（C-02）：`docs/36_微信小程序上线落地指引.md` 覆盖合法域名配置、隐私保护指引、体验版发布与体验成员管理流程
- `docs` 定位与叙事打磨（D-01/D-02/D-03）：`00_project_overview` 新增「差异化优势（为什么学生会持续用）」三壁垒并更新产品边界；复赛方案 32/33 补充认证/附近评分/小程序已完成能力与证据；Demo作品帖、视频脚本、社媒文案同步补充附近探索/设施评分/校园认证/小程序场景
- `ui` 新用户引导突出附近/评分/认证价值（D-04）：`FirstUseGuide.tsx` 第 3 步改为「三步开启校园生活」价值入口，可直达附近地点与校园认证页面
- `test` 同步 AI 混合排序权重测试断言（Q-01）：`test_t7_vector_search.py` 断言由过时权重 0.35/0.25/0.20/0.20 改为与实现一致的 0.5/0.15/0.15/0.20（期望分 0.825）
- `fix(ui)` 消除 `LocationPage.tsx` set-state-in-effect lint warning（Q-02），使 `npm run lint` 零错误零警告
- `fix(ops)` E2E 走查发现 `school_domains` 表为空导致「校园邮箱域名不匹配」（Q-03）：重新执行 `seed_data.py` 填充三校域名与 `campus_verified` 标记后，地点评分/地图附近/校园认证/作者徽标链路全部验证通过

## [2.1.7] - 2026-08-05

### 新增

- `rev` 新增地点评分/评价能力（REV-01）：`location_reviews` 表 + `locations` 评分汇总字段（avg_score/rating_count/review_count），每地点每用户一条可改可撤回
- `rev` 新增地点 API（`/locations`）：地点详情含评分汇总与"我的评价"、评价提交/更新/撤回、评价分页列表
- `rev` 新增"附近地点"接口 `GET /locations/nearby`：Haversine 距离升序 + 半径过滤 + 距离字段，多租户隔离
- `rev` 作者简明信息（UserBrief）新增 `is_verified` 认证标识字段
- `rev` 前端 Web 新增校园地点页 `/locations`（A-05）：附近地点列表（GPS/校园中心定位 + 半径筛选 + 距离与评分展示）+ 详情 Modal（评分汇总、评价列表、提交/更新/撤回评价），侧边栏新增「地点」入口
- `rev` 前端 Web 地图页新增「附近」模式（A-06）：切换后渲染带评分徽标的地点标记（水滴内显 avg_score，未评分显「新」），点击弹出地点侧滑面板（评分/距离/评价数 + 跳转评价页），学校切换自动重拉；首页新增「附近好去处」区块（定位 + 评分卡片横向滚动 + 查看全部）
- `rev` 演示数据 seed 新增地点评分/评价（A-08）：`seed_location_reviews` 按地点类型差异化评分倾向生成真实感评价，回写 avg_score/rating_count/review_count；实测生成 157 条评价覆盖 39 地点

### 变更

- `ai` 移除 AI 发布建议校验中 `summary` 必填约束，避免模型未生成摘要时校验失败
- `deploy` 新增华为云 Nginx 部署配置 `deploy/nginx-moment.conf`：HTTP→HTTPS 跳转、Gzip 预压缩、静态资源永久缓存、SPA 路由与 API 代理

## [2.1.6] - 2026-08-03

### 新增

- `video` 为 13 段旁白逐段配置独立情感指令（instruction）：痛点段紧迫、产品段沉稳、个人故事温暖感性、参赛宣言深情坚定，SDK 与 REST API 双通道均已接入
- `video` 新增社媒发布文案：适配哔哩哔哩、抖音、小红书三平台，含标题、正文、标签及发布策略建议；抖音标题以「VibeCoding大赏」开头，30字以内
- `video` 个人介绍视频旁白脚本全量改造：移除所有真人实拍要求，统一改为 AI 生图 + AI 视频 + 模拟截图 + 产品录屏，附 AI 生图提示词方向和完整素材清单
- `video` 作品演示视频旁白脚本新增"后台管理系统"段落（3:35-4:05）：数据总览、审核队列、数据分析、定时任务、操作日志录屏展示；TTS 脚本同步新增 demo_07_admin 段并更新全部段 ID；总时长从 4:10 延长至 4:45

### 变更

- `video` 修正 Qwen-Audio-3.0-TTS-Plus 旁白生成方案：脚本从纯 REST API 改为 DashScope SDK（WebSocket）优先 + REST API 回退双模式；修复中文引号导致 Python 语法错误；更新方案文档补充模型能力、指令控制、地域限制等信息

## [2.1.5] - 2026-08-02

### 变更

- `post` 修复新建帖子选择信息截止时间报错：前端 UTC 时区 ISO 字符串被 Pydantic 解析为带时区 datetime，asyncpg 无法插入 `TIMESTAMP WITHOUT TIME ZONE` 列；`PostCreate` 和 `PostUpdate` 的 `expire_at` 字段添加 `field_validator` 统一转为北京时间 naive datetime
- `ai_search` 混合排序权重调整：语义相似度 35% → **50%**，新鲜度 25% → 15%，验证数 20% → 15%，关键词相关度保持 20%（提升语义/向量检索主导地位）

## [2.1.4] - 2026-08-02

### 仓库全面整理与优化

- 全量梳理仓库文件：移除误提交的小程序 AI 工具链产物（`miniprogram/.ai-mode-skills/`、`miniprogram/cli-agent-run/`）、一次性图标生成脚本 `miniprogram/components/icon/._gen.cjs`、含硬编码 JWT 的调试脚本 `AIwork/全链路API校验脚本.ps1`
- 解除跟踪（文件保留本地）：`miniprogram/project.private.config.json`（微信开发者工具私有配置）、`frontend/.env.development`
- `.gitignore` 新增规则：微信开发者工具私有配置、小程序 AI 工具链产物目录、`AIwork/*.ps1`，防止同类文件再次误提交
- 决策：**不重写 Git 历史**（历史上已删除的 E2E 截图等旧文件保留，总量约 1.15MB）
- 验证：前端 `npm run build` 通过；后端全量 `pytest` 983 passed（openGauss 环境，14min24s）

### 测试数据规模扩充：每校 500 帖 + 50 用户程序化生成

- 新增 `backend/scripts/generate_bulk_data.py`：程序化生成全新演示数据（清空现有数据后填充），复用 seed_data.py 的清库/学校/分类/地点/套餐基础设施
- 规模：每校 50 活跃用户（1 管理员 + 49 普通用户，含现有演示账号）、500 条有效帖子（published）+ 5 条 6 态样本
- 互动数据基于真实校园社区量级（幂律分布）：浏览数按热度分层（热门 5% / 中等 60% / 冷门 35%），点赞率 6%~15%，点赞:评论 ≈ 6:1，所有帖子 ≥1 条主题相关评论
- 真实填充 `likes` 表：帖子 `like_count` 与实际 `Like` 记录严格一致（此前 likes 表从未填充）
- 用户-帖子-评论-验证关联同校准确：跨校关联数为 0；帖子计数与明细 1500/1500 一致
- 已回填 1515 条帖子 embedding（512 维，0 失败）；后端关键测试 55 passed
- 生成方式：`$env:APP_ENV="opengauss"; python scripts/generate_bulk_data.py`（含清库），随后 `python scripts/generate_embeddings.py --batch-size 50`

### 华为云 v2.1.4 全量部署

- 全量部署 v2.1.4 到华为云 `campus.chaina1.com`：关停 `moment-backend` → 上传后端代码与前端 dist → 重置测试库（DROP/CREATE `moment_campus`）→ `alembic upgrade head`（head=`d5e6f7a8b9c1`）→ 大数据集填充（三校各 505 帖 / 50 用户，1515 帖 embedding 全部回填）
- 修复部署阻断 Bug：`alembic/versions/d5e6f7a8b9c1_remove_invitation_codes.py` 缺少 `from typing import Union` 导入导致 alembic 加载版本文件失败
- 服务器 `deploy/.env.prod` 与 `backend/.env.prod`/`.env.opengauss` 更新（新增 `EMBEDDING_*` 配置）；AI/Embedding Key 仅经服务器端内存注入，未落文档
- 验证：`/health`=ok、admin 登录、HTTPS 首页与 API、MCP 浏览器端到端 7 项全部 PASS

## [2.1.3] - 2026-08-02

### 修复：注册完成后进入系统误报"无该学校访问权限，已切换回 xxx"

- 现象：游客态浏览过其他学校（URL/store 残留如 `?school=fudan`）后再注册新账号，注册成功后进入系统弹出"您没有该学校的访问权限，已切换回 江南大学"
- 根因 1：注册成功后仅 `setCurrentSchool` 同步 store，URL 仍残留旧学校值，`useSchoolSync` 的 URL 监听器读到旧值反向覆盖当前学校，最终 `ensureValidSchool` 回退并弹提示
- 根因 2：`useSchoolSync` 登录态 effect 用 effect 闭包捕获的 `currentSchoolCode` 作为回退前后对比基准，注册瞬间存在渲染竞态，未真正回退也会误弹提示
- 修复：注册成功后立即同步改写 URL 的 `school` 参数（与 store 同一批次）；回退对比基准改为读取实时 store 值
- 验证：`npm run build` 通过；浏览器多次注册实测无权限提示消除

## [2.1.2] - 2026-08-02

### 修复：学校切换器加入新学校后误报"无该学校访问权限"

- 现象：注册单校账号后，通过页头学校切换器选择未加入学校时提示"您没有该学校的访问权限"，无法切换
- 根因：切换流程先调用 `joinSchool`（后端已创建 membership），但未刷新前端 store 的 memberships，随后 `useSwitchSchool` 用过期数据校验权限导致误拦截
- 修复：`SchoolSwitcher.handleSelect` 在 join 成功后重新拉取 `me/memberships` 并更新 store，再执行切换
- 验证：浏览器实测单校账号切换其他学校成功（申请加入 + 切换 + 学校上下文生效）；`npm run build` 通过

## [2.1.1] - 2026-08-02

### 删除邀请码 + 注册时自由选择学校

- 用户决策（2026-08-01）：注册不再需要邀请码，初始加入的学校由用户注册时下拉选择（不再默认绑定江南大学）
- 后端：删除 `SchoolInvitation` 模型与 `school_invitations` 表（迁移 `d5e6f7a8b9c1`），`register` 端点改为 `body.school_id` 优先、`X-School-Code` 头回退，注册成功自动创建所选学校 active membership（is_default=true）；`join` 端点移除邀请码校验直接加入；平台创建学校不再生成管理员邀请
- 前端：注册页移除邀请码输入框，新增"选择加入的学校"下拉（公开学校目录）；登录页移除邀请码消费逻辑；`schools.joinSchool` 移除邀请码参数
- 小程序：`emailRegister` 移除 `invite_code` 参数
- 测试：删除 9 个邀请码相关用例，新增注册无学校 400 / X-School-Code 回退 / body 优先用例；后端全量 `pytest` 983 passed
- 端到端验证：浏览器实测选择复旦大学注册 → 自动登录 → 首页学校上下文为复旦大学，全链路通过

## [2.1.0] - 2026-08-01

### 最终归档（v2.1.0）

- 遗留后端配套补齐：`GET /api/v1/search/hot-tags` 热门标签接口、`permissions.py` 协同验证端点注释对齐、`interaction.py` ValidationCreate/ValidationResponse 收敛为 2 类枚举（含 action/counts 字段）
- 新增微信身份体系迁移 `0898a6eeb570`：`user_auth_identities` / `auth_sessions` / `binding_tickets` 三表，支持小程序登录与邮箱密码多身份绑定
- `README.md`、`Demo 作品帖`、`AGENTS.md` 全量校对：协同验证收敛 2 类、自动过期定时器、DataVec 512 维混合检索、测试覆盖 987 后端 / 38 前端 E2E
- `docs/` 与 `docs/design/` 系统校对：34 份文档 + 7 份 ER 图 + 数据库表结构 xlsx 与现行契约对齐（6 态状态机、2 类验证、openGauss 7.0、三校多租户）
- `AIwork/` 归档 20+ 份任务报告与校验脚本（复赛冲刺 Web 完善、T7 向量检索、自动过期、Analytics 清理、pytest 治理、小程序 AI-Skills 等）
- 至此完成 v2.0.1 → v2.1.0 共 9 批次归档提交

## [2.0.8] - 2026-08-01

### 运维 SQL 与部署脚本收敛

- openGauss 运维 SQL 与现行数据库契约对齐：索引、物化视图、函数、触发器、分区、表空间、性能测试脚本全面修订
- 新增 `test_opengauss_sql_contract` 契约测试，校验 SQL 文件与迁移/ORM 模型一致性
- `deploy/` 安装/更新/混合部署脚本补充自动过期 systemd 单元安装与定时器启用
- 后端系统层修复与加固：auth 限流、upload 安全、db_compat 兼容补丁、main 启动收敛、`verify_data`/`generate_full_report` 数据校验脚本重构

## [2.0.7] - 2026-08-01

### 小程序 AI-Skills 校验与配置

- 新增 `miniprogram/skills/moment-campus`：14 个原子接口（listPosts/createPost/aiSearch/searchPosts/validatePost 等）+ request 工具 + mcp.json + SKILL.md，符合 `wx.modelContext` 规范
- `project.config.json` 开启 urlCheck=false、packOptions 纳入 skills 目录；`project.private.config.json` 关闭 urlCheck
- 归档小程序 AI 校验产物：`.ai-mode-skills/`（鉴权规范与探测）与 `cli-agent-run/`（运行报告与验证结果）

## [2.0.6] - 2026-08-01

### 后端 pytest 警告治理与测试清理

- 全量消除 `-W error` 下的 DeprecationWarning 等告警：`datetime.utcnow` 弃用、pytest-asyncio 等，新增 `test_deprecation_cleanup` 契约防回潮
- 移除已废弃的 `tests/integration/` 集成测试目录（tablespaces/indexes/materialized_views/partitions/stored_procedures/triggers 共 6 个测试 + conftest），高级 SQL 对象改由 SQL 契约测试覆盖
- 修复 / 同步 12 个既有测试文件（ai_publish、ai_search、config、posts、publish_flow、rel02、schemas、search、tenant_isolation、upload_security、post_detail、post_transition）
- 后端 `pytest tests -q -W error`：987 passed / 0 failed / 0 warnings

## [2.0.5] - 2026-08-01

### 前端统一状态组件与分类视觉

- 新增 `components/state/`（EmptyState / ErrorState / LoadingState / StateLayout）统一异常态与加载态，替换各页面手写占位
- 新增 `GlobalToast` 全局提示与 `utils/categoryVisual.ts`（`category.code` 稳定配色），切换学校时清理旧校分类、筛选值与地图标记
- 全量前端 lint 治理：0 error / 0 warning；`npm run build` 通过
- 新增 Playwright E2E：`state-components`、`admin-category-live-sync`、`validation-and-categories`；同步修复既有 `accessibility` / `business` 用例

## [2.0.4] - 2026-08-01

### T7 向量检索 384→512 维度改造

- Embedding 独立 OpenAI 兼容配置（阿里云百炼 DashScope `compatible-mode/v1`，模型 `qwen3.7-text-embedding`），`EMBEDDING_*` 配置项入 `.env.opengauss.example`；真实密钥仅存本地 `.env.opengauss`（不入库）
- `Post.embedding` 列 `vector(384)` → `vector(512)`：迁移 `b6c7d8e9f0a1`（ALTER 列类型 + 重建 HNSW 索引），配合 `a1b2c3d4e5f6` 历史迁移
- 新增 `app/services/embedding_service.py`（生成/构建 512 维向量文本、超时降级）与 `app/db_types.py` Vector 类型；`scripts/generate_embeddings.py` 回填脚本实测 90 条帖子全部回填成功
- 真实链路验证：同义查询（"打印店在哪里" vs "附近哪里有打印服务"）正确召回同一组打印店帖子；测试环境通过 conftest autouse fixture 完全隔离外部 Embedding 调用（消除代理连接泄漏 ResourceWarning）

## [2.0.3] - 2026-08-01

### 自动过期定时器 30 分钟周期统一

- 统一自动过期任务调度周期为 30 分钟（deploy/bare-metal/moment-expire-posts.service + .timer）
- `expire_posts` job 增强：running 记录超时租约回收（60 分钟），advisory lock 获取失败改为 fail-closed（禁止无锁执行）
- 手动触发/记录查询接口权限收紧为 super_admin 专属（`require_role(Role.SUPER_ADMIN)`）
- 新增 systemd 单元结构测试与过期任务回归测试

## [2.0.2] - 2026-08-01

### Analytics 运行时废弃清理

- 移除 Analytics 服务与接口中对已删除业务表（post_change_reports 等）的残留引用与文档说明
- 前端 AnalyticsPage / analytics.ts 同步移除废弃指标展示
- 新增契约测试 `test_analytics_removed_metrics_contract.py`，防止废弃指标回潮

## [2.0.1] - 2026-08-01

### 变更

- `.gitignore` 修复 `rubbish/` 目录未被正确忽略的问题，移除 17 个已跟踪的回收站文件，仅保留 `rubbish/README.md`
- `.gitignore` 新增部署临时文件忽略规则（`deploy/_*.zip`、`deploy/_*.tar.gz` 等）和 `!.env.opengauss.example` 例外规则
- `docs/` 系统性整理与校对：16 份核心设计文档全面修正，移除 PostType/Tag/Favorite 等已废弃实体引用，更新状态机为 6 态、协同验证为 5 类、数据库统一为 openGauss 7.0
- `AIwork/` 新增 TRAE 复赛项目审查与评分报告、复赛展示帖子、任务报告，完成 R-13 社区作品帖任务
- `AIwork/` 新增复赛待完善清单与评委视角评分，提取 13 项待完善点并制定实现规划，按"看帖/视频"与"实操"两种场景重打分（79.4 vs 68.8）
- `AIwork/` 新增复赛冲刺实施计划（基于用户决策），8 项任务：删除 3 类验证、自动过期、状态组件、分类对齐、租户隔离、测试清理、向量检索、文档更新
- `backend/scripts/test_vector.py` 验证脚本：确认 openGauss 7.0.0-RC3 原生支持 DataVec 向量引擎，无需升级数据库
- `miniprogram/` 修复 WXML 编译错误：`wx:elif`/`wx:else` 不能直接用于自定义组件（empty-state、icon），统一用 `<block>` 包裹；修复 `wx:else` 与 `wx:for` 同元素导致的 `wx:if not found` 错误
- `miniprogram/` 修复 TypeScript ES2020 语法兼容性：将 `?.` 可选链替换为 `obj && obj.prop`、`??` 空值合并替换为三元表达式（home.ts、profile.ts、post-detail.ts、school-select.ts、search.ts、services/request.ts）
- `miniprogram/` 修复 7 个页面 WXML 模板结构（profile、school-select、search、subscriptions、topics、notifications、post-detail），全部通过 `compile_wxml` 验证

### 治理模块清理与协同验证收敛（本批归档）

- 移除治理模块遗留代码：`app/api/governance.py`、`app/schemas/governance.py`、`frontend/src/pages/admin/AdminGovernancePage.tsx`、`frontend/src/services/governance.ts`、`tests/test_governance.py` 及 `router.py` 注册引用
- 协同验证收敛为 2 类（confirmation/refutation）：删除 legacy 别名兼容逻辑（valid/invalid），统计口径只计 confirmation + refutation
- 不允许用户为自己的帖子投票（新增 `ForbiddenException` 校验）
- 验证接口响应新增 `action`（created/removed/switched）、`current_validation_type`、`confirmation_count`/`refutation_count` 字段，切换类型改为原地更新而非删除重建
- 同步更新 enums、post schema、interactions 及 6 个相关测试文件

## \[2.0.0] - 2026-07-29

### 多轮测试问题修复

- 增强 `ProtectedRoute` 组件的 token 有效性检查，防止匿名用户访问 `/publish` 页面
- 修复协同治理报告 API 路径不匹配问题（前端从 `/admin/governance/reports` 改为 `/admin/reports`）
- 为浏览历史接口添加异常处理，防止 500 错误影响用户体验
- 更新 `react-router-dom` 至最新版本以修复已知安全漏洞
- 更新 API 文档，补充当前 19 个路由模块概览
- 更新项目概述文档，反映已实现的多租户/多学校切换功能

### 浏览量与举报表单修复

- 为 `GET /posts/{id}` 添加 `increment_view` 查询参数，防止点赞/评论/回复等操作虚增浏览量
- 重构点赞、评论、回复、验证的前端状态更新逻辑，使用 API 响应本地更新而非重新加载帖子
- 修复举报表单重复提交问题，添加防重复提交守卫
- 修复帖子详情页与列表预览页数据不一致问题

### 前端 E2E 基线维护

- 更新 axe、注册、AI 搜索、跨租户和平台 API 测试以匹配当前依赖与接口，完整 Playwright 恢复为 27 通过 / 1 个已下线能力跳过
- 为发布表单地点与失物类型下拉框补充关联 label，消除 axe `select-name` critical 违规

### AI 发布建议摘要修复

- 修复 `ai-suggest` 已解析摘要却在响应构造时硬编码为 `None` 的缺陷，恢复结构化 `summary` 建议

### MapLibre 原生 Marker 图层重写

- 地图页帖子点由 DOM `maplibregl.Marker` 重写为 GeoJSON source + symbol layer，与高德瓦片共用 WebGL canvas 和投影帧
- 保留水滴几何、分类色、单帖/聚合数量、hover、点击侧栏和深链接，并增加跨学校请求竞态保护
- 新增三校基准相对位移回归：第二食堂、本部食堂、西区食堂与同校其他点在 zoom 14/16/18 下使用同一投影变换；对齐 E2E 5/5 通过

### 地图 GCJ-02 契约与三校坐标校正

- 数据库/API/地图/导入统一使用 GCJ-02，浏览器 WGS-84 定位在前端转换后显示
- 建立三校 39 地点坐标目录，更新种子数据并新增保护式 openGauss 数据迁移
- 修正浙大紫金港中心与地点整体偏东约 4km 的数据问题，新增只读离群审计与目录回归测试

### MapLibre SVG Marker 几何对齐

- 废弃旋转方块与 X+Y 人工补偿，改用尖端位于 SVG 底部中心的无描边水滴路径
- hover 以底部中心为 transform origin，单帖/聚合 Marker 在 hover 与 zoom 14/16/18 下尖端误差均不超过 0.5px
- 新增 Playwright 几何矩阵回归测试，并修正旧报告对零圆角位置的错误推导

### 地图 Marker 尖端 X+Y 补偿修复

- `MapPage.tsx` 修正水滴形 marker 补偿公式：compensator div 从仅 Y 平移 `translate(0, -tipOffset)` 改为 X+Y 同时平移 `translate(-compX, -compY)`，消除视觉尖端相对 anchor:'bottom' 偏右 25px 的问题
- MCP 浏览器验证 3 个缩放级 10+ marker 偏移稳定（S=36 聚合 marker：dx≈7.5/dy≈-3.1；S=28 单帖 marker：dx≈5.8/dy≈-2.4），无 zoom 漂移
- `npm run build` 构建成功

### 地图缩放漂移彻底修复

- `MapPage.tsx` marker 容器添加 `transition: none` 内联样式 + Marker 构造参数 `subpixelPositioning: true`
- `index.css` 新增 `.maplibregl-marker` 与 `.maplibregl-canvas-container` 全局 CSS 覆盖，禁用所有 transition/animation
- `MapLocationPicker.tsx` Picker 组件 Marker 同步添加 `subpixelPositioning: true`
- MCP 浏览器 E2E 验证：13 个 marker 缩放前后位置稳定，39 个 DOM 元素 0 CSS transition 违规

### 阶段四+五：性能优化与质量收尾

- `P2-001` vite.config.ts 添加 manualChunks 拆分 maplibre-gl/react-vendor/icons，MapPage chunk 1043KB→16KB（97% 下降），index.js 307KB→128KB
- `P2-008` MapPage 瓦片源 OSM→高德栅格（4 个 webrd0{1-4}.is.autonavi.com 子域加速），国内可达性提升
- `P2-006` api.ts 401 并发刷新加锁：refreshPromise 单例 promise 复用，避免并发 401 多次消费 refresh\_token
- `P2-007` 新增 utils/logger.ts（dev 打印/prod 静默），48 处 console.\* 替换为 logger.\*（21 个文件）
- `P2-003` SearchPage HOT\_TAGS 改为多租户动态化：useMemo 从当前学校 categories 派生 top 8，fallback 到 FALLBACK\_HOT\_TAGS
- `P3-001` 删除 AdminTagsPage.tsx（602 行死代码）+ 4 个零引用 tag API + 3 个 tag 类型
- `P3-003` 新增 utils/date.ts 4 个函数（formatRelativeTime/formatDate/formatDateTime/formatShortDateTime），15 个文件的本地实现替换为导入
- `P3-004` 删除 3 对重复 API 定义：uploadApi.uploadAvatar / usersApi.getMyPosts / interactionsApi.transitionPost（零引用）
- `P3-006` nginx.conf 生产环境关闭 /docs 与 /openapi.json 对外暴露（return 404）
- `P3-007` CHANGELOG.md 补记阶段一/二/三/四/五全部变更
- `P3-008` docs/ 下 11 个文件 160+ 处 `file:///d:/Project/database-class/...` 旧盘符路径批量替换为相对路径
- `P3-011` frontend/README.md 由 Vite 模板默认文案替换为项目说明

### 阶段三：仓库卫生与部署配置

- `P2-009` 7 个 verify\_\*.py 调试脚本迁移到 backend/tests/manual/（git mv 保留历史），.gitignore 新增 `/verify_*.py` 规则
- `P2-010` 清理 backend/ 76 个 + 根目录 16 个调试脚本/日志（全部已被 .gitignore 覆盖）
- `P2-012` 新增 backend/.dockerignore 与 frontend/.dockerignore，排除 .git/.venv/node\_modules/tests/logs/.env 等
- `P2-011` deploy/.env.prod.example 与 backend/.env.example 同步补齐 9 项 AI\_\* 变量模板；backend/.env.example 修复 SQLite 残留改为 openGauss
- `P2-002` index.html title/description 移除江南大学硬编码，改为多租户通用文案
- `P2-005` ProfilePage 与 AdminDashboard 的 handleLogout 改为先 await authApi.logout() 后清本地 state

### 阶段二：多租户与代码质量

- `P1-002` MapPage 接入 useCampusStore 学校中心点 + 分类映射动态化（categoriesApi 拉取，CATEGORY\_COLORS/NAMES 保留 fallback）
- `P1-001` 确认收藏相关代码已彻底移除（前端无残留 UI/调用，后端无残留路由）
- `P1-004` 清零 ESLint 24 个 error（react-hooks/exhaustive-deps 等），保留 set-state-in-effect 为 warning（项目设计）
- `P2-013` auth.py:380 移除明文 reset\_token 日志，降级为 DEBUG 级别且只记 token 前 8 位

### 阶段一：紧急修复

- `P0-001` frontend/Dockerfile 补 `ARG VITE_API_BASE_URL=/api/v1` + `ENV VITE_API_BASE_URL=$VITE_API_BASE_URL`，修复生产构建 API 地址回退 localhost 的问题
- `P1-005` README/docs/27 物理模型描述修正（说明为课设交付物，实际部署仅 Alembic 索引）
- `P1-006` docs/12/13/22 头部增加「⚠️ 本文档已过时」声明
- `P2-014` AGENTS.md「演示学校唯一」更新为三校口径（江南为主，附带 fudan/zju）

## \[1.0.0] - 2026-07-04

### 变更

- `api/posts` 修复帖子列表/详情/创建/更新接口 author 字段返回问题（移除 alias="user"，手动映射 author，非匿名帖子正确显示作者昵称）
- `api/comments` 修复评论创建 500 错误（MissingGreenlet，添加 selectinload 预加载 replies）；修复评论/回复 author 字段返回
- `api/search` 修复搜索结果 author 字段名称不一致问题，content 返回完整内容
- `schemas/post` PostListResponse 补充 user\_id、is\_anonymous 字段；PostResponse/PostListResponse 移除 author 的 alias="user"
- `schemas/comment` CommentResponse 移除 author 的 alias="user"
- `schemas/user` 删除重复 LoginResponse 定义，改用 Pydantic v2 的 model\_config
- `frontend` 个人中心显示真实信誉分（reputation\_score），User 类型补充 reputation\_score 字段
- 信誉分系统完善：登录/个人信息接口正确返回 reputation\_score，发帖后信誉分正确触发存储过程更新
- 清理数据库测试垃圾数据（"123123"帖子及相关评论）
- `.gitignore` 添加 .trae/ 目录

## [0.1.0](https://github.com/yourusername/moment-campus/releases/tag/v0.1.0) - 2026-06-18

### 新增

- 完成第一阶段产品与技术规划文档（18 个核心文档）
- 项目总览与产品需求文档
- 用户角色与使用场景分析
- 功能范围与优先级定义（P0/P1/P2）
- 信息架构与导航设计
- 18 个核心用户流程设计
- 37 个页面规格说明（用户端 29 页 + 管理端 8 页）
- 12 个内容分类与字段设计
- 社区治理机制设计
- AI 能力规划与降级方案
- UI/UX 设计规范（颜色、字体、组件等）
- 技术架构设计（React + FastAPI + PostgreSQL）
- 数据库设计（21 个核心实体）
- API 接口规范（19 个模块，60+ 接口）
- 安全与隐私保护方案
- 测试策略与验收标准
- 9 阶段开发路线图
- 风险识别与应对措施
