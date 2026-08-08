# 注册阶段强制教育邮箱 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `/api/v1/auth/register` 邮箱注册和 `/api/v1/auth/wechat/register` 微信注册两条链路中，后端强制要求用户填写所选学校允许的教育邮箱域名（或运营豁免域 momentcampus.com），不再允许用非教育域名的 gmail/qq/163 等绕过前端注册进租户；同时微信注册不再允许 email 为空时自动生成 `wx_xxx@momentcampus.local` 占位邮箱，改为 400 明确提示"请填写所选学校教育邮箱"。

**Architecture:** 抽取单一后端校验辅助函数 `ensure_email_matches_school_domains(db, school_id, email, *, require_email=True)` 放 `app/services/school_domain.py`，统一做四件事：(1) require_email=True 且 email 空 → 400；(2) 解析 email 域名，若域名在全局豁免域 `ALLOWED_NON_CAMPUS_DOMAINS = {"momentcampus.com"}` → 直接放行（供运营账号注册）；(3) 查询目标学校的 SchoolDomain 有效域名列表，若列表为空（极端未配置情况）→ 放行（避免租户启动初期死锁）；(4) 邮箱域名不在 SchoolDomain 列表 → 400 `请使用 {school_name} 的官方教育邮箱注册（或 momentcampus.com 运营邮箱）`。然后在 auth.py register 和 wechat_auth.py wechat_register 两处分别调用一次此 helper，规则完全同源。

**Tech Stack:** FastAPI, openGauss 7.0, SQLAlchemy 2.x async ORM, pytest-asyncio, httpx AsyncClient (ASGITransport)

---

## File Structure

- **Modify** `backend/app/services/__init__.py`（或直接新建）：`backend/app/services/school_domain.py` — 新增 `ALLOWED_NON_CAMPUS_DOMAINS` 常量 + `ensure_email_matches_school_domains()` 异步校验函数 + 可选同步纯函数辅助 `_parse_email_domain(email) -> str | None`
- **Modify** `backend/app/api/auth.py#L80-L120` — 在 `register()` 完成 school_id 解析后、邮箱查重前插入 helper 调用
- **Modify** `backend/app/api/wechat_auth.py#L276-L360` — 在 `wechat_register()` 开始处完成 school 校验后，user_email 确定分支：① 直接把空 email fallback `wx_xxx@momentcampus.local` 的 else 分支整段删掉，改为 BadRequestException；② 在 email 确定（data.email 有值）后立即调用 helper
- **Modify** `backend/tests/test_auth.py` — 新增 4 条注册邮箱域名 pytest
  - `test_register_email_domain_mismatch_returns_400`：选 jiangnan 学校 + 传 random@gmail.com → 400 detail 含"请使用江南大学的官方教育邮箱"
  - `test_register_email_domain_example_match_returns_200`：选 jiangnan + `newuser@example.jiangnan.edu.cn` → 200 campus_verified=False user.email 正确
  - `test_register_momentcampus_com_whitelist_returns_200`：选 fudan + `ops_fudan@momentcampus.com`（豁免域，无需命中复旦 SchoolDomain）→ 200
  - `test_register_school_with_empty_domains_allows_any_email`：若某学校删光 SchoolDomain（暂时手动模拟：conftest 建 school_with_no_domains fixture 或临时 DELETE FROM school_domains WHERE school_id=X…）+ `anybody@outlook.com` → 200
- **Modify** `backend/tests/test_wechat_auth.py` — 新增 3 条微信注册邮箱域名 pytest
  - `test_wechat_register_empty_email_now_returns_400`：data.email 完全不传（或者空字符串）→ 400 "请填写所选学校的教育邮箱"
  - `test_wechat_register_email_domain_mismatch_returns_400`：选 school_id=jiangnan + email=`user@gmail.com` + 合法 binding_ticket → 400 教育域名不匹配
  - `test_wechat_register_example_email_works`：选 zju + `new_zju@example.zju.edu.cn` + 合法 binding_ticket → 200 user 里 email 正确且 campus_verified=False
