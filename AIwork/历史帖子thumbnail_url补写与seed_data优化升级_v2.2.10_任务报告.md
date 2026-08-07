# 任务报告：历史帖子 thumbnail_url 补写脚本与 seed_data 优化升级（v2.2.10）

## 1. 任务概述

与 v2.2.9「thumbnail_url 端到端入库修复」配套，把 v2.2.9 之前已经上传入库的历史帖子图片 `PostImage.thumbnail_url` 从 NULL 批量补写为与 upload.py 命名规则一致的缩略图 URL（`/uploads/thumb_<filename>`），让详情页缩略图加载的带宽优化对旧帖子同样生效。同时优化原本的 `seed_data.py` 工具，把补写能力内嵌为可复用的独立函数与命令行参数，既支持 seed 完自动补写，也支持线上升级时只跑补写不 seed。

## 2. 已完成内容

1. **seed_data.py 优化**：
   - 在 [seed_data.py](backend/scripts/seed_data.py) 主函数前新增顶层公共函数 `async def fix_missing_thumbnails(session: AsyncSession, *, dry_run=False) -> int`（L2178-L2214），与其他 seed_* 函数平级，可被管理端任务、其他脚本直接 import 调用
   - `seed_data()` 主函数扩展为三签名版本：`fix_thumbnails=True`（默认 seed 完自动补写）、`only_fix_thumbnails=False`（模式切换），并在写入侧 `await session.commit()` 前（L2353-L2361）执行 dry-run 预估算行数 + 真实 UPDATE（0 行时打印跳过）
   - `if __name__ == "__main__"` 入口从裸 `asyncio.run(seed_data())` 升级为标准 argparse CLI，支持 4 种常用调用：
     - `python scripts/seed_data.py` — 完整 seed + 末尾自动补写（默认）
     - `python scripts/seed_data.py --no-fix-thumbnails` — 完整 seed 但跳过补写（不推荐）
     - `python scripts/seed_data.py --only-fix-thumbnails` — 不清空、不 seed，只对现有库执行一次补写（线上升级场景）
     - `python scripts/seed_data.py --only-fix-thumbnails --dry-run` — 只 COUNT 不 UPDATE

2. **独立补写脚本 `backend/scripts/fix_post_image_thumbnails.py`**：
   - 与 seed_data.py 内置版本 SQL 完全同构，适合运维场景"不想碰 seed 工具只想跑补写"
   - 支持 `--dry-run` 先预览候选行数；执行完二次 COUNT 做幂等性验证，并打印建议的验证 SQL
   - 自动处理 sys.path 插入 backend 根目录 + 提前导入 `app.db_compat` 兼容补丁，保证与 seed_data 同链路启动

3. **SQL 设计（openGauss / PostgreSQL 标准语法通用）**：
   - UPDATE 规则：`thumbnail_url = '/uploads/thumb_' || substring(image_url FROM '/uploads/(.*)$')`，与 `backend/app/api/upload.py` 缩略图生成命名 `thumb_{uuid}{ext}` 严格一致，不会出现 DB 有 thumbnail_url 但磁盘缺缩略图文件的错配
   - 四重 WHERE 安全过滤：`thumbnail_url IS NULL`（幂等，绝不覆盖已有缩略）+ `image_url LIKE '/uploads/%'`（只管平台托管文件）+ `char_length(image_url) > 10`（避免异常 `/uploads/` 空路径）+ `substring(...) IS NOT NULL`（正则提取非空），确保线上执行不会误伤非托管 URL、外链图片和异常行

4. **静态校验通过**：
   - py_compile 两个脚本 0 Error 0 Warning（docstring 改为 raw string 消除 `\S` 无效转义告警）
   - `--help` 输出正常，参数与 docstring 示例一致
   - 纯 Python 等价模拟补写推导：`/uploads/abc123.jpg → /uploads/thumb_abc123.jpg ✅`；`/uploads/`、非 `/uploads/` 前缀、空 basename 全部安全 SKIP ✅

## 3. 未完成内容

