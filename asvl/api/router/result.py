"""结果获取API"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from asvl.db.session import get_session
from asvl.db.repositories.task_repo import TaskRepository
from asvl.models.schemas import TaskResult, TaskStatus
from configs.logging import log

router = APIRouter()


@router.get("/{task_id}")
async def get_task_result(
    task_id: str,
    session: AsyncSession = Depends(get_session),
):
    """获取任务处理结果"""
    repo = TaskRepository(session)
    task = await repo.get_by_task_id(task_id)

    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if task.status != TaskStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Task not completed. Current status: {task.status}",
        )

    # TODO: 从final_output表获取完整结果

    return TaskResult(
        task_id=task.task_id,
        video_id=task.video_id,
        status=TaskStatus(task.status),
        summary=None,
        duration=None,
        segments=None,
        highlights=None,
        alignment_issues=None,
    )