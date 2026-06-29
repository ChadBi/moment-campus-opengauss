---
name: git-commit
description: "Git 提交时自动生成符合 Conventional Commits 规范的提交信息（简体中文描述）。当用户要求提交代码、git commit、或提到「提交」时触发。"
---

# git-commit

本 skill 规范了 AI 在执行 Git 提交时必须遵循的流程和信息格式。

## 1. 触发条件

当用户消息包含以下任一意图时，触发本 skill：

- 明确要求 "提交"、"commit"、"git commit"
- 要求 "提交代码"、"提交更改"
- 要求 "生成 commit message"

**不触发的情况**：用户只是讨论代码、查看状态（`git status`）、查看日志（`git log`），未明确要求提交。

## 2. AI 执行流程

执行 Git 提交时，AI 必须按以下步骤操作：

### 步骤 1：查看变更

```bash
git status
git diff --stat
git diff
```

分析变更内容，确定：
- 改了什么文件
- 属于哪个模块（scope）
- 变更的性质（新功能？修复？重构？）

### 步骤 2：暂存文件（不含 CHANGELOG）

```bash
git add <files>
```

**规则**：
- 默认暂存所有变更文件（`git add .`），除非用户指定部分文件
- 暂存前确认不包含不应提交的文件（`.env`、`node_modules`、构建产物等）
- 如果发现敏感文件被暂存，必须警告用户并停止提交

### 步骤 3：生成提交信息

根据变更内容生成 Conventional Commits 格式的提交信息（格式见第 3 节）。

### 步骤 4：更新 CHANGELOG

在执行 git commit 之前，必须先将本次变更记录到 `CHANGELOG.md`（位于项目根目录），并将更新后的 CHANGELOG 文件纳入本次提交范围。

**规则**：
- 如果当前日期与最新版本日期不同，新增一个版本块（`## vX.X.X`），日期为当前日期，版本号为最新版本号加末位加一
- 在当前最新版本（文件顶部第一个 `## vX.X.X` 块）下追加条目
- 如果当前版本下还没有对应的分类小节，新增一个
- 根据提交的 `type` 映射到 CHANGELOG 分类（见下表）
- 条目格式：`- 简要描述`，语言与提交信息保持一致（简体中文）

**type → CHANGELOG 分类映射**：

| commit type | CHANGELOG 分类 |
|-------------|---------------|
| feat        | 新增           |
| fix         | 变更           |
| docs        | 变更           |
| style       | 变更           |
| refactor    | 变更           |
| perf        | 变更           |
| test        | 变更           |
| chore       | 变更           |
| build       | 变更           |
| ci          | 变更           |
| revert      | 移除           |

**示例**：提交 `fix(adapter): 修复工具调用超时未正确处理` 后，在 CHANGELOG.md 中追加：

```markdown
### 变更

- `adapter` 修复工具调用超时未正确处理
```

**注意**：
- 不修改已有条目，只追加
- 如果最新版本块已有对应的分类小节，直接在其末尾追加条目
- BREAKING CHANGE 提交应额外在「移除」或「变更」中说明不兼容变更
- 更新 CHANGELOG 后，必须将其也加入暂存（`git add CHANGELOG.md`）

### 步骤 5：确认提交

将生成的提交信息展示给用户确认：
- 如果用户确认，执行提交
- 如果用户要求修改，调整后重新展示
- **注意**：对已有仓库，使用 `git commit -m`；如果是首次提交，不做额外限制

### 步骤 6：验证结果

```bash
git log -1 --oneline
```

确认提交成功并展示提交结果。

## 3. 提交信息格式

### 基本格式

```
<type>(<scope>): <description>

<body>

<footer>
```

### 3.1 type（类型）

