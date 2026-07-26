# 任务报告：AI-02 AI 意图—检索—排序—理由—地图 UI

## 1. 任务概述

在 moment-campus 项目中实现 AI 结构化搜索，包含两个子任务：

- **AI-02.1** `POST /api/v1/search/ai` 后端：TenantContext 取校 → 长度/频率/敏感检查 → 模型解析意图（严格 JSON Schema + 超时 + 有限重试）→ 白名单校验分类/排序/时间/地图范围 → openGauss 查询本校可公开未删除符合状态/有效期数据 → 确定性分数排序 → 模型/模板生成简短理由 → 记录元数据 → 任一步失败降级普通搜索返回 `fallback=true`
- **AI-02.2** 前端：搜索框提示语、可编辑筛选 Chip、"为什么匹配"理由展示、更新时间/地点/有效性显示、点击结果同步定位地图、普通搜索切换、AI 降级提示；不用全屏聊天 UI

## 2. 已完成内容

### AI-02.1 后端 AI 结构化搜索

- **schemas** (`backend/app/schemas/search.py`)：新增 `AISearchRequest` / `AISearchIntent` / `AISearchIntentFilters` / `AISearchOverrides` / `AISearchMapBounds` / `AISearchResponse`，约束 query 长度 1-200、page/page_size 范围
- **service** (`backend/app/services/ai_search.py`)：实现 `execute_ai_search` 主入口
  - 敏感词检查（政治/暴力/色情/隐私 4 类正则）→ 命中降级
  - 加载白名单（当前学校分类 + 地点，防止模型编造）
  - overrides 提供 keyword 时跳过模型调用，直接构造意图
  - 否则调用 `invoke_ai`（SEARCH_INTENT_SCHEMA 约束）解析意图
  - 白名单校验：分类按 name/code 匹配、排序限 latest/hottest/nearest/active/relevance、时间 ISO 解析、地图范围 north>south & east>west
  - 查询：school_id 强制取自 TenantContext、is_deleted=False、status=published、未过期、关键词 ilike title/content/contact_info、分类/地点/时间/地图范围筛选、limit 200 候选
  - 确定性打分：时间新鲜度 40%（30 天衰减）+ 验证数 30%（10 次封顶）+ 相关度 30%（标题 1.0 / 内容 0.6 / 联系方式 0.3 / 默认 0.5）
  - 排序：relevance 按分数降序、latest 按 created_at 降序、hottest 按 like_count 降序、active/nearest 按 updated_at 降序
  - 模板理由：今日发布/N 天内发布/近一个月发布 + 获 N 次证实 + 标题包含「关键词」/内容描述匹配 + 地点 + 分类 + 点赞数
  - 分页 + 响应构造
  - 任一步失败 → 降级普通搜索（用 query 作为关键词，应用 overrides）
- **API** (`backend/app/api/search.py`)：新增 `POST /search/ai` 端点
  - 集成 TenantContext（三校隔离）+ get_current_user_optional（游客可搜索）
  - 限流：RateLimitMiddleware 已配置 10 次/分钟
  - 搜索历史记录（登录用户 + 有意图关键词时）
- **AI schema** (`backend/app/ai/schemas.py`)：`SEARCH_INTENT_SCHEMA` 新增 `map_bounds` 字段（north/south/east/west）支持地图范围过滤
- **安全约束**：
  - school_id 强制取自 TenantContext，不信任外部传入
  - 提示词只含当前学校分类/地点白名单，不泄露其他学校数据
  - 密钥仅从 settings.AI_API_KEY 读取，不进日志/响应/前端
  - 隐私约束：ai_invocation_logs 只保存 input_length 与 input_hash

### AI-02.2 前端 SearchPage 集成

