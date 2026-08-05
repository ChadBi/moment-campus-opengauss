import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.db_compat  # noqa: F401  openGauss 兼容性补丁，必须在创建引擎前导入
from app.database import Base, get_db
from app.main import app
from app.models import *  # noqa: F401,F403 - ensure all models registered with Base
from app.core.security import get_password_hash, create_access_token, create_refresh_token
from app.config import settings

# ============================================================
# FND-02.1 + FND-02.2: 独立测试库 + 防误删保护
# ============================================================
# 测试统一使用 openGauss（项目已完全迁移，不再支持 SQLite）。
# 测试库连接串只读 TEST_DATABASE_URL 环境变量，缺失即停（不回退到开发库，防止误删开发数据）。
# 启动断言：
#   1. 必须提供 TEST_DATABASE_URL
#   2. 数据库名必须含 _test（防止指向开发/生产库）
#   3. 严禁与 settings.DATABASE_URL（开发库）相同
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    raise RuntimeError(
        "FND-02: 未设置 TEST_DATABASE_URL 环境变量。"
        "测试必须使用独立测试库，不会回退到开发库以防误删数据。"
        "请设置：$env:TEST_DATABASE_URL = "
        "'postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test'"
    )

# 从 URL 中解析数据库名（取最后一个 / 之后、? 之前的部分）
_db_name_in_url = TEST_DATABASE_URL.rsplit("/", 1)[-1].split("?")[0]
if "_test" not in _db_name_in_url:
    raise RuntimeError(
        f"FND-02: 测试库连接串的数据库名 '{_db_name_in_url}' 必须包含 '_test'，"
        f"以防误删开发/生产库。当前 TEST_DATABASE_URL = {TEST_DATABASE_URL}"
    )

if TEST_DATABASE_URL == settings.DATABASE_URL:
    raise RuntimeError(
        "FND-02: TEST_DATABASE_URL 与开发库 settings.DATABASE_URL 相同，"
        "严禁在开发库上运行测试（TRUNCATE 会清空数据）。"
    )

# 使用 NullPool 避免连接跨事件循环复用（pytest-asyncio 默认每用例一个 loop）。
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)

test_session_maker = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(autouse=True)
def _no_external_embedding_calls(monkeypatch):
    """测试隔离：禁用真实外部 Embedding 调用。

    单元/接口测试不应发起真实外部 API 请求（避免走系统代理、产生未关闭连接与额外费用）。
    默认降级为 None（与未配置 Embedding 时的行为一致）；需要向量时由具体测试自行 mock。
    """
    async def _noop_embedding(*args, **kwargs):
        return None

    monkeypatch.setattr("app.services.ai_search.generate_embedding", _noop_embedding)
    monkeypatch.setattr("app.api.posts.generate_post_embedding", _noop_embedding)


@pytest.fixture(scope="session")
def opengauss_test_engine():
    """向需要验证真实 SQL 事务的测试显式暴露独立测试库引擎。"""
    return test_engine


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session.

    保留以兼容旧版 pytest-asyncio；新版（1.x）默认按用例创建 loop。
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_test_tables():
    """FND-02: 测试库建表（session 级，仅一次）。

    测试库 moment_campus_test 是空库，需在 session 开始时通过
    Base.metadata.create_all() 创建所有 ORM 模型对应的表。
    注意：仅创建 ORM 模型表，不创建高级 SQL 对象（表空间/分区/物化视图/存储过程/触发器），
    这些由 integration 测试单独验证（未安装时跳过）。
    测试结束后保留表结构（不 DROP DATABASE），数据由 setup_database 用 TRUNCATE 清理。

    Task 1.2 调整：先 DROP SCHEMA CASCADE 清理所有旧表（含已删除模型遗留的表
    如 post_change_reports / post_types，避免它们阻止 drop_all），再 create_all。
    """
    from sqlalchemy import text
    async with test_engine.begin() as conn:
        # DROP 所有旧表与依赖对象（CASCADE），处理已删除模型遗留的孤儿表
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.run_sync(Base.metadata.create_all)
    yield
    # session 结束时仅 dispose engine，不删库不删表
    await test_engine.dispose()