- **文档交付物**：`AIwork/注册阶段强制教育邮箱校验_任务报告.md`（按 8 节模板，§7.1 pytest 结果，§7.2 HTTP 仿真结果）；`TODO.md` 头部最后更新 + 插入 8 条新任务章节；`CHANGELOG.md` 顶部新版本 [2.2.16]

---

## Task 1: 新增 school_domain helper 模块 + failing tests（auth 侧 4 条）

**Files:**
- Create: `backend/app/services/school_domain.py`
- Modify: `backend/tests/test_auth.py`

**TDD 顺序：先写 failing tests 跑 → 失败 → 再写 helper + 接入 → 再跑通过**

- [ ] **Step 1: 在 backend/tests/test_auth.py 文件末尾插入 4 条注册邮箱域名用例**

确保每条都选"江南大学"或新建空域名学校：

```python
@pytest.mark.asyncio
async def test_register_email_domain_mismatch_returns_400(client: AsyncClient, db_session: AsyncSession):
    """普通注册：学校有教育域名，但传了 gmail → 400 拦。"""
    schools_resp = await client.get("/api/v1/schools")
    assert schools_resp.status_code == 200
    schools = schools_resp.json()
    jiangnan = next(s for s in schools if s["code"] == "jiangnan")

    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "random_jiangnan@gmail.com",
            "password": "pass12345",
            "nickname": "gmail用户",
            "school_id": jiangnan["id"],
        },
    )
    assert resp.status_code == 400
    assert "江南大学的官方教育邮箱" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_register_email_domain_example_match_returns_200(client: AsyncClient, db_session: AsyncSession):
    """普通注册：example.jiangnan.edu.cn → 合法，200。"""
    schools_resp = await client.get("/api/v1/schools")
    jiangnan = next(s for s in schools_resp.json() if s["code"] == "jiangnan")
    unique_email = f"new_user_{__import__('time').time_ns()}@example.jiangnan.edu.cn"
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": "pass12345",
            "nickname": "教育邮箱新生",
            "school_id": jiangnan["id"],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"] == unique_email
    assert body["user"]["campus_verified"] is False


@pytest.mark.asyncio
async def test_register_momentcampus_com_whitelist_returns_200(client: AsyncClient, db_session: AsyncSession):
    """普通注册：momentcampus.com 豁免域（运营邮箱）→ 无需命中复旦 SchoolDomain 也能注册进复旦。"""
    schools_resp = await client.get("/api/v1/schools")
    fudan = next(s for s in schools_resp.json() if s["code"] == "fudan")
    unique_email = f"ops_fudan_{__import__('time').time_ns()}@momentcampus.com"
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": "pass12345",
            "nickname": "复旦运营小号",
            "school_id": fudan["id"],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["user"]["email"] == unique_email
    assert resp.json()["user"]["campus_verified"] is False


@pytest.mark.asyncio
async def test_register_school_with_empty_domains_allows_any_email(client: AsyncClient, db_session: AsyncSession):
    """普通注册：如果某学校暂时清空了所有 SchoolDomain（配置期极端场景）→ 允许任意邮箱注册，不 400 死锁。"""
    schools_resp = await client.get("/api/v1/schools")
    zju = next(s for s in schools_resp.json() if s["code"] == "zju")
    # 手动清空 zju 的 SchoolDomain（注意测试事务隔离，最后不提交，会自动回滚）
    from app.models.school_domain import SchoolDomain as SD
    from sqlalchemy import delete as sql_delete
    await db_session.execute(sql_delete(SD).where(SD.school_id == zju["id"]))
    await db_session.flush()

    unique_email = f"temp_zju_user_{__import__('time').time_ns()}@outlook.com"
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": "pass12345",
            "nickname": "临时用户（空域名阶段）",
            "school_id": zju["id"],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["user"]["email"] == unique_email
```

- [ ] **Step 2: 运行 tests → 预期 FAIL**

命令（PowerShell）：

```powershell
cd backend
$env:APP_ENV='opengauss'
$env:TEST_DATABASE_URL='postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test'
.venv\Scripts\python.exe -m pytest tests/test_auth.py::test_register_email_domain_mismatch_returns_400 tests/test_auth.py::test_register_email_domain_example_match_returns_200 tests/test_auth.py::test_register_momentcampus_com_whitelist_returns_200 tests/test_auth.py::test_register_school_with_empty_domains_allows_any_email -v --asyncio-mode=auto
```

