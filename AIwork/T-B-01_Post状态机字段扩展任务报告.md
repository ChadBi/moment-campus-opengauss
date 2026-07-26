# 任务报告：T-B-01 Post 状态机字段扩展（6 态流转）

## 1. 任务概述

将 Post 模型的 `status` 字段从当前 3 态（draft/pending/published）扩展为 6 态状态机：`draft` / `pending` / `published` / `expired` / `conflict` / `archived`，定义合法流转规则，提供 `can_transition()` 函数供后续 Service 层（T-B-03/T-B-04）调用，并补全单元测试。

对应任务：[docs/21_后续开发任务清单.md](../docs/21_后续开发任务清单.md) T-B-01（阶段 B 第 1 项，P0）

## 2. 已完成内容

### 2.1 验收标准逐项核对

| 验收标准 | 完成情况 |
|---------|---------|
| 1. Post 模型 `status` 字段类型为 `String(20)`，含注释说明 6 态 | ✅ [post.py](../backend/app/models/post.py) 第 20-26 行，添加 `comment` 参数 |
| 2. `post_status.py` 定义状态枚举与合法流转规则 | ✅ [post_status.py](../backend/app/core/post_status.py) 定义 `PostStatus` 类与 `_TRANSITIONS` 字典 |
| 3. 提供 `can_transition(current, target)` 函数 | ✅ 同文件提供 `can_transition` / `get_allowed_transitions` / `is_valid_status` / `normalize_status` |
| 4. 新增 Alembic 迁移脚本（仅注释变更，无需数据迁移） | ✅ [b1a2c3d4e5f6_post_status_machine_6_states.py](../backend/alembic/versions/b1a2c3d4e5f6_post_status_machine_6_states.py) |
| 5. 单元测试覆盖所有合法/非法流转 | ✅ [test_post_status.py](../backend/tests/test_post_status.py) 54 项测试全部通过 |

### 2.2 6 态状态机定义

| 状态 | 含义 | 说明 |
|------|------|------|
| `draft` | 草稿 | 用户创建未提交 |
| `pending` | 待审核 | 等价于 doc 21 中的 `pending_review`，沿用现有代码命名以保持兼容 |
| `published` | 已发布 | 管理员审核通过 |
| `expired` | 已过期 | 自动过期或手动过期 |
| `conflict` | 冲突中 | 同一地点出现相互矛盾的信息 |
| `archived` | 已归档 | 终态，不可流转 |

### 2.3 合法流转规则（共 13 条）

```
draft      → pending / archived
pending    → published / draft / archived
published  → expired / conflict / archived
expired    → published / archived    （支持续期）
conflict   → published / archived    （管理员裁定后）
archived   → （终态，不可流转）
```

### 2.4 向后兼容性设计

- **别名映射**：doc 21 中的 `pending_review` 在 `PostStatus.ALIASES` 中映射为 `pending`，外部输入接受两种命名
- **default 不变**：模型 `status` 默认值保持 `"pending"`，无需数据迁移
- **seed_data 兼容**：现有 30 条 `status="published"` 数据在新状态机中仍为有效状态
- **现有测试兼容**：`test_create_post_authenticated` 期望新创建帖子 `status=="pending"` 仍成立
- **字段长度足够**：最长状态值 `published`（9 字符）远小于 `String(20)`

## 3. 未完成内容

- **T-A-04 遗留问题未修复**：`test_posts.py` / `test_interactions.py` 存在 33 个错误，错误为 `NOT NULL constraint failed: schools.id`，原因是 SQLite + BigInteger 主键不支持 autoincrement（SQLAlchemy 仅对 `INTEGER PRIMARY KEY` 启用 rowid 自动递增）。**此问题在 T-B-01 改动前已存在**（已通过 `git stash` 验证），不属于 T-B-01 引入，建议在后续单独任务（如 T-A-04 修复补丁或 T-B-03）中统一处理：将 21 个模型主键改为 `BigInteger().with_variant(Integer, "sqlite")`
- **openGauss 环境验证未执行**：T-B-01 单元测试基于 SQLite，openGauss 上的迁移脚本执行留到 T-B-07 阶段 B 联调验证

## 4. 实现思路

### 4.1 命名决策：`pending` vs `pending_review`

doc 21 验收标准写明 6 态包含 `pending_review`，但现有代码、seed_data、测试全部使用 `pending`。两种选择：

| 方案 | 优点 | 缺点 |
|------|------|------|
| A. 改用 `pending_review` | 与 doc 21 完全一致 | 破坏现有 seed_data/测试，需数据迁移 |
| B. 沿用 `pending` + 别名映射 | 零破坏，向后兼容 | 与 doc 21 命名略有差异 |