async def _reset_opengauss_sequences(conn) -> None:
    """显式重置所有表的自增序列。

    openGauss (PGXC) 不支持 `TRUNCATE ... RESTART IDENTITY`，
    使用 setval(seq, 1, false) 重置（DML，不会隐式提交，可与事务共存）。
    仅对存在 id 列的表生效。每条 setval 用 savepoint 包裹防止单表失败影响全局。

    重要：setval(seq, 1, false) 设置序列当前值为 1，is_called=False，
    下一次 nextval() 返回 1。配合 DELETE 清空数据后使用，确保新插入从 ID=1 开始。
    若 DELETE 失败（savepoint 回滚），序列不应被重置（否则导致 duplicate key），
    因此 setval 在 DELETE 之后执行，且用独立 savepoint 包裹。
    """
    for table_name in Base.metadata.tables.keys():
        # 查询序列名（pg_get_serial_sequence 返回 NULL 表示该表无 id 序列）
        result = await conn.execute(
            text(f"SELECT pg_get_serial_sequence('{table_name}', 'id')")
        )
        seq_name = result.scalar()
        if seq_name is None:
            continue
        sp_name = f"sp_seq_{table_name}"
        try:
            await conn.execute(text(f"SAVEPOINT {sp_name}"))
            # setval(seq, 1, false) → 下一次 nextval 返回 1（等价于 RESTART WITH 1）
            await conn.execute(text(f"SELECT setval('{seq_name}', 1, false)"))
            await conn.execute(text(f"RELEASE SAVEPOINT {sp_name}"))
        except Exception:
            try:
                await conn.execute(text(f"ROLLBACK TO SAVEPOINT {sp_name}"))
            except Exception:
                pass


# 自引用表集合：这些表存在自引用 FK（如 comments.parent_id → comments.id），
# 需要先删除子行（parent_id IS NOT NULL）再删除全部，否则 FK 约束阻止删除。
_SELF_REF_TABLES = {"comments"}


async def _delete_all_data(conn) -> None:
    """使用 DELETE 按反向拓扑序清空所有 ORM 表数据。

    方案演进（经多轮实测验证）：
    - TRUNCATE CASCADE：AccessExclusiveLock 与并发 SELECT 的 AccessShareLock 死锁；
      且 TRUNCATE 失败后序列仍被重置 → INSERT 报 duplicate key
    - DELETE + session_replication_role='replica'：禁用 FK 后 openGauss 缓存过期
      snapshot，后续 INSERT 报 FK violation 假阳性
    - DELETE + savepoint：savepoint 静默吞掉 DELETE 失败，导致数据残留但序列被重置
      → INSERT 报 duplicate key（本次修复的关键发现）
    - **当前方案**：DELETE 按反向拓扑序（子表先于父表），不禁用 FK 约束，不用 savepoint
      - RowExclusiveLock 与并发 SELECT 的 AccessShareLock 兼容（不阻塞/死锁）
      - 不使用 session_replication_role（不破坏 FK 可见性）
      - 反向拓扑序确保子表先删，FK 约束自然满足
      - 自引用表（comments.parent_id）先删子行再删全部
      - 多趟删除：首趟可能因复杂 FK 残留少量数据，第二/三趟清理干净
      - 不使用 savepoint：DELETE 失败则整个清理事务失败，由 _cleanup_with_retry 重试
        （重试间隔让 override_get_db session 有时间 close 释放锁）
      - 序列重置由 _reset_opengauss_sequences 在同一事务内执行（原子性）

    归档表（分区表，不在 Base.metadata 中）单独清理。
    """
    # 多趟删除：首趟删除大部分数据，后续趟清理因 FK 残留的数据
    for pass_num in range(3):
        deleted_any = False
        for table in reversed(Base.metadata.sorted_tables):
            # 自引用表：先删子行（parent_id IS NOT NULL），再删全部
            if table.name in _SELF_REF_TABLES:
                await conn.execute(text(
                    f'DELETE FROM "{table.name}" WHERE parent_id IS NOT NULL'
                ))
            result = await conn.execute(table.delete())
            if result.rowcount and result.rowcount > 0:
                deleted_any = True
        # 如果本趟没有删除任何数据，说明全部清理完成
        if not deleted_any:
            break

    # 归档表（分区表，不在 Base.metadata 中）
    try:
        await conn.execute(text(
            "DO $$ BEGIN "
            "EXECUTE 'DELETE FROM admin_operation_logs_archive'; "
            "EXCEPTION WHEN undefined_table THEN NULL; "
            "END $$"
        ))
    except Exception:
        pass