预期：
- `test_register_email_domain_mismatch_returns_400` → FAIL（当前实际行为是 200 成功创建 gmail 用户）
- `test_register_email_domain_example_match_returns_200` → PASS（本就允许）
- `test_register_momentcampus_com_whitelist_returns_200` → PASS（本就允许）
- `test_register_school_with_empty_domains_allows_any_email` → PASS（本就允许）

只有第一条会 fail，这正是我们期望的 failing test。

**仅 FAIL 的是 domain_mismatch**（证明当前后端确实允许非教育邮箱绕过）。如果 Example Match 反而 FAIL，检查 seed 数据。

- [ ] **Step 3: 新建 `backend/app/services/school_domain.py` 写 helper**

```python
"""学校教育域名校验：注册阶段强制命中 SchoolDomain 或全局豁免域。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException
from app.models.school import School
from app.models.school_domain import SchoolDomain


# 非校园邮箱但允许注册的全局豁免域名：平台运营专用、运维邮箱、系统通知等。
# 注意：momentcampus.local 是老数据占位域（旧微信注册 fallback），不在豁免列表——新注册一律不允许
ALLOWED_NON_CAMPUS_DOMAINS: frozenset[str] = frozenset({"momentcampus.com"})


def parse_email_domain(email: Optional[str]) -> Optional[str]:
    """安全解析邮箱域名（小写，None/空/@前为空都返回 None）。"""
    if not email or not isinstance(email, str):
        return None
    e = email.strip().lower()
    if "@" not in e:
        return None
    domain = e.rsplit("@", 1)[-1]
    return domain or None


async def ensure_email_matches_school_domains(
    db: AsyncSession,
    school_id: int,
    email: Optional[str],
    *,
    require_email: bool = True,
) -> None:
    """注册阶段的统一邮箱域名校验：

    Rules（按顺序）:
      1. require_email=True 且 email 空 → 400 请填写所选学校教育邮箱
      2. 解析域名；域名本身无效 → 400 请输入有效邮箱
      3. 域名 in ALLOWED_NON_CAMPUS_DOMAINS → 直接放行
      4. SELECT School WHERE id=school_id；不存在 → 404 学校不存在（上游 register 已检查，但本函数双保险）
      5. SELECT SchoolDomain WHERE school_id=X AND is_deleted=false → 列表为空 → 放行（避免配置期极端死锁）
      6. domain in 学校允许域名列表 → 放行；否则 400
    """
    # Rule 1
    if require_email and (not email or not str(email).strip()):
        raise BadRequestException(detail="请填写所选学校的教育邮箱")

    # Rule 2
    domain = parse_email_domain(email)
    if domain is None:
        raise BadRequestException(detail="请输入有效的邮箱地址")

    # Rule 3 运营豁免
    if domain in ALLOWED_NON_CAMPUS_DOMAINS:
        return

    # Rule 4 学校存在性（双保险，读 school.name 用于 400 文案）
    school = (await db.execute(
        select(School).where(School.id == int(school_id), School.is_active == True)  # noqa: E712
    )).scalar_one_or_none()
    if school is None:
        raise BadRequestException(detail="所选学校不存在")

    # Rule 5 查 SchoolDomain 列表
    rows = (await db.execute(
        select(SchoolDomain.domain).where(
            SchoolDomain.school_id == school.id,
            SchoolDomain.is_deleted == False,  # noqa: E712
        )
    )).scalars().all()
    if not rows:
        # 极端场景：学校还没配置任何允许域名 → 不卡死，放行任何邮箱，等运营配完 SchoolDomain 自动收紧
        return

    allowed = {d.lower() for d in rows if d}
    if domain not in allowed:
        readable = "、".join(sorted(allowed))
        raise BadRequestException(
            detail=(
                f"请使用{school.name}的官方教育邮箱注册（@ {readable}）"
                "；或使用 @momentcampus.com 运营邮箱。"
                "若为该校学生但邮箱后缀不在列表中，请联系该校管理员添加附加域名。"
            )
        )
```

