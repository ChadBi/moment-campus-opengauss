"""微信认证 API 测试。

测试范围：
- 微信 code2Session（模拟模式）
- exchange（已绑定/未绑定）
- bind-existing（绑定已有账号）
- register（微信新用户注册）
- identities 管理（查看/添加/解绑）
- sessions 管理（查看/撤销/全部撤销）
- 双读兼容：现有邮箱登录仍正常工作
"""
import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.user_auth_identity import UserAuthIdentity
from app.models.auth_session import AuthSession, BindingTicket
from app.core.security import get_password_hash, verify_password
from app.services.wechat import MOCK_STATIC_OPENID


@pytest.mark.asyncio
async def test_wechat_exchange_unbound(client: AsyncClient, test_school: dict):
    """未绑定用户调用 exchange → 返回 binding_ticket。"""
    response = await client.post(
        "/api/v1/auth/wechat/exchange",
        json={"code": "test_code_123456"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "binding_required"
    assert "binding_ticket" in data
    assert data["expires_in"] == 300
    assert len(data["binding_ticket"]) > 30


@pytest.mark.asyncio
async def test_wechat_exchange_bound(
    client: AsyncClient, test_user: dict, db_session: AsyncSession
):
    """已绑定用户调用 exchange → 直接返回 JWT。"""
    # 模拟模式下 openid 固定为 MOCK_STATIC_OPENID（与 code 无关，模拟真实 code2Session 行为：
    # 同一微信用户无论传什么临时 code 都会返回同一个稳定 openid）
    test_code = "test_code_for_bound_user"
    expected_openid = MOCK_STATIC_OPENID

    # 先给测试用户绑定一个微信身份
    identity = UserAuthIdentity(
        user_id=test_user["id"],
        identity_type="wechat_miniprogram",
        identity_key=expected_openid,
        openid=expected_openid,
        last_used_at=datetime.now(),
    )
    db_session.add(identity)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/wechat/exchange",
        json={"code": test_code},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "authenticated"
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user_id"] == test_user["id"]
    assert "user" in data
    assert data["user"]["id"] == test_user["id"]


@pytest.mark.asyncio
async def test_wechat_bind_existing_success(
    client: AsyncClient, test_user: dict, db_session: AsyncSession
):
    """绑定已有 Web 账号 → 成功。"""
    # 1. 先获取 binding_ticket
    exchange_resp = await client.post(
        "/api/v1/auth/wechat/exchange",
        json={"code": "bind_test_code"},
    )
    assert exchange_resp.status_code == 200
    ticket = exchange_resp.json()["binding_ticket"]

    # 2. 用 binding_ticket + 邮箱密码绑定
    bind_resp = await client.post(
        "/api/v1/auth/wechat/bind-existing",
        json={
            "binding_ticket": ticket,
            "email": test_user["email"],
            "password": test_user["password"],
        },
    )
    assert bind_resp.status_code == 200
    data = bind_resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user_id"] == test_user["id"]
    assert "user" in data
    assert data["user"]["id"] == test_user["id"]

    # 3. 验证身份已创建
    identity_check = await db_session.execute(
        select(UserAuthIdentity).where(
            UserAuthIdentity.user_id == test_user["id"],
            UserAuthIdentity.identity_type == "wechat_miniprogram",
        )
    )
    assert identity_check.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_wechat_bind_existing_wrong_password(
    client: AsyncClient, test_user: dict
):
    """绑定失败：密码错误 → 401。"""
    exchange_resp = await client.post(
        "/api/v1/auth/wechat/exchange",
        json={"code": "wrong_pwd_code"},
    )
    ticket = exchange_resp.json()["binding_ticket"]

    response = await client.post(
        "/api/v1/auth/wechat/bind-existing",
        json={
            "binding_ticket": ticket,
            "email": test_user["email"],
            "password": "wrongpassword",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_wechat_bind_existing_expired_ticket(client: AsyncClient, test_user: dict, db_session: AsyncSession):
    """绑定失败：过期的 binding_ticket → 400。"""
    # 创建一个已过期的 binding_ticket
    from app.services.wechat import _hash_token
    expired_ticket = "expired_ticket_value_12345678901234567890"
    bt = BindingTicket(
        ticket_hash=_hash_token(expired_ticket),
        openid="expired_openid",
        expires_at=datetime.now() - timedelta(seconds=10),
        client_ip="127.0.0.1",
    )
    db_session.add(bt)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/wechat/bind-existing",
        json={
            "binding_ticket": expired_ticket,
            "email": test_user["email"],
            "password": test_user["password"],
        },
    )
    assert response.status_code == 400
    assert "无效或已过期" in response.json()["detail"]


@pytest.mark.asyncio
async def test_bind_existing_account_already_has_wechat_identity_fails(
    client: AsyncClient, test_user: dict, db_session: AsyncSession
):
    """绑定失败：账号本身已经绑过另一个微信了 → 409。"""
    # 先给 test_user 预先绑定一个 wechat_miniprogram 身份（模拟"该账号已经绑过微信"）
    pre_existing_identity = UserAuthIdentity(
        user_id=test_user["id"],
        identity_type="wechat_miniprogram",
        identity_key="pre_bound_openid_for_conflict_test",
        openid="pre_bound_openid_for_conflict_test",
    )
    db_session.add(pre_existing_identity)
    await db_session.commit()

    # 拿一张新的 binding_ticket（代表另一个微信）
    exchange_resp = await client.post(
        "/api/v1/auth/wechat/exchange",
        json={"code": "conflict_already_bound_account_code"},
    )
    assert exchange_resp.status_code == 200
    ticket = exchange_resp.json()["binding_ticket"]

    # 尝试绑定（同一个账号 userX 已经绑过微信 A，现在要再绑微信 B → 应 409 拒绝）
    bind_resp = await client.post(
        "/api/v1/auth/wechat/bind-existing",
        json={
            "binding_ticket": ticket,
            "email": test_user["email"],
            "password": test_user["password"],
        },
    )
    assert bind_resp.status_code == 409
    assert "该账号已绑定其他微信" in bind_resp.json()["detail"]


@pytest.mark.asyncio
async def test_wechat_register_success(
    client: AsyncClient, test_school: dict, db_session: AsyncSession
):
    """微信新用户注册 → 成功（B-01 后必须提供邮箱；test_school 没配 SchoolDomain 所以任何邮箱皆可）。"""
    # 1. 获取 binding_ticket
    exchange_resp = await client.post(
        "/api/v1/auth/wechat/exchange",
        json={"code": "register_test_code"},
    )
    ticket = exchange_resp.json()["binding_ticket"]

    # 2. 注册新用户（B-01 后 email 为必填）
    register_email = "wx_new_user_test@example.com"
    register_resp = await client.post(
        "/api/v1/auth/wechat/register",
        json={
            "binding_ticket": ticket,
            "nickname": "微信新用户",
            "school_id": test_school["id"],
            "password": "securepassword123",
            "email": register_email,
        },
    )
    assert register_resp.status_code == 200
    data = register_resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["message"] == "注册成功"
    assert "user" in data
    assert data["user"]["id"] >= 1
    assert data["user"]["campus_verified"] is False  # 新用户默认未进行校园邮箱验证
    assert data["user"]["email"] == register_email

    # 3. 验证用户已创建
    user_check = await db_session.execute(
        select(User).where(User.nickname == "微信新用户")
    )
    user = user_check.scalar_one_or_none()
    assert user is not None
    assert user.email == register_email

    # 4. 验证两种身份都已创建（wechat_miniprogram + email_password）
    identities = (await db_session.execute(
        select(UserAuthIdentity).where(UserAuthIdentity.user_id == user.id)
    )).scalars().all()
    identity_types = [i.identity_type for i in identities]
    assert "wechat_miniprogram" in identity_types
    assert "email_password" in identity_types


@pytest.mark.asyncio
async def test_wechat_register_with_email(
    client: AsyncClient, test_school: dict, db_session: AsyncSession
):
    """微信注册时提供自定义邮箱（test_school 空域名 → 放行任意邮箱）。"""
    exchange_resp = await client.post(
        "/api/v1/auth/wechat/exchange",
        json={"code": "custom_email_code"},
    )
    ticket = exchange_resp.json()["binding_ticket"]

    response = await client.post(
        "/api/v1/auth/wechat/register",
        json={
            "binding_ticket": ticket,
            "nickname": "自定义邮箱用户",
            "school_id": test_school["id"],
            "password": "securepassword123",
            "email": "custom@example.com",
        },
    )
    assert response.status_code == 200

    user_check = await db_session.execute(
        select(User).where(User.email == "custom@example.com")
    )
    assert user_check.scalar_one_or_none() is not None


# ============================================================
# B-01 微信注册邮箱域名强制校验 & 空邮箱 400
# ============================================================


async def _seed_wechat_school_with_domains(db_session: AsyncSession, suffix: str, domains: list[str]):
    """事务内自建临时学校+SchoolDomain（pytest 不 seed 三校），返回学校 dict。"""
    from app.models.school import School
    from app.models.school_domain import SchoolDomain
    import time as _t
    short_code = f"w{suffix}{_t.time_ns() % 10000000:07d}"  # 保证 <=20 字，唯一
    school = School(
        name=f"测试校-wx-{suffix}",
        code=short_code,
        is_active=True,
    )
    db_session.add(school)
    await db_session.flush()
    for i, d in enumerate([x.strip().lower().lstrip("@") for x in domains if x.strip()]):
        db_session.add(SchoolDomain(
            school_id=school.id,
            domain=d,
            is_primary=(i == 0),
        ))
    await db_session.commit()
    return {"id": school.id, "name": school.name, "code": school.code}


@pytest.mark.asyncio
async def test_wechat_register_empty_email_now_returns_400(client: AsyncClient, test_school: dict, db_session: AsyncSession):
    """微信注册：不提供 email（或空字符串）→ B-01 后 400，请填写所选学校的教育邮箱。"""
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
            "school_id": test_school["id"],
            "password": "pass12345",
            # 故意不提供 email
        },
    )
    assert register_resp.status_code == 400
    assert "请填写所选学校的教育邮箱" in register_resp.json()["detail"]


@pytest.mark.asyncio
async def test_wechat_register_email_domain_mismatch_returns_400(client: AsyncClient, db_session: AsyncSession):
    """微信注册：自建临时学校（有 SchoolDomain）+ 传 gmail 邮箱 → 400 官方教育邮箱提示。"""
    jn = await _seed_wechat_school_with_domains(
        db_session,
        suffix="jn",
        domains=["jiangnan.edu.cn", "example.jiangnan.edu.cn"],
    )

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
            "school_id": jn["id"],
            "password": "pass12345",
            "email": "wechat_gmail_user@gmail.com",
        },
    )
    assert register_resp.status_code == 400
    assert "官方教育邮箱" in register_resp.json()["detail"]
    assert jn["name"] in register_resp.json()["detail"]