async def _cleanup_with_retry(max_retries: int = 5) -> None:
    """带重试的数据清理 + 序列重置（同一事务，原子性）。

    残留 session 锁来源：上一用例的 db_session / override_get_db 未及时释放（asyncio
    事件循环切换延迟）。重试间隔给 GC / connection close 足够时间完成。

    关键改进：DELETE + setval 在同一事务内执行，避免"数据未删但序列已重置"的
    不一致状态（此前 TRUNCATE 失败但序列重置成功导致 duplicate key）。
    """
    import asyncio as _asyncio
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            async with test_engine.begin() as conn:
                await _delete_all_data(conn)
                await _reset_opengauss_sequences(conn)
            return
        except Exception as e:
            last_exc = e
            if attempt < max_retries - 1:
                # 异步等待，让事件循环有机会清理残留 session
                await _asyncio.sleep(0.5 * (attempt + 1))
                continue
            raise
    if last_exc:
        raise last_exc


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """每个用例前后清空所有表并重置序列（openGauss）。

    使用 DELETE 按反向拓扑序清空所有表（多趟），并显式重置序列
    （openGauss 不支持 TRUNCATE ... RESTART IDENTITY）。
    DELETE + 序列重置在同一事务内执行（原子性），避免不一致状态。
    同时清理归档表（admin_operation_logs_archive，SP05 写入），表不存在时跳过。

    COM-01: 清表后立即预置 3 档套餐 + 权益项数据，保证 EntitlementService 可加载权益。
    """
    # 清理 + 序列重置（同一事务，原子性）
    await _cleanup_with_retry()

    # COM-01: 预置 3 档套餐 + 权益项
    # openGauss 不支持 PostgreSQL 的 ON CONFLICT 语法，使用 DO $$ BEGIN ... EXCEPTION
    # WHEN unique_violation THEN NULL; END $$ 实现幂等（与归档表清理同一模式）
    # 但 openGauss 的 DO 块在某些并发/锁场景下可能静默失败（INSERT 未生效但未抛异常），
    # 因此改用 Python 层 SELECT-then-INSERT 模式，更可靠地保证 plan 行存在。
    # 关键：asyncpg 期望 datetime 对象（不是字符串），created_at/updated_at 直接传 datetime。
    from datetime import datetime as _dt
    from sqlalchemy.exc import IntegrityError as _SAIntegrityError
    now = _dt.now()
    plans_data = [
        ("trial", "试用档", "trial desc", 10, [
            ("members_max", 20, True), ("posts_max", 50, True),
            ("storage_mb", 200, False), ("ai_calls_daily", 20, True),
        ]),
        ("standard", "标准档", "standard desc", 20, [
            ("members_max", 200, True), ("posts_max", 2000, True),
            ("storage_mb", 2048, False), ("ai_calls_daily", 200, True),
        ]),
        ("operations", "运营档", "operations desc", 30, [
            ("members_max", None, False), ("posts_max", None, False),
            ("storage_mb", 10240, False), ("ai_calls_daily", 2000, True),
        ]),
    ]
    async with test_engine.begin() as plan_conn:
        for code, name, desc, sort, ents in plans_data:
            # 先查询是否已存在（幂等）
            existing = (await plan_conn.execute(
                text("SELECT id FROM product_plans WHERE code = :code"), {"code": code}
            )).first()
            if existing is None:
                # 不存在则插入；用 savepoint 包裹防 unique_violation 中断事务
                try:
                    await plan_conn.execute(text("SAVEPOINT sp_plan_insert"))
                    await plan_conn.execute(text(
                        "INSERT INTO product_plans (code, name, description, status, sort_order, created_at, updated_at) "
                        "VALUES (:code, :name, :desc, 'active', :sort, :now, :now)"
                    ), {"code": code, "name": name, "desc": desc, "sort": sort, "now": now})
                    await plan_conn.execute(text("RELEASE SAVEPOINT sp_plan_insert"))
                except _SAIntegrityError:
                    # unique_violation：回滚 savepoint 后重新查询
                    await plan_conn.execute(text("ROLLBACK TO SAVEPOINT sp_plan_insert"))
                    await plan_conn.execute(text("RELEASE SAVEPOINT sp_plan_insert"))
            # 再次查询获取 plan_id（无论新建还是已有）
            row = (await plan_conn.execute(
                text("SELECT id FROM product_plans WHERE code = :code"), {"code": code}
            )).one_or_none()
            if row is None:
                # 极端情况：INSERT 未生效且未抛异常，跳过该 plan 的权益项
                # 避免级联失败影响后续测试
                continue
            plan_id = row[0]
            for key, lv, hard in ents:
                # 同样用 savepoint 包裹防 unique_violation
                # 全部用绑定参数（避免 SQL 注入 + 类型转换由 driver 处理）
                try:
                    await plan_conn.execute(text("SAVEPOINT sp_ent_insert"))
                    await plan_conn.execute(text(
                        "INSERT INTO plan_entitlements (plan_id, key, limit_value, is_hard, created_at, updated_at) "
                        "VALUES (:plan_id, :key, :lv, :hard, :now, :now)"
                    ), {"plan_id": plan_id, "key": key, "lv": lv, "hard": hard, "now": now})
                    await plan_conn.execute(text("RELEASE SAVEPOINT sp_ent_insert"))
                except _SAIntegrityError:
                    await plan_conn.execute(text("ROLLBACK TO SAVEPOINT sp_ent_insert"))
                    await plan_conn.execute(text("RELEASE SAVEPOINT sp_ent_insert"))

    yield
    # teardown：清理 + 序列重置（同一事务，原子性）
    await _cleanup_with_retry()


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """测试用 get_db 覆盖：每个请求独立 session，退出时显式 rollback + close 释放锁。

    不使用 async with（async generator + async with 组合在 pytest-asyncio 事件循环
    切换时可能延迟 close），改为手动管理 session 生命周期：
    1. 请求结束 → rollback 释放未提交事务的锁
    2. 显式 close → 归还连接（NullPool 即销毁），确保不残留 RowExclusiveLock
       与下一个用例的 setup_database DELETE 抢锁。
    """
    session = test_session_maker()
    try:
        yield session
    finally:
        try:
            await session.rollback()
        except Exception:
            pass
        try:
            await session.close()
        except Exception:
            pass


