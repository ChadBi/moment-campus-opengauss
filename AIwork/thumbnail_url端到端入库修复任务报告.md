# 任务报告：thumbnail_url 端到端入库修复（缩略带宽优化生效）

## 1. 任务概述

用户在上一轮任务报告里看到一项高优先级后续建议：
> `PostImage.thumbnail_url` 列 DB 永远为空 = 缩略带宽优化暂时未生效。

用户确认「直接修复」后，本次任务要求彻底打通：
- 上传响应：`/upload/image` 返回的 `{ url, thumbnail_url }`
- 前端表单：`PostForm.tsx` 把两个 URL 一起保留
- 提交 payload：`POST /api/v1/posts` / `PUT /posts/{id}` 传对象数组
- 后端 schema：`PostCreate` / `PostUpdate` 接收两种结构
- 写入 DB：`PostImage.image_url` + `PostImage.thumbnail_url` 两个列同时有值
- 最终效果：详情页缩略图缩略请求 `thumb_xxx.jpg` 而不是原图，真正节省 ~90% 带宽/加载时间

同时必须 **100% 向后兼容**：旧前端（只传 image_urls 字符串数组）/ 旧本地草稿 / 手动 API 调用不能出问题。

## 2. 已完成内容

### 2.1 后端

1. **`app/schemas/post.py`**
   - 新增 `PostImageInput(image_url: str, thumbnail_url: str | None = None)` 入参对象
   - `PostCreate` 新增 `images: Optional[List[PostImageInput]]`（同时保留旧 `image_urls: Optional[List[str]]` 做兼容）
   - `PostUpdate` 同上，新增 images 字段 + 保留旧 image_urls
   - 新增 `@model_validator(mode='after') normalize_images_fields`，对 PostCreate / PostUpdate 两个类都生效：
     - 规则：`images` 优先（新版前端）；用户只传旧 `image_urls` 时自动转成 `List[PostImageInput](thumbnail_url=None)`；两者都传则 images 为准，把 image_urls 置 None 避免冲突；都不传保持 None
   - 新增 `pydantic.model_validator` import
2. **`app/api/posts.py` create_post**
   - 原 `if post_data.image_urls: for idx, image_url in enumerate(...)` → 改为 `if post_data.images: for idx, img in enumerate(post_data.images)` → 写入 `PostImage(..., image_url=img.image_url, thumbnail_url=img.thumbnail_url or None, sort_order=idx)`，两列同时入库
3. **`app/api/posts.py` update_post**（更复杂：因为 `update_data = post_data.model_dump(exclude_unset=True)`，model_validator 里用 `object.__setattr__` 改的字段不会标记为 "set"，可能出现在 `post_data.images` 但不在 `update_data`）
   - 把图片字段提取统一写成：先 pop `update_data` 里的 "images" 和 "image_urls" 两个 key；如果取到 None 再用 `post_data.images` 兜底（兼容 exclude_unset 场景）
   - 内部兼容 3 种输入形式：① 旧版 `List[str]` → 转成 `PostImage(image_url=item, thumbnail_url=None)`；② 新版 `List[PostImageInput]`（有 `.image_url` attribute）→ 取 `.image_url + .thumbnail_url`；③ 极端 dict[]（理论上不会出现，但 schema 解析失败仍可能触发）→ `.get()` 取值
   - 写入前统一按 enumerate(idx) 填 `sort_order` 和 `post_id`，db.add 入库

### 2.2 前端

1. **`services/posts.ts` CreatePostRequest 类型**
   - 新增 `images?: Array<{ image_url: string; thumbnail_url?: string }>`（注释【新版推荐】）
   - 保留 `image_urls?: string[]`（注释【旧版兼容】），双向兼容