@pytest.mark.asyncio
async def test_wechat_register_example_zju_email_works(client: AsyncClient, db_session: AsyncSession):
    """微信注册：自建临时浙大校（有 example.zju.edu.cn 域名）→ 200 成功且自动校园认证。

    邮箱域名完全命中该校 SchoolDomain → 自动设置 campus_verified=True 并记录认证时间，
    免去用户重新走 verify-campus/send→confirm 邮箱验证码流程。
    """
    zj = await _seed_wechat_school_with_domains(
        db_session,
        suffix="zj",
        domains=["zju.edu.cn", "example.zju.edu.cn"],
    )

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
            "school_id": zj["id"],
            "password": "pass12345",
            "email": unique_email,
        },
    )
    assert register_resp.status_code == 200, register_resp.text
    body = register_resp.json()
    assert body["user"]["email"] == unique_email
    # 命中 addl_domains（example.zju.edu.cn）→ 自动认证
    assert body["user"]["campus_verified"] is True
    assert "access_token" in body
    assert "refresh_token" in body


@pytest.mark.asyncio
async def test_wechat_register_qq_com_global_test_domain_returns_200(client: AsyncClient, db_session: AsyncSession):
    """微信注册：临时学校有严格 SchoolDomain（不含 qq.com）→ qq.com 全局测试邮箱白名单域仍放行，200 成功。"""
    jn = await _seed_wechat_school_with_domains(
        db_session,
        suffix="jnQQ",
        domains=["jiangnan.edu.cn", "example.jiangnan.edu.cn"],
    )
    exchange_resp = await client.post(
        "/api/v1/auth/wechat/exchange",
        json={"code": "QQ_TEST_WECHAT_CODE"},
    )
    ticket = exchange_resp.json()["binding_ticket"]
    unique_email = f"wx_qq_tester_{__import__('time').time_ns()}@qq.com"

    register_resp = await client.post(
        "/api/v1/auth/wechat/register",
        json={
            "binding_ticket": ticket,
            "nickname": "微信QQ邮箱测试者",
            "school_id": jn["id"],
            "password": "pass12345",
            "email": unique_email,
        },
    )
    assert register_resp.status_code == 200, register_resp.text
    body = register_resp.json()
    assert body["user"]["email"] == unique_email
    assert body["user"]["campus_verified"] is False
    assert "access_token" in body
    assert "refresh_token" in body


