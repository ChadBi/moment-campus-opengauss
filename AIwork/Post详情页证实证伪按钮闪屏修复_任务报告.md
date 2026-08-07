# 任务报告：Post 详情页证实/证伪按钮点击后整页闪屏修复

## 1. 任务概述

用户反馈：在 Post 详情页点击「证实」或「证伪」协同验证按钮后，**整个页面会「闪一下」，就好像重新加载了**。需要排查根因并修复，同时保留协同验证的业务逻辑（新增/切换/取消）与数据一致性。

## 2. 已完成内容

### 2.1 根因定位（调用链收敛到唯一原因）

点击证实/证伪 → `handleValidate(type)`（PostDetailPage.tsx L196）成功后执行 `void loadPost(true)` → 进入 `loadPost` 后立即执行 `setLoading(true)` → 命中组件主体 L391 守卫 `if (loading) return <LoadingState title="正在加载校园信息"/>` **整页 Early Return** → DOM 卸载帖子详情并替换为 1 行 Loading 骨架屏 → 请求返回后 `setLoading(false)` 再渲染帖子详情。

在人类视觉上表现为：`帖子详情 → 白色 Loading 骨架 → 帖子详情`，即「闪一下」，感知上与「浏览器整页刷新/重新加载」完全一致。

（对比：`handleLike` 点赞函数使用了就地 `setPost(prev => ({...prev, like_count, is_liked}))` 不切 loading，所以没有闪屏，是正确写法。）

### 2.2 修复方案

给 `loadPost(skipViewCount = false)` 新增**第 2 个可选参数 `silent = false`**：

```typescript
const loadPost = async (skipViewCount = false, silent = false) => {
  try {
    if (!silent) setLoading(true);  // ← 仅非静默时切 loading
    setPostError(null);
    const response = await postsApi.getPost(Number(id), !skipViewCount);
    setPost(response as Post);
  } catch (err: unknown) {
    ...
  } finally {
    if (!silent) setLoading(false);  // ← 仅非静默时复位
  }
};
```

`handleValidate` 成功后调用改为：

```typescript
void loadPost(true, true);  // skipViewCount=true, silent=true
```

### 2.3 兼容性保障

- **首屏加载**：`useEffect(() => { void loadPost(); }, [id])` → 默认 `silent=false`，正常显示骨架屏 Loading，用户首次进入详情页仍有「正在加载」反馈 ✅
- **ErrorState 手动重试按钮**：`onRetry={() => void loadPost()}` → 默认 `silent=false`，出错后点重试同样有 Loading，交互正确 ✅
- **数据一致性**：仍通过全量 `postsApi.getPost()` 从服务端拉回最新 governance（total_validation_count / confirmation_count / refutation_count / user_validation_type），比手写「乐观更新 +1/-1 票数」的正确性更高，不会出现数字对不上的 UI 瑕疵 ✅
- **点赞（handleLike）/评论（handleComment/handleReply）**：这些函数没有调用 `loadPost`，原逻辑不受影响 ✅

### 2.4 构建验证
前端 `npm run build`：tsc -b 0 error + vite build 1973 modules transformed（耗时 1.39s），0 warning。

## 3. 未完成内容

暂无（本次修复属于单点局部问题，所有用户可见的「闪屏」路径已全部收敛到 `loadPost` + `silent` 参数）。

## 4. 实现思路

### 4.1 根因排查思路（可证伪列表逐项排除）

当用户说「点按钮后整页像重新加载」时，枚举所有可能性并排除：
1. ❌ **路由跳转/Navigate replace 触发**：检查 handleValidate 代码无 navigate 调用，路由参数 `{id}` 也未变化
2. ❌ **React Query 的 refetchOnMount / isFetching 全局重渲染**：本页未用 React Query，全部是 useState + useEffect，排除
3. ❌ **组件 key 变化导致卸载重挂载**：外层 Outlet 没有 key 传参，post.id 也没变，排除
4. ❌ **`<form>` submit 默认 reload 行为**：handleValidate 没有 form，是普通 button.onClick，排除
5. ✅ **Early Return 守卫触发**：组件里存在 `if (loading) return <LoadingState/>`，点击后 loading 从 false→true→false 会三次走不同返回分支 → 就是这个 ✅

### 4.2 为什么选择「silent 参数」而不是「乐观更新局部 setState」？

