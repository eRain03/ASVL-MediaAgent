"""依赖注入"""
from functools import lru_cache
from sqlalchemy.ext.asyncio import AsyncSession
from asvl.db.session import async_session
from asvl.db.repositories.task_repo import TaskRepository
from asvl.core.llm.client import LLMClient


async def get_db_session() -> AsyncSession:
    """获取数据库会话"""
    async with async_session() as session:
        yield session


@lru_cache
def get_llm_client() -> LLMClient:
    """获取LLM客户端（缓存）"""
    return LLMClient()


def get_task_repo(session: AsyncSession) -> TaskRepository:
    """获取任务Repository"""
    return TaskRepository(session)