@pytest.mark.asyncio
async def test_list_identities(client: AsyncClient, test_user: dict, auth_headers: dict):
    """查看当前用户身份列表。"""
    response = await client.get(
        "/api/v1/auth/wechat/identities",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "identities" in data
    # 至少有一个 email_password 身份
    identity_types = [i["identity_type"] for i in data["identities"]]
    assert "email_password" in identity_types


@pytest.mark.asyncio
async def test_add_email_identity(
    client: AsyncClient, test_user: dict, auth_headers: dict, db_session: AsyncSession
):
    """为微信用户添加邮箱登录方式。"""
    # 先创建一个只有微信身份的用户
    wechat_only_user = User(
        email="wx_only@momentcampus.local",
        nickname="微信独登录用户",
        password_hash=get_password_hash("wechatpass123"),
        school_id=test_user["school_id"],
    )
    db_session.add(wechat_only_user)
    await db_session.flush()

    wechat_identity = UserAuthIdentity(
        user_id=wechat_only_user.id,
        identity_type="wechat_miniprogram",
        identity_key="test_openid_only",
        openid="test_openid_only",
    )
    db_session.add(wechat_identity)
    await db_session.commit()

    # 用该用户身份登录测试
    from app.core.security import create_access_token
    token = create_access_token(data={"sub": str(wechat_only_user.id)})

    # 添加邮箱登录方式
    response = await client.post(
        "/api/v1/auth/wechat/identities/email",
        json={
            "email": "newemail@example.com",
            "password": "newpass123",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "添加成功"

    # 验证身份已创建
    identities = (await db_session.execute(
        select(UserAuthIdentity).where(UserAuthIdentity.user_id == wechat_only_user.id)
    )).scalars().all()
    types = [i.identity_type for i in identities]
    assert "email_password" in types


@pytest.mark.asyncio
async def test_delete_identity(
    client: AsyncClient, test_user: dict, auth_headers: dict, db_session: AsyncSession
):
    """解绑登录方式（至少保留一种）。"""
    # 先给用户添加一个微信身份（确保至少 2 种）
    wechat_identity = UserAuthIdentity(
        user_id=test_user["id"],
        identity_type="wechat_miniprogram",
        identity_key="test_openid_for_delete",
        openid="test_openid_for_delete",
    )
    db_session.add(wechat_identity)
    await db_session.commit()
    identity_id = wechat_identity.id

    # 解绑微信身份
    response = await client.delete(
        f"/api/v1/auth/wechat/identities/{identity_id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "解绑成功"

    # 验证已软删除
    await db_session.refresh(wechat_identity)
    assert wechat_identity.is_deleted is True


@pytest.mark.asyncio
async def test_delete_only_identity_fails(
    client: AsyncClient, test_user: dict, auth_headers: dict, db_session: AsyncSession
):
    """尝试解绑最后一种身份 → 400。"""
    # 找到唯一的 email_password 身份
    result = await db_session.execute(
        select(UserAuthIdentity).where(
            UserAuthIdentity.user_id == test_user["id"],
            UserAuthIdentity.identity_type == "email_password",
        )
    )
    identity = result.scalar_one_or_none()
    assert identity is not None

    # 尝试解绑
    response = await client.delete(
        f"/api/v1/auth/wechat/identities/{identity.id}",
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "至少需要保留" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_sessions(client: AsyncClient, test_user: dict, auth_headers: dict):
    """查看当前用户会话列表。"""
    response = await client.get(
        "/api/v1/auth/wechat/sessions",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    # 至少有一个会话（登录时创建的）
    assert len(data["sessions"]) >= 1


@pytest.mark.asyncio
async def test_revoke_session(
    client: AsyncClient, test_user: dict, auth_headers: dict, db_session: AsyncSession
):
    """撤销单个会话。"""
    # 创建一个额外的会话
    session = AuthSession(
        user_id=test_user["id"],
        refresh_token_hash="fake_hash_for_revoke_test",
        session_type="web",
        expires_at=datetime.now() + timedelta(days=7),
    )
    db_session.add(session)
    await db_session.commit()
    session_id = session.id

    # 撤销
    response = await client.delete(
        f"/api/v1/auth/wechat/sessions/{session_id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "会话已撤销"

    # 验证已撤销
    await db_session.refresh(session)
    assert session.is_revoked is True


@pytest.mark.asyncio
async def test_logout_all(
    client: AsyncClient, test_user: dict, auth_headers: dict, db_session: AsyncSession
):
    """退出全部设备。"""
    # 创建几个会话
    for i in range(3):
        session = AuthSession(
            user_id=test_user["id"],
            refresh_token_hash=f"fake_hash_logout_all_{i}",
            session_type="web",
            expires_at=datetime.now() + timedelta(days=7),
        )
        db_session.add(session)
    await db_session.commit()

    # 退出全部
    response = await client.post(
        "/api/v1/auth/wechat/logout-all",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["revoked_count"] >= 3


@pytest.mark.asyncio
async def test_email_login_still_works(client: AsyncClient, test_user: dict):
    """双读兼容：现有邮箱登录仍正常工作。"""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user["email"],
            "password": test_user["password"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_register_creates_identity(
    client: AsyncClient, test_school: dict, db_session: AsyncSession
):
    """注册新用户时自动创建 email_password 身份。"""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "identity_test@example.com",
            "nickname": "身份测试用户",
            "password": "testpassword123",
            "school_id": test_school["id"],
        },
    )
    assert response.status_code == 200
    user_id = response.json()["user"]["id"]

    # 验证身份已创建
    identities = (await db_session.execute(
        select(UserAuthIdentity).where(UserAuthIdentity.user_id == user_id)
    )).scalars().all()
    assert len(identities) >= 1
    assert identities[0].identity_type == "email_password"
    assert identities[0].identity_key == "identity_test@example.com"


@pytest.mark.asyncio
async def test_login_creates_identity_lazy(
    client: AsyncClient, test_school: dict, db_session: AsyncSession
):
    """登录时懒迁移：没有身份记录的老用户登录后自动创建。"""
    # 先创建一个没有身份记录的用户
    user = User(
        email="lazy_migrate@example.com",
        nickname="懒迁移用户",
        password_hash=get_password_hash("testpassword123"),
        school_id=test_school["id"],
    )
    db_session.add(user)
    await db_session.commit()

    # 确保没有身份记录
    identities_before = (await db_session.execute(
        select(UserAuthIdentity).where(UserAuthIdentity.user_id == user.id)
    )).scalars().all()
    assert len(identities_before) == 0

    # 登录
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "lazy_migrate@example.com",
            "password": "testpassword123",
        },
    )
    assert response.status_code == 200

    # 验证身份已自动创建
    identities_after = (await db_session.execute(
        select(UserAuthIdentity).where(UserAuthIdentity.user_id == user.id)
    )).scalars().all()
    assert len(identities_after) >= 1
    assert identities_after[0].identity_type == "email_password"
