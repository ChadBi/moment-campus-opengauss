# 任务报告：DeepSeek 地点摘要空响应修复

## 1. 任务概述

修复 `deepseek-v4-flash` 生成地点摘要时 HTTP 200 但 `message.content` 为空的问题。按用户要求仅验证有问题的 AI 摘要链路，不执行全量后端、前端或端到端测试。

## 2. 已完成内容

- 为 `AIInvokeOptions` 增加可选 `thinking` 控制项。
- 地点摘要固定关闭 DeepSeek V4 思考模式，保留 1500 tokens 和 60 秒超时。
- AI 搜索、辅助发布及非 DeepSeek Provider 保持原有行为。
- 空响应日志增加 response id、finish reason、输出/推理 token 和推理长度，不记录敏感正文。
- 完善 JSON 提取与额外字段剥离，兼容模型在 JSON 外增加说明或回显输入字段的情况。
- 使用真实南门地点数据完成一次 DeepSeek 请求并通过 JSON Schema 校验。

## 3. 未完成内容

暂无当前 AI 摘要问题的未完成项。按用户明确要求，未运行全量 pytest、前端构建、小程序编译或完整 E2E。

## 4. 实现思路

DeepSeek V4 默认启用思考模式，复杂地点数据可能在 1500 个输出 token 内只生成推理内容，尚未生成最终 JSON。Provider 通过 OpenAI SDK 的 `extra_body={"thinking":{"type":"disabled"}}` 仅关闭地点摘要的思考模式，避免改变其他 AI 场景。空响应时只记录诊断元数据，便于区分 token 截断、内容过滤和服务端资源问题。

## 5. 修改文件

- `backend/app/ai/provider.py`：思考模式参数、超时透传、空响应安全诊断和 JSON 提取兼容。
- `backend/app/ai/schemas.py`：递归剥离 Schema 未声明字段。
- `backend/app/services/location_summary.py`：精简快照与 prompt，并为地点摘要关闭思考模式。
- `backend/tests/test_ai_provider_unit.py`：DeepSeek 请求参数、场景隔离、日志安全与结构兼容测试。
- `backend/tests/test_location_summary_unit.py`：地点摘要 AI 调用选项测试。
- `TODO.md`、`CHANGELOG.md`：完成记录与版本变更说明。

## 6. 影响范围

仅影响 DeepSeek 地点摘要生成和 AI Provider 的内部诊断能力，不修改公开 HTTP API、数据库结构、Web 前端或小程序。AI 搜索和辅助发布未显式设置 `thinking`，继续沿用原行为。

## 7. 测试与验证

### AI 定向单元测试

```powershell
$env:DEBUG='false'
$env:APP_ENV='opengauss'
$env:TEST_DATABASE_URL='postgresql+asyncpg://gaussdb:***@localhost:5432/moment_campus_test'
.\.venv\Scripts\python.exe -m pytest tests/test_ai_provider_unit.py tests/test_location_summary_unit.py -v
```

结果：`26 passed in 5.98s`。覆盖 DeepSeek `thinking=disabled` 请求参数、其他 AI 场景不受影响、非 DeepSeek 忽略选项、空响应日志不泄露正文、JSON 额外字段剥离及地点摘要选项。

安全日志调整完成后又只复跑了本次核心 5 项：`TestDeepSeekThinkingMode` 4 项和地点摘要选项 1 项，结果 `5 passed in 3.97s`。

### 真实 DeepSeek 地点摘要

读取开发库现有南门地点快照，只发送一次外部请求并关闭重试，不写入摘要版本：

- prompt 长度：1663 字符；来源：2 条帖子、2 条评价。
- 返回内容：607 字符，非空。
- JSON Schema：通过，字段为 `summary_text/claims/conflicts`。
- 输出：2 条 claims、0 条 conflicts。
- token：输入 635、输出 221。
- 总执行时间约 7.7 秒。

### 已知的非本任务测试门禁

曾按原计划尝试附带运行地点摘要 Scenario A：AI Provider 与纯函数部分 25 项通过，但集成用例在 setup 阶段被旧 `two_school_users` fixture 阻断。该 fixture 仍使用旧邮箱注册请求，当前手机号注册契约要求 `phone/sms_code/password_confirm`，因此返回 422；测试体未运行，与本次 DeepSeek 修复无关。用户随后明确只需测试有问题的 AI 摘要，故未扩修该注册 fixture。

## 8. 后续建议

- 若再次出现空响应，优先根据新增日志检查 `finish_reason` 与 `reasoning_tokens`。
- 后续单独维护测试基础设施时，再迁移 `two_school_users` 到当前手机号注册契约；不要与本次 AI 修复混合处理。