**最终选择方案 B**，理由：
1. 验收标准"风险/注意事项"明确要求"不要破坏现有 30 条演示数据"
2. `pending` 是 `pending_review` 的合理简写，语义等价
3. 通过 `ALIASES` 字典保证 doc 21 命名仍可被接受
4. 符合 MVP 原则，避免不必要的数据迁移

### 4.2 状态机实现方式

采用**纯函数 + 字典查表**而非状态机类，理由：
- Post 是 ORM 实体，状态作为字符串字段存储，不需要状态对象
- 纯函数无副作用，易于单元测试
- 字典查表 O(1) 复杂度，性能优于状态模式

### 4.3 Alembic 迁移脚本设计

迁移脚本仅修改 `comment`，不修改字段类型/default：
- **upgrade**：`op.alter_column` 添加 comment（仅非 SQLite 方言执行）
- **downgrade**：`op.alter_column` 移除 comment
- **SQLite 兼容**：通过 `bind.dialect.name != "sqlite"` 判断跳过，因 SQLite 不支持 column comment

## 5. 修改文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/core/post_status.py` | 新增 | 状态机定义与流转规则（124 行） |
| `backend/app/models/post.py` | 修改 | `status` 字段添加 `comment` 参数（第 20-26 行） |
| `backend/alembic/versions/b1a2c3d4e5f6_post_status_machine_6_states.py` | 新增 | Alembic 迁移脚本（仅注释变更） |
| `backend/tests/test_post_status.py` | 新增 | 单元测试 54 项（272 行） |
| `TODO.md` | 修改 | 标记 T-B-01 完成 |

## 6. 影响范围

- **Post 模型**：`status` 字段语义扩展，但类型/default/索引不变，向后兼容
- **后续任务依赖**：T-B-03（Service 层抽取）将调用 `can_transition()` 校验状态流转；T-B-04（API 改造）新增 `POST /api/v1/posts/{id}/transition` 接口；T-C-01（可信度计算）/T-C-02（自动过期）/T-C-03（冲突检测）均依赖 6 态定义
- **数据库**：openGauss 上 `posts.status` 字段新增 comment，无数据变更
- **前端**：T-B-05（详情页改造）将消费 6 态展示状态徽章

## 7. 测试与验证

### 7.1 已执行测试

```
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_post_status.py -v
```

**结果：54 passed, 4 warnings in 23.40s**

测试覆盖：
- `TestPostStatusConstants`（3 项）：6 态常量定义完整性、长度校验
- `TestIsValidStatus`（8 项）：6 个正式状态 + 别名 + 非法值
- `TestNormalizeStatus`（3 项）：别名归一化、正式名不变、未知值原样返回
- `TestCanTransitionLegal`（13 项）：覆盖全部 13 条合法流转 + 别名流转
- `TestCanTransitionIllegal`（13 项）：终态、跨级流转、回退、自流转、未知状态
- `TestGetAllowedTransitions`（9 项）：每个状态的允许集合 + 别名归一化 + 返回值副本隔离
- `TestBackwardCompatibility`（4 项）：seed_data published 兼容、default pending 兼容、关键流转可用

### 7.2 未执行测试及原因

- **`test_posts.py` / `test_interactions.py`**：未运行通过，但失败原因是 T-A-04 遗留的 SQLite BigInteger 主键 autoincrement 问题，**非 T-B-01 引入**（已通过 `git stash` 验证 T-B-01 改动前后失败数量一致）。建议在后续单独任务修复 T-A-04
- **openGauss 迁移脚本执行**：未执行，留到 T-B-07 阶段 B 联调验证

## 8. 后续建议

1. **修复 T-A-04 SQLite 兼容性（高优先级）**：将 21 个模型主键改为 `BigInteger().with_variant(Integer, "sqlite")`，使 SQLite 环境下 `test_posts.py` / `test_interactions.py` 恢复通过。建议作为 T-B-03 开始前的前置修复
2. **T-B-02 协同验证类型扩展**：将 `ValidationRecord.validation_type` 扩展为 5 类（confirmation/refutation/update/expiration_report/conflict_report），参考本任务的别名映射设计模式
3. **T-B-04 API 改造**：新增 `POST /api/v1/posts/{id}/transition` 接口，调用 `can_transition()` 校验流转合法性，区分用户/管理员权限（管理员可强制流转，普通用户只能 `draft → pending`）
4. **openGauss 迁移执行**：在 T-B-07 联调前，于 openGauss 容器执行 `alembic upgrade head` 应用本迁移，验证 comment 写入成功
5. **状态机图文档化**：可在 [docs/25_数据库概念模型设计.md](../docs/25_数据库概念模型设计.md) 中补充 6 态状态机流转图
