# 任务报告：E2E 测试反馈四项修复

## 1. 任务概述

针对《全功能 E2E 测试任务报告》中暴露的 4 项遗留问题进行修复：

1. **2.2.5 提交审核按钮遮挡**：PostForm 的「提交审核」按钮被底部固定导航栏遮挡，JS 点击后未触发后端 API。
2. **3.8 分类名称核查**：核对 `seed_data.py` 中 5 类分类的实际名称，确认测试期望是否需要更新。
3. **后端登录限流优化**：测试环境放宽限流（20 次/60 秒），避免 API 验证脚本间隔等待。
4. **verify_governance.py 脚本更新**：脚本仍测试 3 类问题报告，但 Task 1.1 已删除 ChangeReport 模型。

## 2. 已完成内容

| # | 项目 | 状态 | 说明 |
|---|---|---|---|
| 1 | PostForm 提交按钮 z-index 修复 | ✅ | page 变体 submitRow：`pt-2 relative z-40 pb-24 md:pb-2`；panel 变体：`pt-1 relative z-40 pb-6 md:pb-1`。移动端 96px 底部留白 + z-40 高于 MobileNav 的 z-30 |
| 2 | seed_data.py 分类名称核查 | ✅ | 5 类分类名称确认为「分享吐槽/组队交友/二手交易/失物招领/其他」，与测试期望一致；AdminCategoriesPage `PAGE_SIZE=20` 足以容纳 5 类；测试 FAIL 根因为 `browser_evaluate` 时序问题（未等表格渲染完成） |
| 3 | 后端限流倍率函数 | ✅ | 新增 `_is_production_env()` + `_get_rate_limit_multiplier()`：APP_ENV != "production" 时倍率 ×4（登录 5→20/60s，发布 20→80/60s，AI 搜索 10→40/60s）；生产环境保持严格限流 |
| 4 | 单元测试覆盖倍率逻辑 | ✅ | `test_rel02_security.py::TestRateLimitLogic` 新增 `test_rate_limit_multiplier_non_production` 与 `test_rate_limit_multiplier_production` 两个用例 |
| 5 | verify_governance.py 重写 | ✅ | 移除 3 类问题报告（change-reports）+ 报告处理（/governance/reports/{id}）相关测试；保留 2 类互斥投票（confirmation/refutation）+ governance 聚合字段验证；标题从「5 类协同验证」改为「2 类互斥投票」 |
| 6 | E2E 浏览器验证 | ✅ | browser_use 子代理验证：移动端视口下按钮可见、可点击、点击后跳转 /profile + 成功 Toast；MobileNav z-index=30，submitRow 容器 z-index=40 |

## 3. 未完成内容

暂无。

## 4. 实现思路

### 4.1 PostForm 按钮遮挡修复

**根因分析**：
- MobileNav（`frontend/src/components/layout/MobileNav.tsx`）使用 `fixed bottom-3 z-30 md:hidden`，仅移动端显示，z-index=30
- PostForm 的 submitRow 容器使用 `flex gap-2 pt-2`，无 z-index、无底部 padding
- 在移动端长表单滚动到底部时，MobileNav 视觉上覆盖了提交按钮

**修复方案**（双层防护）：
1. **z-index 提升**：submitRow 容器加 `relative z-40`，高于 MobileNav 的 z-30，确保按钮在 stacking context 中位于导航之上
2. **底部留白**：page 变体加 `pb-24 md:pb-2`（移动端 96px / 桌面 8px），保证按钮下方有足够空间避免被固定导航遮挡
3. **panel 变体同步**：`pb-6 md:pb-1`（移动端 24px / 桌面 4px），侧滑面板内同样防止遮挡

### 4.2 分类名称核查

**核查结果**：
```python
# backend/scripts/seed_data.py:101-107
JIANGNAN_CATEGORIES = [
    ("分享吐槽", "share", "💬", "校园生活分享、吐槽、心得", 30, 1),
    ("组队交友", "teamup", "🤝", "组队、交友、活动搭子", 30, 2),
    ("二手交易", "trade", "💰", "二手物品买卖、赠予", 30, 3),
    ("失物招领", "lost_found", "🔍", "丢失与拾到物品信息", 30, 4),
    ("其他", "other", "📝", "其他校园信息", 30, 5),
]
```

- seed_data 名称 = 测试期望名称 = 「分享吐槽」，**无需更新测试期望**
- AdminCategoriesPage 使用 `PAGE_SIZE=20`，5 类分类可在一页内全部渲染，**非分页问题**
- 真正根因：`browser_evaluate` 在表格异步加载完成前执行 `innerText.includes('分享吐槽')`，返回 false
- **建议**：后续 E2E 测试在 `browser_evaluate` 前增加 `browser_wait_for` 等待表格渲染完成（如等待 `<td>` 元素出现或 `loading` 类消失）

### 4.3 后端限流倍率

**设计原则**：
- `_match_rate_limit_rule` 保持纯函数（仅返回配置的规则，便于单元测试断言 `(5, 60)`）
- 倍率在 `RateLimitMiddleware.dispatch` 中应用，不影响规则匹配逻辑
- 通过 `APP_ENV` 环境变量区分生产与非生产

**生效规则**：

