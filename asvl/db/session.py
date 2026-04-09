"""数据库会话管理"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from configs.settings import get_settings
from configs.logging import log

settings = get_settings()

# 基类
Base = declarative_base()


def get_new_engine():
    """创建新的异步引擎（每个任务使用独立的引擎避免event loop问题）"""
    return create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        pool_size=1,  # 每个引擎只有一个连接，避免跨loop共享
        max_overflow=0,
    )


def get_new_session_factory(engine=None):
    """创建新的会话工厂"""
    if engine is None:
        engine = get_new_engine()
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


# 保留全局引擎用于API（共享event loop）
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
)

# 创建会话工厂
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:
    """获取数据库会话"""
    async with async_session() as session:
        try:
            yield session
        except Exception as e:
            log.error(f"Database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """初始化数据库"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("Database initialized successfully")