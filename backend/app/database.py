import app.db_compat  # noqa: F401  应用 openGauss 兼容性补丁，必须在创建引擎前导入
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

# 根据数据库类型构造引擎参数：PostgreSQL 使用连接池，SQLite 不传 pool 参数
engine_kwargs = {
    "echo": settings.DEBUG,
}
if "postgresql" in settings.DATABASE_URL or "asyncpg" in settings.DATABASE_URL:
    engine_kwargs.update(
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=settings.DB_POOL_RECYCLE,
    )

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