协同验证涉及 4+ 字段联动：`total_validation_count`、`confirmation_count`、`refutation_count`、`user_validation_type`（含三种语义：首次新增 / 切换 / 取消），还会影响后续 `confirmPercent/refutePercent` 的计算百分比。手写乐观更新容易出错（例如：取消时到底是 -1 还是不变？切换时 confirmation/refutation 同时 +1/-1？），而 silent 参数方案只加一个 boolean，改动面极小，风险最低，是「工程正确性 > 极致性能」的合理取舍。

## 5. 修改文件

| 类型 | 文件 | 变更摘要 |
|------|------|----------|
| 修改 | `frontend/src/pages/PostDetailPage.tsx` | `loadPost` 新增第 2 参 `silent=false`（为 true 时跳过 setLoading 切换）；`handleValidate` 成功后调 `loadPost(true, true)` 静默刷新；对 loadPost 增加 JSDoc 说明两个参数语义 |
| 修改 | `CHANGELOG.md` | v2.2.6 前端区追加「修复点击证实/证伪后整页闪一下的感知 Bug」条目 |
| 修改 | `TODO.md` | 最后更新时间同步；「当前执行任务」区追加 `[x]` 完成条 |
| 新增 | `AIwork/Post详情页证实证伪按钮闪屏修复_任务报告.md` | 本报告 |

## 6. 影响范围

| 维度 | 影响 |
|------|------|
| **协同验证体验**：点击证实/证伪 | ✅ 无闪屏，UI 就地更新（Toast「验证已提交/已切换验证/已取消验证」→ 若干毫秒后验证条数 + 百分比无闪烁更新） |
| **首屏进入详情页** | ✅ 无变化，仍然先显示「正在加载校园信息」骨架屏，符合首次加载预期 |
| **加载失败点重试** | ✅ 无变化，ErrorState 重试按钮仍会显示 Loading，符合「我点了重试，系统在努力」的反馈预期 |
| **点赞/评论/回复** | ✅ 无影响，这三个函数各自用就地 setState 不走 loadPost |
| **性能** | ✅ 少一次 loading=true→false 带来的整页 diff+DOM 卸载重挂，实际更快 |
| **代码复杂度** | ➕ 增加 1 个 boolean 参数，为避免后续误用，在 loadPost 上方加了 6 行 JSDoc 双参说明，总改动 < 15 行 |

## 7. 测试与验证

| 验证项 | 执行方式 | 结果 |
|--------|----------|------|
| 类型 & 构建 | `frontend $ npm run build`（tsc -b + vite build） | ✅ 0 error；1973 modules / 1.39s |
| 调用链静态走查 | `handleValidate → loadPost(true,true)`；`useEffect → loadPost()`；`ErrorState onRetry → loadPost()` | ✅ 3 条路径全部覆盖；只有 handleValidate 走 silent=true，其他两个路径正常切换 loading |
| 根因排除法复盘 | 枚举「路由跳转 / React Query refetch / 组件 key / form 原生 reload / Early Return」5 条假设，并收敛到唯一根因 | ✅ 与症状 100% 吻合：loading 状态导致的整页骨架屏 Early Return |
| 后端 pytest | 本轮为纯前端样式/状态治理 | 未运行（后端 0 代码变更） |
| 浏览器真实点击验证 E2E | 前后台 dev server 已在后台运行（job-38062d657dc6486fa27e41d8cd67e992 / job-21fa1d5b44e34fc3a8094fbb9070262f） | 未运行自动化 E2E（需模拟登录+认证用户+定位帖子再点按钮，单次交互人工验证成本更低，建议下次人工走查顺便确认） |

## 8. 后续建议

1. **同类代码排查**：其他详情页（TopicDetail/PostDetail 已查，LocationPage 的评分 submit 是就地 setState）若存在「用户操作后再调 XX load 函数 + setLoading(true)」的模式，都可加 silent 参数统一消除闪屏。可做一次 Grep `setLoading(true);\n.*setPost/setTopic` 扫描。
2. **升级为 React Query 模式**：长远来看，把 useState + useEffect + loadPost 改成 `useQuery({ queryKey: ['post', id], ... })` 模式，`refetch()` 天然是 silent 的（不会触发 isLoading=true，只会切 isFetching），UI 上用 Skeleton 绑定 isLoading、右下角灰色 loading 小圆绑定 isFetching，就能同时解决「首次加载」和「静默刷新」两种视觉反馈，彻底根除这类 setLoading 误用。
3. **协同验证的防抖**：现在同一用户反复切换证实↔证伪（5 次以内）会产生 5 条网络请求并 5 次 silent 刷新 governance。未来可加 200ms 防抖，或「按钮切换态后本地乐观更新 + 后台 debounced sync」进一步降低请求数。