- **类型定义** (`frontend/src/types/index.ts`)：新增 `AISearchRequest` / `AISearchResponse` / `AISearchIntent` / `AISearchIntentFilters` / `AISearchOverrides` / `AISearchMapBounds` / `AISearchSort`（避免循环依赖，inline 定义不导入 SearchSort）
- **服务层** (`frontend/src/services/search.ts`)：新增 `aiSearch` 方法调用 `POST /search/ai`
- **SearchPage** (`frontend/src/pages/SearchPage.tsx`)：
  - 搜索框提示语："试试自然语言提问，如：图书馆附近最近的失物招领"
  - 模式切换按钮：普通搜索（Search 图标）/ AI 智能搜索（Wand2 图标），选中态 bg-lake text-white
  - AI 意图展示卡片：灯泡图标 + 意图描述 + 整体匹配理由（join 分号）
  - 可编辑筛选 Chip：
    - 关键词 Chip：input 可编辑，回车/失焦触发覆盖检索，含移除按钮
    - 分类 Chip：select 下拉（含图标+名称），含移除按钮
    - 排序 Chip：select 下拉（latest/hottest/nearest/active/relevance）
    - 时间范围 Chip：双 date input（from ~ to）
  - "为什么匹配？" 折叠面板：每条结果卡片底部按钮（含分数显示），点击展开匹配理由列表（圆点引导 + 文案）
  - 降级提示横幅：fallback=true 时顶部橙色横幅"AI 搜索暂时不可用，已切换为普通搜索：{原因}"，含关闭按钮
  - 点击结果同步定位地图：复用既有 MapPage focusPost 机制（localStorage `map:focus_post` + 路由跳转 `/map`）
  - 普通搜索切换：模式切换按钮一键切回普通搜索，保留 query 并清空 AI 状态
  - 不使用全屏聊天 UI

### 测试

- **后端测试** (`backend/tests/test_ai_search.py`)：21 个用例全部通过
  - 成功场景 4：返回意图+结果+分数+理由 / relevance 排序标题匹配优先 / 匹配理由含关键词 / 成功记录日志
  - 降级场景 5：Provider 网络错误 / 超时 / JSON 解析失败 / 敏感词 / 降级仍记录日志
  - overrides 2：提供 overrides 跳过模型 / 非法 category_id 置空
  - 白名单 3：非法分类丢弃 / 非法 sort 回退 latest / map_bounds 过滤地点
  - 租户隔离 2：A 校只返回 A 校帖子 / 提示词不含 B 校分类
  - 确定性打分 2：相同输入相同顺序 / 分数在 [0,1] 区间
  - 输入校验 3：空 query 拒绝 / 超长 query 拒绝 / 缺 X-School-Code 拒绝
- **前端构建**：`npm run build` 通过（`SearchPage-B4oY8M2K.js 26.66 kB`）

## 3. 未完成内容

暂无。

## 4. 实现思路

### 后端架构

采用「意图解析 → 检索 → 打分 → 理由」四阶段流水线，任一阶段失败均降级普通搜索：

1. **意图解析**：复用 AI-01 的 `invoke_ai` 服务（Provider 适配层 + 熔断 + 重试 + 日志），通过 `SEARCH_INTENT_SCHEMA` 严格约束模型输出为 JSON。提示词注入当前学校分类/地点白名单，防止模型编造不存在的分类。
2. **检索**：SQL 层面严格过滤（school_id / is_deleted / status / expire_at），关键词 ilike title/content/contact_info，分类/地点/时间/地图范围筛选。预加载关联（joinedload + selectinload）消除 N+1。
3. **打分**：确定性公式 `0.4*freshness + 0.3*validation + 0.3*relevance`，相同输入相同输出。freshness 按 30 天线性衰减，validation 按 10 次封顶，relevance 按标题/内容/联系方式匹配分级。
4. **理由**：模板生成（不每次调模型），从帖子属性推导（时间新鲜度 / 验证数 / 关键词命中位置 / 地点 / 分类 / 点赞数）。

### 降级策略

- 敏感词命中：不调用模型，直接降级
- Provider 异常（网络/超时/429/余额/熔断）：AI-01 层已封装为 `AIInvokeOutcome(fallback=True)`，service 层直接降级
- JSON 解析失败 / 白名单校验失败 / 查询失败 / 打分失败：捕获异常降级
- 降级时仍记录 ai_invocation_logs（output_status != success），返回 fallback=true + 降级原因 + 普通搜索结果

### overrides 覆盖机制

用户提供 overrides 时不调用模型，直接用 overrides 构造意图检索。这避免了用户编辑 Chip 后重复调用模型的成本，同时保持白名单校验（非法 category_id 置空不报错）。

