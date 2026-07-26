# 任务报告：E2E 测试 Bug 修复 — AI 搜索 Mock Provider 动态响应

## 1. 任务概述

在 E2E 自动化测试中发现：本地开发环境（`AI_PROVIDER=mock`）下，AI 智能搜索始终返回固定关键词「校园卡」相关的结果，无法根据用户实际输入动态生成响应，导致除"校园卡"外的任何查询都返回"未找到相关内容"。本任务修复该 Bug，使本地 mock 模式下 AI 搜索与发布建议功能可用，便于开发与演示。

## 2. 已完成内容

1. **Bug 复现与定位**：
   - 现象：以 `user1@example.com` 登录，访问 `/search?mode=ai` 输入"图书馆开放时间是什么时候？"，搜索结果为"未找到相关内容"；输入"食堂今天有什么菜？"同样无结果。
   - 根因：`backend/app/ai/provider.py` 的 `MockAIProvider` 在构造函数中硬编码了 `self._response`，固定返回 `keyword="校园卡"`、`category="失物招领"` 的意图 JSON，且 `_invoke` 方法每次都返回该固定串。任何不匹配"校园卡"的查询都无法检索到结果。

2. **MockAIProvider 改造**：
   - 新增 `_response_overridden` 标志位，区分"测试用 set_response 注入的固定响应"与"开发模式动态生成响应"。
   - 新增 `_extract_user_query(prompt)` 方法：从搜索意图 prompt 末尾的 `# 用户查询` 区块提取用户原始查询。
   - 新增 `_extract_publish_draft(prompt)` 方法：从发布建议 prompt 提取草稿原文（标题/正文）。
   - 新增 `_extract_first_noun(query, max_len=12)` 方法：基于停用词表与中文字符片段提取核心关键词，停用词表覆盖常见疑问词、停用词、时间词（"什么/怎么/今天/时候/时间/现在"等），避免把疑问/时间词当作关键词。
   - 新增 `_generate_dynamic_response(prompt)` 方法：根据 prompt 类型动态生成响应
     - 搜索意图 prompt（含"你是校园信息搜索助手"）：提取用户查询→抽取核心关键词→返回 `keyword=核心词、sort=relevance、reasons=按相关度排序匹配...`
     - 发布建议 prompt（含"你是校园信息发布助手"）：返回 `suggestions=null`（不修改原文，给出最小可用建议）
     - 其他：回退到固定响应 `self._response`
   - 改造 `_invoke`：响应选择优先级为 `set_response 注入 > 动态生成 > 固定默认`，确保测试用例通过 `set_response` 注入的固定响应仍被采用（测试断言不破坏）。
   - 将 `import re` 提升到模块顶部，避免在静态方法内部 import。

3. **回归测试验证**：
   - `tests/test_ai_provider_unit.py`：17 项全部 PASS（Mock Provider 正常调用、超时/限流/熔断降级、重试、JSON 解析失败等场景）。
   - `tests/test_ai_search.py`：21 项全部 PASS（成功场景、降级场景、overrides 覆盖、白名单校验、租户隔离、确定性打分、输入校验）。
   - `tests/test_ai_publish.py`：25 项全部 PASS（成功场景、降级场景、敏感信息检测、白名单校验、租户隔离、权限校验、缺失信息提示）。
   - 总计 63 项测试全部通过，无回归。

4. **前端 E2E 验证**：
   - 登录 `user1@example.com`，AI 搜索"图书馆开放时间是什么时候？"：返回 1 条结果（标题含"图书馆开放时间"），分数 0.xx，匹配理由"按相关度排序匹配「图书馆」的校园信息"。
   - AI 搜索"食堂今天有什么菜？"：返回 4 条结果（均含"食堂"相关），分数与匹配理由正常。
   - 两次搜索均无"降级""未找到"提示，Bug 完全修复。

## 3. 未完成内容

- 暂无。后续可继续测试评论、协同治理、专题订阅等其他模块。

## 4. 实现思路

- **测试与开发分离**：`set_response` 仍保留固定响应语义，供单元测试断言使用；动态生成仅在未注入固定响应时启用，确保开发环境可用且测试稳定。
- **关键词提取策略**：使用停用词表 + 中文片段提取，避免引入额外 NLP 依赖；停用词表覆盖常见疑问词与时间词，足以应对"图书馆开放时间是什么时候？""食堂今天有什么菜？"等典型查询。
- **安全约束保持**：动态生成仍走 `validate_structured_output` 的 JSON Schema 校验，输出格式与真实 OpenAI Provider 一致；不绕过白名单校验，不泄露其他学校数据（白名单仍由 `ai_search.py` 服务层校验）。
- **回退兜底**：当 prompt 无法识别（既不是搜索也不是发布建议）时，回退到原固定响应，保证向后兼容。

## 5. 修改文件

- `backend/app/ai/provider.py`：
  - 顶部新增 `import re`
  - `MockAIProvider` 类：新增 `_response_overridden` 标志位与 4 个方法（`_extract_user_query`、`_extract_publish_draft`、`_extract_first_noun`、`_generate_dynamic_response`）
  - `set_response` 方法：设置 `_response_overridden = True`，关闭动态生成
  - `_invoke` 方法：按"set_response 注入 > 动态生成 > 固定默认"优先级选择响应内容

## 6. 影响范围

- **本地开发环境**（`AI_PROVIDER=mock`）：AI 智能搜索与 AI 发布建议功能现在可用，能根据用户实际查询动态返回结果。
- **测试环境**：单元测试、集成测试不受影响（仍通过 `set_response` 注入固定响应做断言）。
- **生产环境**（`AI_PROVIDER=openai`）：不受影响（使用 `OpenAIProvider`，不经过 `MockAIProvider`）。
- **演示链路**：复赛 Demo 中"AI 智能搜索"链路打通，可演示不同查询返回不同结果与排序理由。

## 7. 测试与验证

1. **单元测试**（`pytest tests/test_ai_provider_unit.py tests/test_ai_search.py tests/test_ai_publish.py -v`）：
   - 63 项测试全部 PASS ✅
   - 覆盖 Mock Provider 正常调用、超时/限流/熔断降级、重试、JSON 解析失败、白名单校验、租户隔离、确定性打分、输入校验、敏感信息检测等场景

2. **前端浏览器验证**（integrated_code_mode 内联浏览器）：
   - 登录 `user1@example.com / pass123` 成功 ✅
   - AI 搜索"图书馆开放时间是什么时候？"返回 1 条相关结果，含分数与匹配理由 ✅
   - AI 搜索"食堂今天有什么菜？"返回 4 条相关结果，含分数与匹配理由 ✅
   - 两次搜索均无"降级""未找到"提示 ✅

3. **回归验证**：原有 63 项 AI 相关测试全部通过，未引入任何回归 ✅

## 8. 后续建议

1. 可扩展 `_extract_first_noun` 的停用词表，覆盖更多口语化表达（如"想找""帮我查"等）。
2. 可考虑在 `_generate_dynamic_response` 中识别"地图附近"类查询，自动填充 `map_bounds`。
3. 建议补充 `MockAIProvider._generate_dynamic_response` 的单元测试，覆盖搜索/发布/未知 prompt 三类场景。
4. 继续测试评论、协同治理（5 类验证）、专题订阅、个人中心等其他模块的 E2E 链路。