- [ ] **Step 4: 在 `backend/app/api/auth.py register()` 插入调用**

放在"邮箱已存在检查"之前（因为这是更基础的域名/格式校验，比"已注册"更优先）：

```python
    from app.services.school_domain import ensure_email_matches_school_domains
    await ensure_email_matches_school_domains(db, school_id, data.email)

    # 检查邮箱是否已存在
    result = await db.execute(select(User).where(User.email == data.email))
    existing_user = result.scalar_one_or_none()
```

注意 import 放在函数内部（避免循环依赖），或者在文件顶部 import（取决于 services 树是否已有成熟 import 约定）。

- [ ] **Step 5: 再次运行 Step 2 的 pytest 命令 → 预期 4/4 PASS**

Command 同 Step 2。若 `test_register_school_with_empty_domains_allows_any_email` 因事务影响其他用例，把 flush 换成 no_autoflush=False 后保证回滚；如果不行，可把该用例放独立 run 或在 DELETE 前先 SELECT 并断言原 rows≥1 确保测试有效。

---

## Task 2: 微信注册 `/wechat/register` 接入 helper + 移除空 email fallback（先写 3 条 failing tests）

**Files:**
- Modify: `backend/tests/test_wechat_auth.py`
- Modify: `backend/app/api/wechat_auth.py#L276-L360`

- [ ] **Step 1: 追加 3 条 failing tests 到 test_wechat_auth.py 末尾**

```python
@pytest.mark.asyncio
async def test_wechat_register_empty_email_now_returns_400(client: AsyncClient, db_session: AsyncSession):
    """微信注册：email 为空（或完全不传）→ 新行为：400，不再生成 wx_xxx@momentcampus.local。"""
    schools_resp = await client.get("/api/v1/schools")
    jiangnan = next(s for s in schools_resp.json() if s["code"] == "jiangnan")
    exchange_resp = await client.post(
        "/api/v1/auth/wechat/exchange",
        json={"code": "EMPTY_EMAIL_WECHAT_FOR_TEST"},
    )
    assert exchange_resp.status_code == 200
    ticket = exchange_resp.json()["binding_ticket"]

    register_resp = await client.post(
        "/api/v1/auth/wechat/register",
        json={
            "binding_ticket": ticket,
            "nickname": "空邮箱新微信用户",
            "school_id": jiangnan["id"],
            "password": "pass12345",
            # 故意不提供 email
        },
    )
    assert register_resp.status_code == 400
    assert "请填写所选学校的教育邮箱" in register_resp.json()["detail"]


@pytest.mark.asyncio
async def test_wechat_register_email_domain_mismatch_returns_400(client: AsyncClient, db_session: AsyncSession):
    """微信注册：email 合法格式但学校不允许（gmail）→ 400 学校官方教育邮箱提示。"""
    schools_resp = await client.get("/api/v1/schools")
    jiangnan = next(s for s in schools_resp.json() if s["code"] == "jiangnan")
    exchange_resp = await client.post(
        "/api/v1/auth/wechat/exchange",
        json={"code": "GMAIL_WECHAT_FOR_TEST"},
    )
    ticket = exchange_resp.json()["binding_ticket"]

    register_resp = await client.post(
        "/api/v1/auth/wechat/register",
        json={
            "binding_ticket": ticket,
            "nickname": "gmail微信用户",
            "school_id": jiangnan["id"],
            "password": "pass12345",
            "email": "wechat_gmail_user@gmail.com",
        },
    )
    assert register_resp.status_code == 400
    assert "江南大学的官方教育邮箱" in register_resp.json()["detail"]


@pytest.mark.asyncio
async def test_wechat_register_example_zju_email_works(client: AsyncClient, db_session: AsyncSession):
    """微信注册：浙大 example.zju.edu.cn 邮箱 → 200 成功，user 字段正确，campus_verified=False。"""
    schools_resp = await client.get("/api/v1/schools")
    zju = next(s for s in schools_resp.json() if s["code"] == "zju")
    exchange_resp = await client.post(
        "/api/v1/auth/wechat/exchange",
        json={"code": "ZJU_EXAMPLE_EMAIL_WECHAT_FOR_TEST"},
    )
    ticket = exchange_resp.json()["binding_ticket"]
    unique_email = f"zju_new_wx_{__import__('time').time_ns()}@example.zju.edu.cn"

    register_resp = await client.post(
        "/api/v1/auth/wechat/register",
        json={
            "binding_ticket": ticket,
            "nickname": "浙大新生微信",
            "school_id": zju["id"],
            "password": "pass12345",
            "email": unique_email,
        },
    )
    assert register_resp.status_code == 200
    body = register_resp.json()
    assert body["user"]["email"] == unique_email
    assert body["user"]["campus_verified"] is False
    assert "access_token" in body
```