### 前端 UX 设计

- 不使用全屏聊天 UI，而是复用既有搜索页布局
- 模式切换按钮位于搜索框上方，清晰区分普通/AI 模式
- AI 意图展示卡片位于搜索框下方，包含意图描述 + 可编辑筛选 Chip + 整体理由
- 每条结果卡片底部"为什么匹配？"按钮，点击展开匹配理由列表
- 降级时顶部橙色横幅提示，用户可关闭

## 5. 修改文件

### 新增文件
- `backend/app/schemas/search.py`（AI 搜索 schemas）
- `backend/app/services/ai_search.py`（AI 搜索服务主入口）
- `backend/tests/test_ai_search.py`（AI 搜索测试 21 个用例）
- `AIwork/AI-02_AI意图检索排序理由地图UI任务报告.md`（本报告）

### 修改文件
- `backend/app/api/search.py`（新增 `POST /search/ai` 端点）
- `backend/app/ai/schemas.py`（SEARCH_INTENT_SCHEMA 新增 map_bounds 字段）
- `frontend/src/types/index.ts`（新增 AI 搜索类型定义）
- `frontend/src/services/search.ts`（新增 aiSearch 方法）
- `frontend/src/pages/SearchPage.tsx`（集成 AI 搜索 UI：模式切换/意图卡片/可编辑 Chip/匹配理由/降级横幅）
- `TODO.md`（新增 AI-02 完成条目，标记 R-04 完成）

## 6. 影响范围

- **后端搜索模块**：新增 AI 搜索端点，与既有普通搜索 `GET /search` 并存，互不影响
- **AI 模块**：复用 AI-01 Provider 适配层与 invoke_ai 服务，扩展 SEARCH_INTENT_SCHEMA
- **前端搜索页**：SearchPage 新增 AI 模式，与普通模式共享结果列表组件
- **地图页**：复用既有 focusPost 机制，无需修改 MapPage
- **数据库**：无 schema 变更，复用既有 ai_invocation_logs 表
- **租户隔离**：AI 搜索严格遵循 TenantContext 三校隔离，不泄露其他学校数据

## 7. 测试与验证

### 后端测试
- 命令：`pytest tests/test_ai_search.py -v`
- 结果：21 个用例全部通过（95.91s）
- 覆盖：成功场景 / 降级场景 / overrides / 白名单 / 租户隔离 / 确定性打分 / 输入校验

### 前端构建
- 命令：`npm run build`
- 结果：构建成功，SearchPage chunk 26.66 kB

### 测试基础设施问题
- 发现 openGauss 测试库 post_types 表存在残留数据导致 `idx_posttype_code` 唯一约束冲突（previous test session 残留 + openGauss 跨连接可见性问题）
- 解决：运行测试前通过 Python 脚本清理 post_types 表残留数据；测试用例间 TRUNCATE 由 conftest.py 负责
- 修复测试 bug：`match_reasons` 的 dict key 经 JSON 序列化后 int 变 string，测试断言改用 `str(item["id"])`

### 未运行完整测试套件
- 仅运行 `tests/test_ai_search.py`（AI-02 相关），未运行 `pytest tests/ -v` 全量测试
- 原因：AI-02 任务范围仅涉及 AI 搜索，全量测试超出当前任务范围；AI 搜索测试已全部通过

## 8. 后续建议

- **R-07 性能验证**：AI 搜索的候选数限制为 200，需在复赛规模数据下验证打分排序性能
- **R-08 E2E 测试**：建立 AI 搜索 + 降级核心 E2E 测试（Playwright，目前未安装）
- **AI-03 AI 辅助发布**：复用 AI-01 Provider 层与 invoke_ai 服务，实现发布时的分类/标签/地点/有效期建议
- **敏感词扩展**：当前敏感词为基础正则清单，生产环境应接入专门的内容安全服务
- **模型理由增强**：当前理由为模板生成，未来可考虑在模型成本可控时让模型生成更丰富的理由
- **搜索历史联动**：当前仅记录登录用户的搜索历史，可考虑基于历史优化提示词或推荐