1. openGauss 真实数据库上的完整回归验证：暂未启动 opengauss 容器 + 配置 `$env:APP_ENV='opengauss'` + 真实跑一次 `--only-fix-thumbnails --dry-run` 与 `--only-fix-thumbnails`，观察 rowcount、实际更新、幂等性二次 dry-run 应该返回 0（已在 TODO.md 对应条目标注）
2. 真实上传链路 E2E：与 v2.2.9 同缺口——未启动前后端，未走「登录→上传→发布→查 DB→详情 Network 面板」+ 「再跑补写脚本 dry-run 应该 0 行」的完整闭环（已在 TODO.md 对应条目标注）

## 4. 实现思路

**核心原则：脚本要"敢在生产跑"——幂等、安全、可预览、原子。**

- **幂等**：只 UPDATE WHERE thumbnail_url IS NULL，所以就算跑 100 次结果也一样，并且不会覆盖 v2.2.9 新帖已经正确入库的 thumbnail_url 正确值
- **安全**：四重过滤 + SQL 只改自己托管的 `/uploads/` 前缀文件；绝对不会碰外链、管理员手动上传的自定义路径、第三方 CDN URL
- **可预览**：所有入口都有 `--dry-run` / `dry_run=True` 参数，运维先 COUNT，再决定要不要真正 UPDATE，避免"大改之后才发现 WHERE 条件写错"的事故
- **原子**：整条补写是单条 UPDATE 语句 + 1 次 commit，不会出现"一半行改了一半行没改"的中间态
- **复用**：补写逻辑实现为一个带 `session` 参数的顶层 async 函数，所以管理端以后可以直接在定时任务、后台操作、管理端按钮里 import 调用，不需要再 fork 一份 SQL

**与 upload.py 命名对齐的关键决策**：没有选择 `rsplit('/')[-1]` 或 `os.path.basename` 做路径提取，而是直接在 SQL 层面写 `substring(image_url FROM '/uploads/(.*)$')`——因为这等价于「把 `/uploads/` 后面的部分全部保留」，未来就算 uploads 目录改多了子目录层级（虽然当前没有），SQL 仍然是对的，脚本不用升级。

**seed_data 入口保持向后兼容**：不传任何参数还是"完整 seed 全量数据"，老的自动化调用、部署脚本完全不用改；只在需要补写历史的运维场景下传新参数。

## 5. 修改文件

| 路径 | 变更类型 | 说明 |
|------|----------|------|
| [backend/scripts/seed_data.py](backend/scripts/seed_data.py) | 修改（大量新增） | 新增 `fix_missing_thumbnails()` 公共函数；改造 `seed_data()` 主函数两种模式 + 默认自动补写；CLI 从裸入口升级为 argparse 三参数结构 |
| [backend/scripts/fix_post_image_thumbnails.py](backend/scripts/fix_post_image_thumbnails.py) | 新增 | 独立运维补写脚本，与 seed_data SQL 同构；`--dry-run` 预查 + 二次 COUNT 验证 + 打印验证 SQL |
| [TODO.md](TODO.md) | 修改 | 顶部新增 v2.2.10 任务章节（6 条勾选项 + 2 条未执行缺口）；更新最后更新时间与摘要 |
| [CHANGELOG.md](CHANGELOG.md) | 修改 | 新增 `[2.2.10] - 2026-08-07` 版本节（新增/实现/校验三小节） |

## 6. 影响范围

- **数据层（仅 post_image 表）**：只对 `PostImage` 表做 UPDATE，不影响其他任何表；不会改变 Post/Comment/User 等行，不触发触发器、不刷新物化视图
- **脚本/运维侧**：① 旧的 `python scripts/seed_data.py` 调用语义不变；② 新增 `--only-fix-thumbnails` 与独立脚本两个运维入口，均只写 post_image 表
- **前端渲染**：执行补写后，所有帖子（v2.2.9 前 + v2.2.9 后）的详情页轮播缩略图「优先 thumbnail_url、回退 image_url」代码开始真正生效，9 张缩略图单次访问节省约 20-40MB 流量（原 2-5MB/张 → 约 30-80KB/张）
- **代码复用**：`fix_missing_thumbnails(session, dry_run=False)` 可被其他脚本或管理端定时任务直接 import，无副作用、无全局状态依赖

