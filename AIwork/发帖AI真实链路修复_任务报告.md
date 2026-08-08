# 任务报告：发帖 AI 真实链路修复

## 1. 任务概述

排查并修复发帖页面 AI 辅助在真实模型环境下偶发 JSON 解析失败、错误降级文案、上下文参数缺失和手机号重复识别为 QQ 号的问题。

## 2. 已完成内容

- 将发帖建议模型调用的 `max_tokens` 从 1200 提升至 2400，给推理模型保留输出结构化 JSON 的空间。
- 按 `publish_suggestion` 场景生成正确的降级提示，不再显示“已降级普通搜索”。
- 小程序 AI 请求补充分类、地点、联系方式、失物类型和信息截止时间。
- 模型未返回分类时保留用户已选分类；模型返回非法分类时继续执行当前学校白名单校验。
- 修复手机号被 QQ 号正则重复命中的问题。
- 增加发布场景降级文案和手机号检测回归断言。

## 3. 未完成内容

AI 搜索的历史帖子 embedding 回填和“查询向量存在、帖子向量为空”降级逻辑属于另一项问题，本次未修改。

## 4. 实现思路

真实模型使用推理 token，原发帖调用上限可能在输出 JSON 前耗尽，因此提高发帖专用输出上限。发布建议失败时仍保留确定性敏感信息检测，但使用发布场景专用提示。小程序发送当前表单上下文，后端不发送联系方式原文到模型，仅使用服务端规则检测敏感信息。

## 5. 修改文件

- `backend/app/ai/service.py`
- `backend/app/services/ai_publish.py`
- `backend/tests/test_ai_publish.py`
- `backend/tests/test_ai_provider.py`
- `miniprogram/services/posts.ts`
- `miniprogram/pages/publish/publish.ts`
- `TODO.md`
- `CHANGELOG.md`

## 6. 影响范围

影响后端 AI 发布建议、确定性敏感信息检测、小程序发帖 AI 请求参数和 AI 降级提示；不修改帖子创建、审核状态机或数据库结构。

## 7. 测试与验证

- 后端定向测试：`tests/test_ai_publish.py`、`tests/test_ai_provider.py`、`tests/test_ai_provider_unit.py`，52/52 通过。
- 小程序 `npm run typecheck` 通过。
- 小程序 `npm run test:format` 通过。
- 微信开发者工具发帖页 WXML 编译通过。
- 真实 8000 接口验证：`fallback=false`，结构化建议和优化标题正常返回；手机号仅命中 `phone`，未命中 `qq`。
- 未执行后端全量测试，符合当前任务约定。

## 8. 后续建议

- 为真实 provider 增加脱敏后的响应状态与 `finish_reason` 监控，区分 token 截断、空响应和 schema 校验失败。
- 单独修复 AI 搜索历史帖子的 embedding 回填与无向量关键词降级问题。
