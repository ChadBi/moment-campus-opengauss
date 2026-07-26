# 任务报告：评论、协同治理、专题订阅、个人中心、通知中心 E2E 链路测试

## 1. 任务概述

对评论模块、协同治理（5 类验证）、专题订阅通知、个人中心、通知中心等模块进行端到端（E2E）链路测试，验证关键功能、权限校验、通知触发、跨模块联动等关键链路在真实运行环境（前后端已启动、openGauss 数据库）下的正确性，并修复测试过程中发现的 Bug。

## 2. 已完成内容

### 2.1 Bug 修复

- **专题订阅通知不触发**（SUB-01.2）：管理员将帖子加入专题时，订阅该专题的用户未收到 `subscription_new` 通知。
  - 修复位置：[backend/app/api/admin_topics.py](file:///e:/Project/moment-campus/backend/app/api/admin_topics.py)
  - 修复方式：在 `add_posts_to_topic` 流程中接收 `_assert_post_in_same_school_published` 返回的 post 对象，并调用 `app.services.subscription_notifier.notify_new_post` 通知订阅者；通知失败不阻塞主流程，仅记录 warning。

### 2.2 E2E 链路验证（5 个脚本，覆盖 5 大模块）

1. **专题订阅通知链路**（`verify_subscription_fix.py`）
   - user1 已订阅 topic_id=1（新生入学指南）→ user2 创建帖子 → admin 审核通过 → admin 将帖子加入专题 → user1 收到 `subscription_new` 通知（通知数 3→4，target_id 命中新建 post_id=92）。
   - 帖子在专题详情中可见。

2. **评论模块链路**（`verify_comments.py`）
   - user2 评论 user1 的帖子（201）→ user1 收到「您的帖子有新评论」通知 ✅
   - user1 回复 user2 的评论（201）→ user2 收到「有人回复了你的评论」通知 ✅
   - 评论列表嵌套结构正确（顶级 1 + 回复 1，层级正确）✅
   - user2 删除自己的顶级评论（200），删除后列表不再可见 ✅
   - user2 越权删除 user1 的回复 → 403 ✅

3. **协同治理 5 类验证链路**（`verify_governance.py`）
   - **2 类互斥投票**：user2 投 confirmation + user3 投 refutation → 1:1=uncertain ✅
   - 作者不能给自己帖子投票 → 403 ✅
   - 投票替换语义：user2 改投 refutation → confirmation 0 / refutation 2 / validity=invalid ✅
   - **3 类问题报告**：update / expiration_report / conflict_report 全部成功提交（201）✅
   - 重复提交同类型未结案报告 → 400 ✅
   - 3 类报告齐全，open_count=3 ✅
   - admin 流转 update→resolved、expiration_report→in_review ✅
   - 作者 user1 标记 conflict_report→resolved ✅
   - 作者非 resolved 流转 → 403 ✅
   - 普通用户处理他人报告 → 403 ✅
   - 帖子详情 governance 聚合正确（confirmation=0, refutation=2, validity=invalid, total=3, open=1）✅

4. **个人中心链路**（`verify_profile.py`）
   - 获取/更新用户资料（nickname/bio/avatar_url）+ 持久化验证 ✅
   - 我的发布按状态筛选：published=8 / draft=0 / pending=2，6 态求和=11=total ✅
   - 我的统计（PRF-01.2）：状态分组与列表一致，confirmation_count=3 ✅
   - 浏览历史：访问帖子→列表+1→重复访问唯一约束（仍为 1 条）→删除单条→清空全部→0 ✅
   - 通知偏好（UX-01.5）：GET + PUT 切换 subscription_enabled ✅

5. **通知中心链路**（`verify_notifications.py`）
   - 触发评论通知 → unread-count=4 / has_unread=true ✅
   - 按已读状态筛选（未读 4 / 已读 3），按类型筛选（comment=3）✅
   - 标记单条已读 + 重复幂等 + 未读数 -1 ✅
   - 不存在的通知 → 404 ✅
   - 越权标记（user2 标记 user1 的通知）→ 404（不泄露存在性）✅
   - 标记全部已读 → 未读数 0 ✅
   - 安全通道全关（system/audit/instant 全 false）→ 400 ✅
   - 关 system+audit 保留 instant → 200 ✅
   - 非法 digest_time=25:00 → 400 / 合法 08:30 → 200 ✅

### 2.3 测试与构建

- 后端 `pytest tests/ -v`：**972 passed, 66 skipped**（用时 14:55）
- 前端 `npm run build`：**✓ built in 23.67s** 成功

## 3. 未完成内容

暂无。

## 4. 实现思路

1. **修复优先**：先修复测试中发现的 Bug（专题订阅通知不触发），再继续 E2E 验证，避免误判。
2. **API 直连验证**：使用 Python + requests 库直接调用后端 API，模拟真实用户操作流程（登录→创建→审核→评论→投票→报告→通知→个人中心），比浏览器自动化更快且断言精确。
3. **断言驱动**：每个测试点都有明确的期望值与 assert，确保链路真正跑通而非"看起来正常"。
4. **跨模块联动**：测试专题订阅时联动审核流程；测试评论时联动通知中心；测试协同治理时联动权限矩阵；测试个人中心时联动浏览历史与统计；测试通知中心时联动评论触发与偏好校验。
5. **回归保障**：所有 E2E 脚本运行完毕后，再跑完整 pytest 套件与 npm build，确保本次修改未引入回归。

## 5. 修改文件

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `backend/app/api/admin_topics.py` | 修改 | 修复专题订阅通知不触发：在 add_posts_to_topic 中调用 notify_new_post |
| `verify_subscription_fix.py` | 新增 | 专题订阅通知链路验证脚本 |
| `verify_comments.py` | 新增 | 评论模块 E2E 验证脚本 |
| `verify_governance.py` | 新增 | 协同治理 5 类验证 E2E 脚本 |
| `verify_profile.py` | 新增 | 个人中心 E2E 验证脚本 |
| `verify_notifications.py` | 新增 | 通知中心 E2E 验证脚本 |
| `AIwork/评论协同治理专题订阅个人中心通知中心E2E链路测试任务报告.md` | 新增 | 本任务报告 |

## 6. 影响范围

- **专题订阅通知**：`backend/app/api/admin_topics.py` 中 `add_posts_to_topic` 端点的行为变化——加入专题后订阅者会收到通知。修改向后兼容，通知失败不阻塞主流程。
- **其他模块**：本次未修改代码，仅通过 E2E 脚本验证已有实现，无影响。
- **测试脚本**：5 个 verify_*.py 脚本位于项目根目录，是临时验证脚本，不参与构建与运行时。

## 7. 测试与验证

### 7.1 E2E 自动化测试（API 直连）

执行命令（在 `backend/` 目录下）：

```powershell
.\.venv\Scripts\python.exe ..\verify_subscription_fix.py
.\.venv\Scripts\python.exe ..\verify_comments.py
.\.venv\Scripts\python.exe ..\verify_governance.py
.\.venv\Scripts\python.exe ..\verify_profile.py
.\.venv\Scripts\python.exe ..\verify_notifications.py
```

5 个脚本全部退出码 0，所有 assert 通过。

### 7.2 后端单元/集成测试

```powershell
$env:TEST_DATABASE_URL = 'postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test'
$env:APP_ENV = 'opengauss'
cd backend
.\.venv\Scripts\python.exe -m pytest tests/ --tb=short -q
```

结果：**972 passed, 66 skipped, 2057 warnings in 895.82s**。
- skipped 66 项主要为 openGauss 物理对象集成测试（test_indexes / test_materialized_views / test_partitions / test_stored_procedures / test_tablespaces / test_triggers），与本次修改无关。
- warnings 主要是 Pydantic 序列化 UserBrief 时的类型提示警告，不影响功能。

### 7.3 前端构建

```powershell
cd frontend
npm run build
```

结果：**✓ built in 23.67s**，所有资源正常产出至 `dist/`。MapPage 体积较大（1MB+）属已知问题（地图组件依赖），与本次修改无关。

### 7.4 测试覆盖矩阵

| 模块 | 关键链路 | 验证结果 |
| --- | --- | --- |
| 专题订阅 | user 订阅 → 帖子入专题 → 通知触发 | ✅ |
| 评论 | 创建/回复/嵌套/删除/越权 | ✅ |
| 协同治理-投票 | confirmation/refutation/替换/作者禁投 | ✅ |
| 协同治理-报告 | update/expiration/conflict/重复拒绝 | ✅ |
| 协同治理-处理 | admin 流转/作者标记/权限矩阵 | ✅ |
| 个人中心-资料 | 编辑/持久化 | ✅ |
| 个人中心-发布 | 6 态筛选/求和校验 | ✅ |
| 个人中心-统计 | 状态分组/贡献验证 | ✅ |
| 个人中心-历史 | 写入/唯一约束/删除/清空 | ✅ |
| 通知中心-列表 | 类型/已读筛选 | ✅ |
| 通知中心-已读 | 单条/全部/幂等/越权/404 | ✅ |
| 通知中心-偏好 | 安全通道/digest_time 校验 | ✅ |

## 8. 后续建议

1. **将 5 个 verify_*.py 脚本纳入 CI**：可作为冒烟测试定期运行，但需注意它们依赖真实运行的后端服务与种子数据（user1~user10、admin、江南大学），建议在 CI 环境中提供等价的测试库与种子。
2. **浏览器 E2E 补充**：本次以 API 直连验证为主，后续可使用 `integrated_code_mode` 的浏览器工具补充 UI 层交互验证（如通知中心红点角标实时刷新、个人中心编辑表单校验提示等），形成 API + UI 双层覆盖。
3. **专题订阅通知的边界场景**：当前修复覆盖"帖子加入专题"这一主路径，后续可补充"帖子从专题移除""专题下线/删除"等场景下的通知行为定义（是否需要通知订阅者）。
4. **清理临时验证脚本**：5 个 verify_*.py 与之前的 pytest_e2e_output.log 可在正式 CI 化后删除或迁移至 `tests/e2e/` 目录。
5. **MapPage 体积优化**：前端构建提示 MapPage 超过 500KB，建议后续通过动态 import 进行代码分割。
