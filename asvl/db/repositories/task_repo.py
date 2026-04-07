"""任务Repository"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from asvl.db.models.video_task import VideoTask
from asvl.models.enums import TaskStatus
from datetime import datetime


class TaskRepository:
    """任务数据访问"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        task_id: str,
        video_id: str,
        video_url: str,
        options: Optional[dict] = None,
    ) -> VideoTask:
        """创建任务"""
        task = VideoTask(
            task_id=task_id,
            video_id=video_id,
            video_url=video_url,
            options=options,
            status=TaskStatus.PENDING,
            progress={},
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def get_by_task_id(self, task_id: str) -> Optional[VideoTask]:
        """根据task_id获取任务"""
        result = await self.session.execute(
            select(VideoTask).where(VideoTask.task_id == task_id)
        )
        return result.scalar_one_or_none()

    async def get_by_video_id(self, video_id: str) -> List[VideoTask]:
        """根据video_id获取所有任务"""
        result = await self.session.execute(
            select(VideoTask).where(VideoTask.video_id == video_id)
        )
        return result.scalars().all()

    async def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        error_message: Optional[str] = None,
    ) -> Optional[VideoTask]:
        """更新任务状态"""
        task = await self.get_by_task_id(task_id)
        if not task:
            return None

        task.status = status
        task.error_message = error_message
        task.updated_at = datetime.utcnow()

        if status == TaskStatus.COMPLETED:
            task.completed_at = datetime.utcnow()

        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def update_progress(
        self,
        task_id: str,
        stage: str,
        status: TaskStatus,
    ) -> Optional[VideoTask]:
        """更新任务进度"""
        task = await self.get_by_task_id(task_id)
        if not task:
            return None

        progress = task.progress or {}
        progress[stage] = status
        task.progress = progress
        task.updated_at = datetime.utcnow()

        await self.session.commit()
        await self.session.refresh(task)
        return task