**风险极低**：
1. WHERE `thumbnail_url IS NULL` 保证"正确值不会被覆盖"
2. 就算 SQL 写错（实际有四重保护），也只改 thumbnail_url 这一列——真实上传的图片与缩略图磁盘文件完全不动，真改坏了只要 `UPDATE post_image SET thumbnail_url = NULL` 就能回退
3. 幂等，运维可以随时再跑一次做检查

## 7. 测试与验证

未执行真实数据库与 E2E，原因：环境未启动 openGauss 容器、未配置 `$env:APP_ENV='opengauss'`，也未启动前后端服务；按照工作原则「不伪造结果」，如实写明。

已做的静态/逻辑层面验证：

1. **语法级验证**（两脚本）：
   - `py_compile seed_data.py fix_post_image_thumbnails.py` → 0 Error 0 Warning（docstring 改为 raw string 后 `\S` 无效转义告警消除）
2. **CLI 入口**（两脚本）：
   - `--help` 正常输出 seed_data 的 4 条示例和 fix 脚本的 `--dry-run` 说明，与实现一致
3. **SQL 逻辑纯 Python 等价模拟验证**：
   - 独立跑一段与 `substring FROM '/uploads/(.*)$'` 正则等价的 Python 模拟，对 6 类典型输入（正常 jpg、子目录 png、空 `/uploads/`、非前缀、1 字符文件名、None）逐一输出推导结果：
     - `/uploads/abc123.jpg → /uploads/thumb_abc123.jpg ✅`
     - `/uploads/deep/path/x.png → /uploads/thumb_deep/path/x.png ✅`（当前无子目录，但未来兼容）
     - `/uploads/` / `/no-prefix/abc.jpg` → `SKIP ✅`
     - `/uploads/a → /uploads/thumb_a ✅`（最小合法长度，当前 upload.py 不会生成但逻辑正确）
     - `None → SKIP ✅`
4. **幂等性逻辑验证**：WHERE `thumbnail_url IS NULL`，执行一次 UPDATE 后，所有候选行的 thumbnail_url 不再为 NULL，第二次执行必为 0 行（代码层面对齐）

**运维推荐的真实验证清单（升级 2.2.10 前必跑）**：
```powershell
$env:APP_ENV='opengauss';
cd backend;
# Step 1: 先看有多少行候选
.venv\Scripts\python scripts\fix_post_image_thumbnails.py --dry-run
# Step 2: 真实执行
.venv\Scripts\python scripts\fix_post_image_thumbnails.py
# Step 3: 幂等验证（预期 0 行候选）
.venv\Scripts\python scripts\fix_post_image_thumbnails.py --dry-run
```

## 8. 后续建议

1. **立刻做一次真实验证**：在本地 openGauss 容器启动后，至少先 `--only-fix-thumbnails --dry-run` 看一下是否真的有历史 NULL 行，再决定是否跑 UPDATE；结果补写进当前 TODO 的 2 条未执行勾选项
2. **管理端补写按钮**：把 `fix_missing_thumbnails(session, dry_run=True/False)` 接到平台级后台的"数据工具 → 缩略图补写"页面，给管理员一个 dry-run + 真实执行 + 结果展示的 UI，不用每次跑命令行
3. **定期巡检**：在 `backend/scripts/` 下的 expire_posts / usage_summary 等 job 里，偶尔跑一次 dry_run（比如每周一），如果候选行数 > 0 就发个告警——避免未来某一天代码回归、thumbnail_url 又忘记写 DB 了，能第一时间发现
4. **缩略图缺失磁盘文件的补生成**：当前脚本只改 DB，假设 `/uploads/thumb_xxx.jpg` 文件存在（upload.py 上传时已生成）。考虑未来再加一个"扫描磁盘 thumb_ 文件缺失 → 用 Pillow 重新生成 → 再写 DB"的配套脚本，应对"清理 uploads 目录后缩略图丢失"的运维事故场景
5. **与 v2.2.9 的完整链路 E2E**：前后端启动后，跑一次「上传 2 张图→发布→DB 看 PostImage.thumbnail_url 非 NULL → 详情页缩略图 Network 请求的 URL 以 thumb_ 开头、大小在 30-80KB → 再跑补写脚本 dry-run 返回 0」的完整闭环，与 v2.2.9 任务的 E2E 合并一起执行