- [ ] **Step 2: 运行这 3 条 → 预期 fail 2 条**

```powershell
cd backend
$env:APP_ENV='opengauss'
$env:TEST_DATABASE_URL='postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test'
.venv\Scripts\python.exe -m pytest tests/test_wechat_auth.py::test_wechat_register_empty_email_now_returns_400 tests/test_wechat_auth.py::test_wechat_register_email_domain_mismatch_returns_400 tests/test_wechat_auth.py::test_wechat_register_example_zju_email_works -v --asyncio-mode=auto
```

预期：
- `test_wechat_register_empty_email_now_returns_400` → FAIL（当前会 200 生成 momentcampus.local 占位邮箱）
- `test_wechat_register_email_domain_mismatch_returns_400` → FAIL（当前会 200 成功创建 gmail 用户）
- `test_wechat_register_example_zju_email_works` → PASS（本就允许）

- [ ] **Step 3: 修改 `backend/app/api/wechat_auth.py wechat_register()`**

**规则：**
1. 在 `if data.email:` 块前调用 helper：传 `email=data.email, require_email=True` → 空 email 立刻 400
2. 删除原有 `else: email = f"wx_{unique_id}@momentcampus.local"` 分支（helper 已经在 data.email 空时拦了，所以 else 实际不可达；但物理删除更干净，避免未来有人注释 helper 后 fallback 复活）
3. 有值时：先通过 helper → 再继续走 email_uniqueness_check → create User

插入位置：在 `school_result = await db.execute(...)`（学校存在性检查）通过之后，`if data.email:` 分支之前。

```python
    from app.services.school_domain import ensure_email_matches_school_domains
    await ensure_email_matches_school_domains(db, data.school_id, data.email)

    if data.email:
        email_check = await db.execute(select(User).where(User.email == data.email))
        if email_check.scalar_one_or_none() is not None:
            raise ConflictException(detail="该邮箱已被注册")
        email = data.email
    else:
        # require_email=True 在 helper 已拦了空 email；此分支理论不可达，留 500 级兜底
        raise BadRequestException(detail="请填写所选学校的教育邮箱")
```

- [ ] **Step 4: 再次运行 Step 2 pytest → 3/3 PASS**

---

## Task 3: 全量回归测试 + 链路仿真 + 文档交付 + Git commit

- [ ] **Step 1: 全量 pytest tests/test_auth.py tests/test_wechat_auth.py → 全部通过**

```powershell
cd backend
$env:APP_ENV='opengauss'
$env:TEST_DATABASE_URL='postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test'
.venv\Scripts\python.exe -m pytest tests/test_auth.py tests/test_wechat_auth.py -v --asyncio-mode=auto
```

预期：**≥36 passed**（原 29 + 新增 7 = 36）。

- [ ] **Step 2: HTTP 链路仿真（ASGITransport AsyncClient 独立脚本）验证 4 类邮箱 × 3 所学校 共 12 场景**

矩阵（"ji=jiangnan, fu=fudan, zj=zju"）：

