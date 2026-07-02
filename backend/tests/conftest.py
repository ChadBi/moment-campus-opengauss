import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database import Base, get_db
from app.main import app
from app.models import *  # noqa: F401,F403 - ensure all models registered with Base
from app.core.security import get_password_hash, create_access_token, create_refresh_token

# 测试统一使用 openGauss（项目已完全迁移，不再支持 SQLite）。
# 使用 NullPool 避免连接跨事件循环复用（pytest-asyncio 默认每用例一个 loop）。
from app.config import settings
test_engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)

test_session_maker = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session.

    保留以兼容旧版 pytest-asyncio；新版（1.x）默认按用例创建 loop。
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


async def _reset_opengauss_sequences(conn) -> None:
    """显式重置所有表的自增序列。

    openGauss (PGXC) 不支持 `TRUNCATE ... RESTART IDENTITY`，
    需使用 `setval(pg_get_serial_sequence(...), 1, false)` 单独重置。
    仅对存在 id 列的表生效。
    """
    for table_name in Base.metadata.tables.keys():
        await conn.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
                f"1, false) WHERE pg_get_serial_sequence('{table_name}', 'id') IS NOT NULL"
            )
        )


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """每个用例前后清空所有表并重置序列（openGauss）。

    使用 TRUNCATE ... CASCADE 清空所有表（保留外部创建的 schema 与数据库对象如表空间/物化视图/触发器等），
    并显式重置序列（openGauss 不支持 RESTART IDENTITY）。
    """
    table_names = ", ".join(f'"{t}"' for t in Base.metadata.tables.keys())
    async with test_engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {table_names} CASCADE"))
        await _reset_opengauss_sequences(conn)
    yield
    async with test_engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {table_names} CASCADE"))
        await _reset_opengauss_sequences(conn)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_maker() as session:
        yield session


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
    """Provide a test database session for direct DB operations in tests."""
    async with test_session_maker() as session:
        yield session


@pytest_asyncio.fixture
async def test_school(db_session: AsyncSession) -> dict:
    """Create a test school and return its id."""
    from app.models.school import School
    school = School(name="测试大学", code="test-uni", is_active=True)
    db_session.add(school)
    await db_session.commit()
    await db_session.refresh(school)
    return {"id": school.id, "name": school.name, "code": school.code}


@pytest_asyncio.fixture
async def test_category(db_session: AsyncSession) -> dict:
    """Create a test category and return its id."""
    from app.models.category import Category
    category = Category(name="失物招领", code="lost-found", icon="🔍", default_validity_days=30, is_active=True)
    db_session.add(category)
    await db_session.commit()
    await db_session.refresh(category)
    return {"id": category.id, "name": category.name, "code": category.code}


@pytest_asyncio.fixture
async def test_post_type(db_session: AsyncSession) -> dict:
    """Create a test post type and return its id."""
    from app.models.post_type import PostType
    post_type = PostType(name="普通信息", code="normal", is_active=True)
    db_session.add(post_type)
    await db_session.commit()
    await db_session.refresh(post_type)
    return {"id": post_type.id, "name": post_type.name, "code": post_type.code}


@pytest_asyncio.fixture
async def test_user(client: AsyncClient, test_school: dict) -> dict:
    """Register a test user and return user info with tokens."""
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
    return {
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
async def test_post(client: AsyncClient, auth_headers: dict, test_school: dict, test_category: dict, test_post_type: dict) -> dict:
    """Create a test post and return its data."""
    response = await client.post(
        "/api/v1/posts",
        json={
            "title": "测试帖子标题",
            "content": "这是测试帖子的内容，至少十个字符",
            "category_id": test_category["id"],
            "post_type_id": test_post_type["id"],
            "is_anonymous": False,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()


@pytest_asyncio.fixture
async def second_user(client: AsyncClient, test_school: dict) -> dict:
    """Register a second test user for ownership tests."""
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
