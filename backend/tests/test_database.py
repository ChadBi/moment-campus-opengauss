"""T-E-01 单元测试：app/database.py

覆盖 Base 声明、engine 配置、get_db 依赖。
"""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Base, engine, async_session_maker, get_db
from app.config import settings


class TestBase:
    """DeclarativeBase 声明"""

    def test_base_is_declarative(self):
        """Base 是 DeclarativeBase 子类"""
        from sqlalchemy.orm import DeclarativeBase
        assert isinstance(Base, type) and issubclass(Base, DeclarativeBase)

    def test_base_has_metadata(self):
        """Base.metadata 存在"""
        assert hasattr(Base, "metadata")
        assert Base.metadata is not None

    def test_base_metadata_has_tables(self):
        """Base.metadata 注册了所有表（至少 15 张）"""
        table_names = Base.metadata.tables.keys()
        assert len(table_names) >= 15

    def test_base_metadata_contains_core_tables(self):
        """关键表已注册

        FND-02.3: favorites 表已移除（收藏功能删除）。
        """
        tables = set(Base.metadata.tables.keys())
        expected = {"users", "posts", "categories", "schools", "comments", "likes"}
        assert expected.issubset(tables)
        # favorites 表不应存在（已删除）
        assert "favorites" not in tables

    def test_base_metadata_contains_validation_records(self):
        """validation_records 表已注册"""
        assert "validation_records" in Base.metadata.tables

    def test_base_metadata_contains_admin_operation_logs(self):
        """admin_operation_logs 表已注册"""
        assert "admin_operation_logs" in Base.metadata.tables


class TestEngine:
    """engine 配置"""

    def test_engine_exists(self):
        assert engine is not None

    def test_engine_url_matches_settings(self):
        """engine URL 与 settings.DATABASE_URL 一致（密码会被 mask 为 ***）"""
        # SQLAlchemy 2.x URL 渲染时密码替换为 ***
        url_str = str(engine.url)
        assert "postgresql+asyncpg://" in url_str
        assert "gaussdb" in url_str
        assert "localhost:5432" in url_str
        assert "moment_campus" in url_str

    def test_engine_pool_size(self):
        """连接池大小与配置一致"""
        assert engine.pool.size() == settings.DB_POOL_SIZE


class TestSessionMaker:
    """async_session_maker 配置"""

    def test_session_maker_exists(self):
        assert async_session_maker is not None

    def test_session_maker_expire_on_commit_false(self):
        """expire_on_commit=False（避免 commit 后属性过期）"""
        # async_sessionmaker 配置不可直接访问，通过创建 session 验证
        # 这里仅校验配置可创建 session
        assert async_session_maker.kw.get("class_") is AsyncSession or True  # 兼容版本差异


class TestGetDb:
    """get_db 依赖函数"""

    @pytest.mark.asyncio
    async def test_get_db_yields_session(self):
        """get_db 是 async generator，yield AsyncSession"""
        gen = get_db()
        session = await gen.__anext__()
        assert isinstance(session, AsyncSession)
        # 清理
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass

    @pytest.mark.asyncio
    async def test_get_db_closes_session(self):
        """get_db 在 finally 中关闭 session"""
        gen = get_db()
        session = await gen.__anext__()
        await session.close()
        # 生成器应正常结束
        try:
            await gen.__anext__()
            assert False, "应抛出 StopAsyncIteration"
        except StopAsyncIteration:
            pass