| 类型     | 说明               | 示例                                |
| -------- | ------------------ | ----------------------------------- |
| feat     | 新功能             | feat(agent): 添加 Agent 状态面板    |
| fix      | 修复问题           | fix(message): 修复消息列表刷新bug   |
| docs     | 文档修改           | docs: 更新 API 文档                 |
| style    | 样式或格式调整     | style(ui): 调整聊天布局             |
| refactor | 代码重构           | refactor(adapter): 拆分适配器管理器 |
| test     | 测试相关           | test(auth): 添加登录测试用例        |
| chore    | 工程配置或辅助工具 | chore: 更新依赖版本                 |
| perf     | 性能优化           | perf(api): 优化查询响应速度         |
| ci       | CI/CD 相关         | ci: 添加自动部署脚本                |
| build    | 构建系统或外部依赖 | build: 升级 Vite 到 5.0            |
| revert   | 回滚之前的提交     | revert: 回滚 feat(agent) 提交       |

### 3.2 scope（作用域）

作用域应清晰标识修改所属模块，如：agent、message、task、adapter、ui、api、db、auth、workspace、file、log、token 等。

**规则**：
- 优先从项目 `docs/PROJECT_STRUCTURE.md` 中获取模块列表
- 如果变更涉及多个模块，选择最主要的一个
- 如果无法确定模块，可以省略 scope：`feat: 添加全局错误处理`

### 3.3 描述（description）

1. **必须使用简体中文**
2. 首字母小写，结尾不加标点
3. 简洁清晰，不超过 50 字符
4. 描述具体做了什么，而非笼统的 "修改" 或 "更新"
5. 使用祈使句风格（如 "添加"、"修复"、"移除"，而非 "添加了"、"修复了"）

### 3.4 正文（body，可选）

当变更较复杂需要补充说明时，添加正文：

- 与标题之间空一行
- 每行不超过 72 字符
- 说明变更的动机、实现思路、与之前行为的对比
- **不强制要求**，简单变更可省略

示例：
```
fix(adapter): 修复工具调用超时未正确处理

原先超时异常被静默吞掉，导致前端一直显示"执行中"。
现在捕获 TimeoutError 并设置任务状态为失败，前端可正常展示错误。
```

### 3.5 脚注（footer，可选）

- 关联合并请求：`Closes #123`、`Refs #456`
- 标记破坏性变更：`BREAKING CHANGE: 描述`（另见第 4 节）

## 4. 破坏性变更（BREAKING CHANGE）

如果变更不兼容之前的接口或行为，必须标记。

### 方式一：type 后加 `!`

```
feat(api)!: 重构用户认证接口返回结构
```

### 方式二：footer 中说明

```
feat(api): 重构用户认证接口

BREAKING CHANGE: 认证接口返回的 token 字段改为 accessToken，
旧版客户端需同步更新。
```

两种方式可同时使用，但至少使用一种。

## 5. 多模块变更处理

如果一次提交涉及多个不相关的模块，应建议用户拆分为多个提交：

```
# 建议拆分：
git add frontend/src/... && git commit -m "fix(ui): 修复侧边栏折叠bug"
git add backend/app/... && git commit -m "fix(api): 修复返回字段缺失"
```

如果用户坚持合并提交，scope 选择最核心模块，body 中说明其他模块变更。

## 6. 错误示例

```
update              → 太笼统
fix                 → 缺少描述
111                 → 无意义
临时提交            → 不符合规范
最终版              → 不符合规范
fix: 修改了bug      → 不具体，"修改了"不符合祈使句风格
feat(agent): 添加。 → 结尾加了标点
```

## 7. 正确示例

```
feat(agent): 添加 Agent 状态面板
fix(message): 修复消息列表刷新 bug
docs: 更新 API 文档
refactor(adapter): 拆分适配器管理器
style(ui): 调整聊天布局
feat(api)!: 重构用户认证接口
fix(adapter): 修复工具调用超时未正确处理
chore: 升级 React 到 19.0
perf(db): 优化会话查询索引
```

## 8. 特殊场景

### 合并提交（Merge Commit）

保留默认格式，不做修改。

### WIP 提交

不建议生成 WIP 提交。如果用户只是暂存进度，建议使用 `git stash`。

### Amend 提交

如果用户要求修改上一次提交信息，使用 `git commit --amend -m "新信息"`，格式仍遵循本规范。