| 邮箱类型 | 示例 | 江 | 复 | 浙 | 期望 |
|---|---|---|---|---|---|
| 命中主域名 | `x@jiangnan.edu.cn` | ✅ | ❌ | ❌ | 命中的那校 200；其他两校 400 |
| 命中附加 example 域 | `x@example.zju.edu.cn` | ❌ | ❌ | ✅ | 只有 zju 200；jiangnan/fudan 400 |
| 运营豁免域 | `ops@momentcampus.com` | ✅ | ✅ | ✅ | 三校都 200 |
| 普通非教育邮箱 | `x@163.com` | ❌ | ❌ | ❌ | 三校都 400 提示官方邮箱 |

脚本结构参考上轮的 `python -c` 命令；断言 400 场景必须包含"官方教育邮箱"字样且 status=400。

- [ ] **Step 3: TODO + CHANGELOG + 任务报告**

  - `TODO.md` 头部"最后更新时间：2026-08-08（注册阶段后端强制教育邮箱校验：auth.register & wechat.register 接入统一 SchoolDomain 校验；微信注册不再生成 wx_xxx@momentcampus.local 占位邮箱）"，然后插入 8 条 [x] 任务章节（本 plan 的 Task1-2-3 + 对应子步骤简述）。
  - `CHANGELOG.md` 顶部新增 `[2.2.16] - 2026-08-08`，两小节：**修复（注册阶段后端补 SchoolDomain 拦截 + 空邮箱 400；微信注册占位邮箱逻辑下线；豁免域 momentcampus.com）** 和 **校验（pytest 36/36 通过；HTTP 4×3=12 场景矩阵 PASS）**。
  - `AIwork/注册阶段后端强制教育邮箱校验_任务报告.md` 按 AIWORK_RULES.md 的 8 节结构真实记录。

- [ ] **Step 4: Git commit**

暂存：`backend/app/services/school_domain.py backend/app/api/auth.py backend/app/api/wechat_auth.py backend/tests/test_auth.py backend/tests/test_wechat_auth.py TODO.md CHANGELOG.md AIwork/注册阶段后端强制教育邮箱校验_任务报告.md`

提交信息（Conventional Commits）：`fix(auth)!: 注册阶段后端强制教育邮箱；微信注册下线空邮箱fallback占位邮箱`，Body 说明：
- 新增 services/school_domain.ensure_email_matches_school_domains：选学校→查 SchoolDomain→命中或豁免域 momentcampus.com 才放行；学校未配置域名则放行
- auth.py /wechat_auth.py 两接口统一接入
- wechat_register 删除 wx_xxx@momentcampus.local 自动生成逻辑（require_email=True 拦截空邮箱）
- tests 新增 7 条 pytest 用例，全量回归 36/36 PASS
- HTTP 4×3=12 链路矩阵仿真全部断言通过

`!` 表示破坏性变更（依赖微信注册不填邮箱的既有客户端会收到 400，但上轮前端已在 mode='wechat' 注册时要求填邮箱，所以小程序端不影响）。

---

## Self-Review

**Spec coverage:**
- [x] "加一下，注册阶段就得要求是教育邮箱" → Task 1 普通邮箱注册后端拦截 + Task 2 微信注册后端拦截，覆盖全部两条注册入口
- [x] 豁免运营域 momentcampus.com → ALLOWED_NON_CAMPUS_DOMAINS 常量 + test_register_momentcampus_com_whitelist_returns_200 覆盖
- [x] 未配置域名的新学校极端场景 → test_register_school_with_empty_domains_allows_any_email 覆盖
- [x] 微信注册历史遗留空邮箱 → test_wechat_register_empty_email_now_returns_400 + 代码物理删除 fallback 分支

**Placeholder scan:** 无 TBD / TODO / "实现"字眼；Step 代码块全部含可直接复制的真实 pytest + Python helper 实现 + 命令行。

**Type consistency:** helper 名 `ensure_email_matches_school_domains` 在两个路由中写法完全一致；常量 `ALLOWED_NON_CAMPUS_DOMAINS` 统一引用；测试文件名 `test_register_*` / `test_wechat_register_*` 前缀清晰。

Plan complete and saved to `docs/superpowers/plans/2026-08-08-register-force-campus-email.md`. 由于本轮改动集中、跨文件少且严格 TDD 有步骤，推荐 **Inline Execution**（用 executing-plans 走 3 个 Task 分批验证）。