| 端点 | 配置 | 非生产倍率 | 非生产实际 | 生产实际 |
|---|---|---|---|---|
| /auth/login | 5/60s | ×4 | 20/60s | 5/60s |
| /auth/register | 5/60s | ×4 | 20/60s | 5/60s |
| /auth/refresh | 10/60s | ×4 | 40/60s | 10/60s |
| /posts/ai-suggest | 10/60s | ×4 | 40/60s | 10/60s |
| /posts | 20/60s | ×4 | 80/60s | 20/60s |
| /comments | 20/60s | ×4 | 80/60s | 20/60s |
| /search/ai | 10/60s | ×4 | 40/60s | 10/60s |
| /upload | 20/60s | ×4 | 80/60s | 20/60s |

**注意**：
- pytest 环境（`TEST_DATABASE_URL` 已设置）继续完全禁用限流（`_is_test_env()` 返回 True），不受倍率影响
- 仅 dev server（`APP_ENV=opengauss`）受倍率影响，运行 verify_*.py 脚本不再触发 429

### 4.4 verify_governance.py 脚本更新

**确认结果**：
- `PostChangeReport` 模型在 Task 1.1 已删除（`backend/scripts/seed_data.py:1963` 注释明确说明）
- `/posts/{id}/change-reports` 与 `/governance/reports/{id}` 端点已下线
- 帖子详情 governance 聚合仅保留 2 类投票字段：`confirmation_count` / `refutation_count` / `total_count` / `validity_status` / `user_validation_type`
- `change_reports_total` / `change_reports_open` / `recent_change_reports` 字段已移除

**脚本重写**：
- 移除场景 6-13（3 类问题报告 + 报告处理 + 越权处理）
- 保留场景 1-5（2 类互斥投票 + 作者不能给自己投票 + 替换语义）
- 新增场景 6：帖子详情 governance 聚合字段断言
- 标题从「协同治理 5 类验证 E2E 链路验证」改为「协同治理 2 类互斥投票 E2E 链路验证」

## 5. 修改文件

### 后端
- `backend/app/middleware.py`：新增 `_is_production_env()` / `_get_rate_limit_multiplier()`；`RateLimitMiddleware.dispatch` 应用倍率
- `backend/tests/test_rel02_security.py`：`TestRateLimitLogic` 新增 2 个倍率测试用例
- `backend/tests/manual/verify_governance.py`：完全重写，移除 change-reports 相关测试

### 前端
- `frontend/src/components/PostForm.tsx`：`getVariantStyles` 中 page 与 panel 变体的 `submitRow` 样式调整（z-index + padding-bottom）

### 文档
- `AIwork/E2E测试反馈四项修复_任务报告.md`：本报告

## 6. 影响范围

| 模块 | 影响 |
|---|---|
| 前端发布表单 | PostForm 移动端按钮可见性 + 可点击性提升；桌面端无视觉变化（`md:pb-2` 保持原间距） |
| 前端侧滑面板 | MapPage 内嵌的发帖面板同步获得 z-index 防护 |
| 后端限流中间件 | 非生产环境所有 POST 关键端点限流放宽 4 倍；生产环境无变化 |
| 后端单元测试 | 限流逻辑测试用例从 8 个增至 10 个，全部通过 |
| API 验证脚本 | verify_governance.py 与当前 API 契约一致（移除已下线端点） |

## 7. 测试与验证

### 7.1 后端单元测试

```powershell
$env:TEST_DATABASE_URL = 'postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test'
.venv\Scripts\python.exe -m pytest tests/ -v
```

**结果**：`938 passed, 79 skipped, 0 failed`（804.83 秒）

新增用例：
- `test_rate_limit_multiplier_non_production`：APP_ENV=opengauss 时倍率=4
- `test_rate_limit_multiplier_production`：APP_ENV=production 时倍率=1

### 7.2 前端构建

```powershell
npm run build
```

**结果**：`✓ built in 1.42s`，PostForm-*.js chunk 30.10 kB（gzip 8.82 kB），无 TypeScript 编译错误

### 7.3 MCP 浏览器 E2E 验证

通过 `browser_use` 子代理模拟移动端用户操作：

1. **登录**：user1@example.com / pass123（江南大学）→ 成功
2. **进入发布页**：`/publish` → 表单渲染正常
3. **填表**：标题「E2E验证测试帖」+ 内容（>10 字符）+ 默认分类
4. **移动端视口**：375×812（iPhone X 尺寸）
5. **滚动到底部**：截图 `mobile-publish-form-bottom.png` 显示「提交审核」按钮位于底部导航上方
6. **z-index 校验**：
   - MobileNav computed z-index = 30（fixed 定位）
   - submitRow 容器 z-index = 40（relative 定位）
   - 按钮 `getBoundingClientRect().bottom = 638 < windowHeight = 855`，**在视口内可见**
7. **点击提交**：成功触发 API 请求，页面跳转 `/profile`，Toast 显示「已提交审核，可在'我的发布'查看进度」
8. **最终截图**：`final-screenshot-profile-page.png`

**结论**：4 项修复全部验证通过。

## 8. 后续建议

1. **E2E 测试时序优化**：后续 E2E 测试在 `browser_evaluate` 前增加 `browser_wait_for` 等待条件（如等待 `<td>` 元素出现、`loading` 类消失、或 `innerText` 包含预期关键字），避免异步加载未完成时执行断言
2. **限流配置可观察性**：建议在 `/admin/settings` 或运维文档中展示当前生效的限流规则与倍率，便于调试
3. **限流规则外部化**：当前 `RATE_LIMIT_RULES` 硬编码在 `middleware.py`，建议后续通过环境变量或配置文件覆盖，便于不同部署环境调整
4. **verify_*.py 脚本一致性巡检**：建议定期比对 `backend/tests/manual/verify_*.py` 与实际 API 路由，移除已下线端点的测试代码