# Override the get_db dependency in the app
app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an httpx AsyncClient for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session for direct DB operations in tests.

    退出时显式 rollback + close，确保不残留未提交事务/锁，避免 setup_database
    teardown 的 DELETE 与本 session 抢锁。

    ORG-01: 额外确保连接归还到 NullPool，避免 openGauss 在多测试连续运行时
    因连接持有 RowExclusiveLock 互相等待而触发 deadlock。
    """
    session = test_session_maker()
    try:
        yield session
        # 显式清理未提交事务，释放可能持有的锁，避免后续 DELETE 抢锁
        try:
            await session.rollback()
        except Exception:
            pass
    finally:
        # 显式关闭 session，确保底层连接立即归还（NullPool 即销毁），
        # 防止与下一个用例的 setup_database DELETE 抢锁
        try:
            await session.close()
        except Exception:
            pass


@pytest_asyncio.fixture
async def test_school(db_session: AsyncSession) -> dict:
    """Create a test school and return its id.

    COM-01: 同时为该校分配 operations 档 active 订阅，避免 create_post / upload_image
    的 EntitlementService 校验因无订阅拒绝操作（保护现有测试不破坏）。
    """
    from datetime import datetime
    from sqlalchemy import select as _select, text as _text
    from app.models.school import School
    from app.models.product_plan import ProductPlan
    from app.models.school_subscription import SchoolSubscription
    school = School(name="测试大学", code="test-uni", is_active=True)
    db_session.add(school)
    await db_session.flush()  # flush 获取 id，但不提交
    school_id = school.id
    school_code = school.code
    school_name = school.name
    print(f"\n[DEBUG test_school] after flush: school.id={school_id}")

    # 提交事务，让其他 session（override_get_db）可见
    await db_session.commit()
    print(f"[DEBUG test_school] after commit: school.id={school_id}")

    # 不调用 refresh()（openGauss 在某些场景下 refresh 会报 Could not refresh instance）
    # 直接用 id 查询验证
    check_row = (await db_session.execute(
        _text("SELECT id, code FROM schools WHERE id = :sid"), {"sid": school_id}
    )).first()
    print(f"[DEBUG test_school] DB check via db_session: {check_row}")

    # DEBUG: 用全新连接验证可见性（模拟 override_get_db 的视角）
    async with test_engine.connect() as fresh_conn:
        fresh_row = (await fresh_conn.execute(
            _text("SELECT id, code FROM schools WHERE id = :sid"), {"sid": school_id}
        )).first()
        print(f"[DEBUG test_school] DB check via fresh connection: {fresh_row}")

    # 给 test_school 自动分配 operations active 订阅
    plan = (await db_session.execute(
        _select(ProductPlan).where(ProductPlan.code == "operations")
    )).scalar_one_or_none()
    if plan is not None:
        now = datetime.now()
        sub = SchoolSubscription(
            school_id=school_id,
            plan_id=plan.id,
            status="active",
            started_at=now,
            expires_at=None,
            assigned_at=now,
            note="test_school fixture auto-assign operations",
        )
        db_session.add(sub)
        await db_session.commit()

    return {"id": school_id, "name": school_name, "code": school_code}


@pytest_asyncio.fixture
async def test_category(db_session: AsyncSession, test_school: dict) -> dict:
    """Create a test category and return its id.

    FND-03: 依赖 test_school 显式设置 school_id，避免依赖默认值 1 在 school 未创建时触发外键约束。
    """
    from sqlalchemy import text as _text
    from app.models.category import Category
    # DEBUG: 检查 school 是否存在
    school_check = (await db_session.execute(
        _text("SELECT id, code FROM schools WHERE id = :sid"),
        {"sid": test_school["id"]},
    )).first()
    print(f"\n[DEBUG test_category] test_school['id']={test_school['id']}, "
          f"school in DB={school_check}")
    category = Category(
        name="失物招领", code="lost-found", icon="🔍",
        default_validity_days=30, is_active=True,
        school_id=test_school["id"],
    )
    db_session.add(category)
    await db_session.commit()
    await db_session.refresh(category)
    return {"id": category.id, "name": category.name, "code": category.code}


@pytest_asyncio.fixture
async def test_user(client: AsyncClient, test_school: dict, db_session: AsyncSession) -> dict:
    """Register a test user and return user info with tokens.

    UC-01（D4 门禁）：测试用户默认完成校园身份认证（campus_verified=True），
    使既有写操作测试不受「未认证只读」限制；未认证场景由专用 fixture 覆盖。
    """
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "testuser@example.com",
            "nickname": "测试用户",
            "password": "testpassword123",
            "school_id": test_school["id"],
        },
    )
    assert response.status_code == 200
    data = response.json()

    # UC-01: 置为已认证（D4 门禁默认通过）
    from app.models.user import User
    user = (
        await db_session.execute(
            select(User).where(User.email == "testuser@example.com")
        )
    ).scalar_one_or_none()
    assert user is not None
    user.campus_verified = True
    await db_session.commit()

    return {
        "id": data["user"]["id"],
        "email": "testuser@example.com",
        "nickname": "测试用户",
        "password": "testpassword123",
        "school_id": test_school["id"],
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
    }


@pytest_asyncio.fixture
async def auth_headers(test_user: dict) -> dict:
    """Return authorization headers for the test user."""
    return {"Authorization": f"Bearer {test_user['access_token']}"}


@pytest_asyncio.fixture
async def test_post(client: AsyncClient, auth_headers: dict, test_school: dict, test_category: dict) -> dict:
    """Create a test post and return its data."""
    response = await client.post(
        "/api/v1/posts",
        json={
            "title": "测试帖子标题",
            "content": "这是测试帖子的内容，至少十个字符",
            "category_id": test_category["id"],
            "is_anonymous": False,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()


@pytest_asyncio.fixture
async def second_user(client: AsyncClient, test_school: dict, db_session: AsyncSession) -> dict:
    """Register a second test user for ownership tests.

    UC-01（D4 门禁）：默认已完成校园认证。
    """
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "seconduser@example.com",
            "nickname": "第二用户",
            "password": "testpassword456",
            "school_id": test_school["id"],
        },
    )
    assert response.status_code == 200
    data = response.json()

    from app.models.user import User
    user = (
        await db_session.execute(
            select(User).where(User.email == "seconduser@example.com")
        )
    ).scalar_one_or_none()
    assert user is not None
    user.campus_verified = True
    await db_session.commit()

    return {
        "email": "seconduser@example.com",
        "nickname": "第二用户",
        "password": "testpassword456",
        "school_id": test_school["id"],
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
    }


@pytest_asyncio.fixture
async def second_auth_headers(second_user: dict) -> dict:
    """Return authorization headers for the second test user."""
    return {"Authorization": f"Bearer {second_user['access_token']}"}


@pytest_asyncio.fixture
async def admin_user(client: AsyncClient, db_session: AsyncSession, test_school: dict) -> dict:
    """注册一名管理员用户并返回其 token。

    先注册普通用户，再直接修改 role='admin' 升为管理员。
    """
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "adminuser@example.com",
            "nickname": "管理员",
            "password": "adminpassword123",
            "school_id": test_school["id"],
        },
    )
    assert response.status_code == 200
    data = response.json()

    # 升为管理员
    from app.models.user import User
    result = await db_session.execute(
        select(User).where(User.email == "adminuser@example.com")
    )
    user = result.scalar_one_or_none()
    assert user is not None
    user.role = "admin"
    # UC-01（D4 门禁）：管理员默认已完成校园认证
    user.campus_verified = True
    await db_session.commit()

    return {
        "email": "adminuser@example.com",
        "nickname": "管理员",
        "password": "adminpassword123",
        "school_id": test_school["id"],
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "id": user.id,
    }


@pytest_asyncio.fixture
async def admin_headers(admin_user: dict) -> dict:
    """Return authorization headers for the admin user."""
    return {"Authorization": f"Bearer {admin_user['access_token']}"}