2. **`components/PostForm.tsx`**
   - `PublishFormState.image_urls: string[]` → `images: Array<{image_url, thumbnail_url?}>`（注释：【新版】一张图同时携带原图+缩略图 URL）
   - `INITIAL_FORM.image_urls: []` → `images: []`
   - `isFormEffectivelyEmpty`：`form.image_urls.length===0` → `form.images.length===0`
   - **本地草稿迁移 `loadDraft`**：新增 `DRAFT-MIGRATION-1` 注释块，若解析出的 `parsed.form` 有旧 `image_urls` 但 `images` 为空/不存在，自动迁移到对象数组并 `delete form.image_urls`（避免下次再迁移）；保证历史草稿不丢失图片
   - **编辑态回显 useEffect**：`image_urls: (post.images ?? []).sort(...) .map(img.image_url)` → `images: .map(img => ({ image_url: img.image_url, thumbnail_url: img.thumbnail_url }))`，保留 DB 里已有的 thumbnail_url（编辑后再保存不会丢失）
   - **`handleImageChange` 上传**：`urls: string[] = []` → `uploaded: Array<{image_url, thumbnail_url?}> = []`；`resp.url` → `{image_url: resp.url, thumbnail_url: resp.thumbnail_url}` push；`handleFieldChange('image_urls', [...formData.image_urls, ...urls])` → `'images', [...formData.images, ...uploaded]`；数量判断 `formData.image_urls.length + files.length` → `formData.images.length + files.length`
   - **`handleRemoveImage(url: string)`**：改为按 `img.image_url !== imageUrl` 过滤保留；参数仍传字符串（原图 URL 唯一），调用点无需改
   - **提交 payload**：`image_urls: formData.image_urls.length>0 ? formData.image_urls : undefined` → 改为 `images: formData.images.length>0 ? formData.images : undefined`，让后端写入 thumbnail_url 列
   - **预览条渲染**：`formData.image_urls.map((url)` → `formData.images.map(img)`；`key={url}` → `key={img.image_url}`；`<img src={url}>` → `src={img.thumbnail_url \|\| img.image_url}`（上传阶段如果后端生成了缩略图，预览条先加载缩略图，快得多）；增加 `loading="lazy"`；数量判断 `formData.image_urls.length < MAX_IMAGES` → `formData.images.length < MAX_IMAGES`；`onClick handleRemoveImage(url)` → `handleRemoveImage(img.image_url)`

### 2.3 文档 & 提交

- TODO.md：在顶部新增「2026-08-07 执行任务：thumbnail_url 端到端入库修复」区块，共 8 条 checklist（7 项完成 + 1 项未执行 E2E）；最后更新时间改为 2026-08-07
- CHANGELOG.md：新增 `[2.2.9] - 2026-08-07`，含「修复 Bug 说明 + 4 段全链路步骤 + 一致性保证 + 校验」
- AIwork/ 新增本任务报告（8 节模板）
- Git 提交：完成所有修改并验证通过后提交（见 §7）

## 3. 未完成内容

- 端到端真实上传链路 E2E **未执行**：原因是前后端未启动（`uvicorn app.main:app --reload` + `npm run dev` 未运行），无法跑真实的「登录 → 上传 2 张图 → 发布 → 查 DB thumbnail_url 列 → Network 面板校验」链路。
- 数据迁移脚本（历史数据 `PostImage.thumbnail_url = NULL` 按 image_url 推断 `/uploads/thumb_<uuid>.<ext>` 补写）**未编写**：本任务只保证新入库数据不为空，历史帖子缩略图仍加载原图（功能正常，但不省带宽）；如需补全可写一条补写 SQL 或 python 脚本（§8 后续建议）。

## 4. 实现思路

### 4.1 核心难点：向后兼容（不破坏旧前端）

这是修复里的关键设计——不能为了修好新字段就把旧前端发布搞挂了。所以采用「**双字段+归一化 validator**」策略：

- **入参兼容**：旧前端只会传 `image_urls: string[]`，新前端传 `images: [{image_url, thumbnail_url?}]`；后端两个字段都接收
- **内部归一化**：PostCreate/PostUpdate 用 `@model_validator(mode='after')` 在 schema 层把旧字段转成新字段，让 posts.py 的写入侧**只关心 images 一个字段**，不用写一堆 if 判断前端版本；这样未来逐步淘汰旧 image_urls 字段时，写入侧代码不用改

