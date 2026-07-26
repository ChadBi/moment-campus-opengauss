# 任务报告：后端API测试编写

## 1. 任务概述

为后端 FastAPI + SQLAlchemy (async SQLite) 项目编写完整的 API 测试，覆盖认证、帖子、互动三大模块。

## 2. 已完成内容

- 创建 `conftest.py` 测试配置，包含：
  - 内存 SQLite 异步测试数据库引擎
  - httpx AsyncClient 测试客户端 fixture
  - 每个测试前创建表、测试后清除表的 setup_database fixture
  - 测试学校、分类、帖子类型、测试用户、认证头、测试帖子、第二用户等 fixture
- 创建 `test_auth.py`（9 个测试）：
  - 注册成功、重复邮箱注册、登录成功、密码错误登录、不存在邮箱登录、Token 刷新成功、无效 Token 刷新、用 access_token 刷新（类型错误）、登出
- 创建 `test_posts.py`（14 个测试）：
  - 空列表、有数据列表、分页、帖子详情、浏览计数递增、帖子不存在、创建帖子（已认证/未认证）、带标签创建、更新帖子（所有者/非所有者）、帖子不存在更新、删除帖子（所有者/非所有者）、帖子不存在删除
- 创建 `test_interactions.py`（14 个测试）：
  - 点赞/取消点赞、未认证点赞、不存在帖子点赞、收藏/取消收藏、未认证收藏、不存在帖子收藏、有效性确认（valid/invalid/uncertain）、无效类型确认、未认证确认、不存在帖子确认
- 安装测试依赖：pytest、pytest-asyncio、httpx
- 全部 38 个测试通过

## 3. 未完成内容

暂无。

## 4. 实现思路

- 使用 `sqlite+aiosqlite://` 内存数据库作为测试数据库，避免影响开发数据
- 通过 FastAPI 的 `dependency_overrides` 机制替换 `get_db` 依赖，使所有请求使用测试数据库
- 每个测试用例前自动创建所有表、测试后自动清除，确保测试隔离
- 使用 httpx 的 `ASGITransport` + `AsyncClient` 直接调用 FastAPI 应用，无需启动服务器
- 对于帖子列表接口（默认只显示 published 状态），通过直接在 DB 中创建 published 状态的帖子来测试
- 注意到同一秒内生成的 JWT token 可能相同（exp 相同），因此 refresh 测试中不比较 token 是否不同

## 5. 修改文件

- 新增：`backend/tests/conftest.py`
- 新增：`backend/tests/test_auth.py`
- 新增：`backend/tests/test_posts.py`
- 新增：`backend/tests/test_interactions.py`
- 安装依赖：pytest、pytest-asyncio、httpx（未写入 requirements.txt）

## 6. 影响范围

- 仅影响测试目录 `backend/tests/`，不影响业务代码

## 7. 测试与验证

- 运行 `python -m pytest backend/tests/ -v`，38 个测试全部通过
- 测试覆盖了认证、帖子 CRUD、互动（点赞/收藏/有效性确认）的核心接口
- 包含正向和反向测试（权限校验、不存在资源、未认证访问等）

## 8. 后续建议

- 将 pytest、pytest-asyncio、httpx 添加到 `requirements.txt` 或单独的 `requirements-dev.txt`
- 添加更多边界测试（如输入验证、并发操作等）
- 添加评论、搜索、通知等模块的测试
- 考虑添加测试覆盖率报告（pytest-cov）
