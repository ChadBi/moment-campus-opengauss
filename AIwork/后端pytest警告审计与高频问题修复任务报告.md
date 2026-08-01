# 任务报告：后端 pytest 警告审计与高频问题修复

## 1. 任务概述

审计 backend 全量 pytest 的 1799 条警告，按来源统计，并以 TDD 方式修复 UserBrief 字典序列化、datetime.utcnow、FastAPI on_event 与 Pydantic v1 Config 等高频真实问题。禁止通过 pytest 过滤隐藏警告，不修改小程序、TODO，不提交 Git。

## 2. 已完成内容

- 完成全量基线测试：957 passed，1799 warnings。
- 基线分类：datetime.utcnow 1446 条、UserBrief 字典序列化 331 条、同步测试误标 asyncio 16 条、FastAPI on_event 2 条、Pydantic class Config 1 条；pytest 汇总计数与逐类展开相差 3 条，未发现额外警告类型。
- 为 UserBrief 赋值校验、令牌时间生成、密码重置时间、FastAPI lifespan、Pydantic v2 Settings 配置新增回归测试。
- PostResponse 与 PostListResponse 启用赋值校验，使 author 字典赋值自动转换为 UserBrief，消除序列化类型不匹配。
- 令牌签发改用 timezone-aware UTC；密码重置沿用数据库当前 naive datetime 口径并改用 datetime.now()，消除 utcnow 弃用。
- FastAPI 启动事件迁移至 lifespan；Settings 迁移至 SettingsConfigDict。
- 修复高频问题后全量测试：962 passed，16 warnings；继续修正测试标记与图片文件句柄后，以 `-W error` 执行全量测试达到 962 passed、0 warnings。

## 3. 未完成内容

暂无。

## 4. 实现思路

先运行完整测试获得真实基线，再从 pytest warnings summary 按警告来源及每个测试文件的聚合计数还原分类。随后先添加会失败的回归断言，确认 UserBrief 字典赋值未校验、utcnow 仍触发弃用、Settings 仍有 v1 Config、FastAPI 仍注册 on_startup；再进行最小生产代码修改并依次运行相关测试和全量测试验证。

## 5. 修改文件

- backend/app/schemas/post.py
- backend/app/core/security.py
- backend/app/api/auth.py
- backend/app/config.py
- backend/app/main.py
- backend/tests/test_posts.py
- backend/tests/test_config.py
- backend/tests/test_deprecation_cleanup.py
- backend/tests/test_rel02_security.py
- backend/app/api/upload.py
- backend/tests/test_upload_security.py
- AIwork/后端pytest警告审计与高频问题修复任务报告.md

## 6. 影响范围

影响帖子列表与详情响应模型的运行时赋值校验、JWT access/refresh token 时间戳生成、密码重置后的 refresh token 失效时间、应用启动日志生命周期、Settings 配置声明、图片上传处理资源释放及安全测试标记。API 响应结构、数据库结构和业务状态机均未改变。

## 7. 测试与验证

- TDD 红灯检查：独立断言确认 UserBrief赋值校验=False、utcnow无弃用=False、Settings无v1 Config=False、FastAPI无on_startup=False。
- 相关测试：25 passed in 16.11s，0 warnings。
- 中间全量测试：962 passed，16 warnings in 813.34s。
- VS Code diagnostics：0 条。
- 修正 `test_rel02_security.py` 的 asyncio 标记后，该文件使用 `-W error` 为 28 passed。
- 首次全量 `-W error` 暴露 EXIF 上传测试和 Pillow 处理链未关闭文件句柄；修复生产与测试代码后，上传安全测试为 43 passed。
- 最终全量硬门禁：`python -m pytest tests -q -W error` 为 962 passed in 800.72s，0 warnings。
- Web 全量 E2E 已在综合任务中执行为 36 passed；本轮后端修复后没有再次改变 Web 代码。

## 8. 后续建议

持续在 CI 中使用 `-W error` 运行后端测试，防止框架弃用、序列化类型错误和资源泄漏重新退化为仅告警状态。