### 4.2 另一难点：Pydantic v2 `exclude_unset` + `object.__setattr__`

update_post 里用 `post_data.model_dump(exclude_unset=True)` 来「只处理用户明确传入的字段，没传的不动」。但 model_validator 里用 `object.__setattr__` 写入的 images（由旧 image_urls 转过来的）**不会标记为 "set"**，所以 update_data dict 里没有 images 这个 key。为了不丢，update_post 图片段的提取逻辑写成：

```
for key in ("images", "image_urls"):
    if key in update_data: images_value = update_data.pop(key); break
if images_value is None and post_data.images is not None:
    images_value = post_data.images  # 兜底：model_validator 生成的新字段
```

这样 **用户传哪个都能拿到**。

### 4.3 前端草稿迁移：用户历史本地草稿不能丢

用户发布页可能上次写到一半关了页面，localStorage 里存的是旧结构 `form.image_urls = ['/uploads/a.jpg']`（没有 `images` 字段）。如果直接改 PublishFormState，`isFormEffectivelyEmpty(parsed.form)` 会按新结构 `images.length === 0` 判断成 true → 草稿被 `return null` 掉，用户以为草稿没了，会投诉。

解决：在 `loadDraft` 里加一次「迁移钩子」，发现旧结构存在就自动转 `images` 字段并 `delete form.image_urls`，同时写回本地存储，下次进来就是新结构。

## 5. 修改文件

### 后端 2 个

1. `backend/app/schemas/post.py`（#L1 新增 model_validator import；#L59-L66 新增 PostImageInput；#L80-L180 PostCreate/PostUpdate 新增 images + normalize_images_fields validator）
2. `backend/app/api/posts.py`（#L474-L486 create_post 写 thumbnail_url；#L607-L658 update_post 重写图片提取+兼容三种输入）

### 前端 2 个

3. `frontend/src/services/posts.ts`（#L13-L36 CreatePostRequest 新增 images 字段类型）
4. `frontend/src/components/PostForm.tsx`（8 处修改：interface/INITIAL_FORM/isEmpty/草稿迁移/编辑态回显/handleImageChange/handleRemoveImage/payload/预览渲染）

### 文档 3 个

5. `TODO.md`：新增顶部「thumbnail_url 端到端入库修复」区块
6. `CHANGELOG.md`：新增 [2.2.9] 2026-08-07
7. `AIwork/thumbnail_url端到端入库修复任务报告.md`（本文件）

## 6. 影响范围

| 模块 | 影响 | 风险 |
|---|---|---|
| 帖子创建接口 POST /posts | 新增接收 images 字段，同时保留旧 image_urls | 极低：validator 归一化，旧前端传旧字段、新前端传新字段都正常 |
| 帖子更新接口 PUT /posts/{id} | 同上，图片提取逻辑兼容三种输入（str[] / PostImageInput[] / dict[]） | 低：update_data 兜底取 post_data.images，保证不丢字段 |
| 前端 PostForm 发布页 | formData 结构从 `string[]` 变对象数组；草稿迁移；预览缩略优化 | 极低：loadDraft 自动迁移旧草稿；TSC 全量类型保证调用点不遗漏 |
| 其他图片接口（上传 / 首页 / 详情页 / 评论） | 不变：上传接口没动；详情页缩略缩略优化代码 2.2.8 已写好，等待 DB 有 thumbnail_url 就生效 | 无 |
| 历史帖子数据 | PostImage.thumbnail_url 列仍为 NULL（本次不做迁移脚本） | 无：代码里 `img.thumbnail_url \|\| img.image_url` 保证回退原图，历史内容正常显示 |

**破坏性变更：零。** 所有兼容都是添加式的，不存在任何 break。

## 7. 测试与验证

### 7.1 已执行（静态 + 单元样例，全部通过）

