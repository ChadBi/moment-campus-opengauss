# 任务报告：Qwen-Audio-TTS 旁白生成方案修正

## 1. 任务概述

用户计划使用 Qwen-Audio-3.0-TTS-Plus 模型（https://www.qianwenai.com/models/qwen-audio-3.0-tts-plus）为复赛演示视频和个人介绍视频生成 AI 旁白。此前已创建方案文档和生成脚本，但经核实发现 API 调用方式与官方文档不一致，需要修正为正确的 DashScope SDK 调用方式，并完善方案文档。

## 2. 已完成内容

### 脚本修正（`docs/video-assets/generate_narration.py`）

- **重写 API 调用方式**：从纯 REST API 改为双模式（SDK 优先 + REST API 回退）
  - 方式 A（默认）：DashScope SDK `SpeechSynthesizer`（WebSocket，输出 MP3）
  - 方式 B（备选）：HTTP REST API（返回 URL，输出 WAV）
- **修复语法错误**：中文文本中的直引号（`"`）导致 Python 字符串解析错误，替换为 Unicode 转义的中文引号（`\u201c` / `\u201d`）
- **修复 SDK 版本检查**：`dashscope.__version__` 属性不存在，改用 `importlib.metadata.version()` 获取版本号
- **添加 RPM 限流**：每段生成间隔 0.5 秒，避免超过 180 RPM 限制
- **语法验证通过**：`ast.parse` 确认无语法错误
- **启动验证通过**：脚本正确检测到 dashscope SDK 1.26.5，统计字数 1201 字，预估费用 ¥0.17

### 方案文档更新（`docs/video-assets/旁白生成方案.md`）

- **新增模型能力概览**：列出音质、指令控制、声音复刻、多语言、双协议等核心能力
- **修正调用方式**：从仅描述 REST API 改为同时介绍 SDK（WebSocket）和 REST API 两种方式
- **新增 SDK 代码示例**：基于模型页面官方代码，使用 `SpeechSynthesizer` 类
- **修正音色说明**：确认 `longanhuan_v3.6` 为 Qwen-Audio-TTS 系列系统音色
- **新增指令控制章节**：介绍模型支持的指令控制功能（语速、情绪、风格）
- **修正字数和费用估算**：从 720字/¥0.15 更新为 1201字/¥0.17
- **新增地域限制说明**：Qwen-Audio-TTS 仅在北京地域可用
- **新增文件清单**：列出方案涉及的所有文件

### 依赖安装

- 安装 `dashscope` SDK 1.26.5（含 aiohttp、websocket-client 等依赖）
- 验证 `from dashscope.audio.tts_v2 import SpeechSynthesizer` 导入正常
- 验证 `SpeechSynthesizer` 类可正常创建（需 API Key）

## 3. 未完成内容

- 实际生成旁白音频：需要用户提供有效的阿里云百炼 API Key（北京地域），设置 `$env:DASHSCOPE_API_KEY` 后运行脚本
- 音色试听：建议先用短文本测试 `longanhuan_v3.6` 音色效果
- 如 SDK 方式失败，需确认 REST API 端点是否需要 WorkspaceId

## 4. 实现思路

通过查阅 Qwen-Audio-3.0-TTS-Plus 模型页面（https://www.qianwenai.com/models/qwen-audio-3.0-tts-plus）和阿里云百炼官方文档（https://help.aliyun.com/zh/model-studio/non-realtime-tts-user-guide），发现该模型支持两种 API 调用方式：

1. **WebSocket SDK**（模型页推荐）：`dashscope.audio.tts_v2.SpeechSynthesizer`，返回音频字节
2. **HTTP REST API**（非实时）：`POST /api/v1/services/audio/tts/SpeechSynthesizer`，返回音频 URL

脚本采用双模式策略：优先使用 SDK（更简洁），失败后自动回退到 REST API（支持 WAV 格式）。这种方式确保在 SDK 出问题时仍可通过 HTTP 方式生成音频。

关键验证信息：
- 模型 `qwen-audio-3.0-tts-plus` 定价 ¥1.4/万字符，速率限制 180 RPM
- 仅在北京地域可用
- 支持指令控制（可用自然语言控制语速、情绪、风格）
- 音色 `longanhuan_v3.6` 已在官方文档示例中确认

## 5. 修改文件

- `docs/video-assets/generate_narration.py` — 重写 API 调用方式（SDK + REST API 双模式），修复中文引号语法错误，修复版本检查，添加限流逻辑
- `docs/video-assets/旁白生成方案.md` — 全面更新方案文档，新增模型能力概览、双调用方式说明、SDK 代码示例、指令控制章节，修正字数和费用估算

## 6. 影响范围

- 复赛演示视频制作流程
- 不涉及代码变更，不影响系统功能
- 新增 Python 依赖 `dashscope`（仅用于旁白生成，不影响项目运行环境）

## 7. 测试与验证

### 语法验证

- 使用 `ast.parse` 验证脚本语法，通过
- 修复 5 处中文引号导致的语法错误

### SDK 导入验证

- `import dashscope` 成功
- `from dashscope.audio.tts_v2 import SpeechSynthesizer` 成功
- `SpeechSynthesizer` 类可正常创建（需 API Key）

### 脚本启动验证

- 设置测试 API Key 后运行脚本
- 正确检测到 dashscope SDK 1.26.5
- 正确显示双调用方式
- 正确统计 9 段演示旁白（839字）+ 4 段个人旁白（362字）= 1201 字
- 预估费用 ¥0.17，与定价 ¥1.4/万字符一致

### 未运行测试说明

- 实际生成旁白需要用户提供有效的阿里云百炼 API Key（北京地域），本任务仅完成脚本编写和验证，未执行实际 TTS 调用

## 8. 后续建议

1. **获取 API Key**：前往 https://help.aliyun.com/zh/model-studio/get-api-key 获取北京地域的 API Key
2. **试听音色**：运行方案文档中 Step 3 的测试命令，试听 `longanhuan_v3.6` 音色效果
3. **批量生成**：确认音色后运行 `python docs\video-assets\generate_narration.py`，13 段音频约 1 分钟完成
4. **音色备选**：如不满意可尝试 `longanyang`（女声）等其他系统音色
5. **剪映对齐**：将生成的 MP3/WAV 文件导入剪映，按视频脚本时间段对齐画面和旁白
6. **指令控制**：如需更精细的情感表达，可研究 REST API 的 `instructions` 参数