1. **后端 Schema 导入 + 归一化验证**（PowerShell，`backend/.venv` 执行 8 行 Python）：
   - `PostCreate.model_validate({'image_urls': ['/u/a.jpg', '/u/b.jpg']})` → `len(c1.images) == 2` ✅
   - `PostCreate.model_validate({'images': [{'image_url': '/u/a.jpg', 'thumbnail_url': '/u/t.jpg'}]})` → `images[0].thumbnail_url == '/u/t.jpg'` ✅
   - `PostUpdate.model_validate({'image_urls': ['/u/x.jpg']})` → 转 images 成功 ✅
   - `PostUpdate.model_validate({'images': [{'image_url': '/u/y.jpg'}]})` ✅
2. **后端 API import 检查**：`from app.api.posts import create_post, update_post` 成功，无 ImportError ✅
3. **前端 TypeScript 全量类型检查**：`cd frontend; npx tsc -p tsconfig.json --noEmit` → 0 错误（PostForm 35+ 处修改不引发任何 TS 报错）✅

### 7.2 未执行（前后端未启动；建议 4 步 E2E 回归清单）

环境启动后按下面的清单手动跑一遍即可闭环：

```powershell
# 启动后端
$env:APP_ENV = "opengauss"; cd backend; .venv\Scripts\uvicorn.exe app.main:app --reload
# 启动前端（新终端）
cd frontend; npm run dev
```

1. **发布新帖 2 张图** → 登录 user1 → 发布页选择 2 张真实 JPG → 提交 → toast 成功
2. **验证 DB** → 用 `_check_db.py` 或 SQL：`SELECT image_url, thumbnail_url, sort_order FROM post_images ORDER BY id DESC LIMIT 2;` → 期望：两列都非空，thumbnail_url 前缀 `/uploads/thumb_` 正确
3. **Network 面板验证** → 打开刚才发布的帖子详情页 → F12 Network 过滤 `thumb_` → 期望 2 个 `thumb_xxx.jpg` 成功，大小 ~30-80KB（不是 2-5MB 的原图）
4. **编辑保存不丢缩略图** → 点编辑 → 不增删图直接保存 → 回查 DB 同一 post_id 的 post_images → 期望 thumbnail_url 仍不为空（证明编辑态回显和再次保存未丢失）

### 7.3 没运行 pytest 的原因

与前两次任务一致：本地未配置独立 openGauss 测试库 + `TEST_DATABASE_URL` 环境变量，直接运行 pytest 会被 `conftest.py` RuntimeError 主动拦住，防止误伤开发数据库。

## 8. 后续建议

1. **历史 PostImage 补写 thumbnail_url**（可选，高收益）：现有历史数据 `thumbnail_url = NULL`，详情页缩略还在加载原图。可写一条 SQL 一次性补全：
   ```sql
   UPDATE post_image SET thumbnail_url = '/uploads/thumb_' || substring(image_url from '/uploads/(.*)$')
   WHERE thumbnail_url IS NULL AND image_url LIKE '/uploads/%';
   ```
   （不区分 openGauss 语法小差异）
2. **评论 / 评价图片复用本模式**：如果未来产品加「评论配图」或「地点评价配图」，直接复用 `PostImage` 模式 + upload 接口 + thumbnail_url 写库，不要再走「只传 image_urls 字符串」的老路径
3. **上传后异步生成多种尺寸**：目前缩略图固定 300×300，如未来做卡片缩略图布局（HomePage 封面图用），可在 upload.py 同步生成 180×180 `list_thumb_xxx.jpg` 和 64×64 `avatar_thumb_xxx.jpg`，入参 PostImageInput 扩展对应字段即可
4. **上传失败回滚 / 清理**：发布失败或用户删除图片时，上传到 backend/uploads 的文件目前不会删，长期会有「孤儿文件」。建议未来引入「图片生命周期服务」：上传后先放 temp 目录，24 小时未绑定 post_id 就自动清理；删除 post 时级联清理文件
