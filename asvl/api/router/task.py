"""任务管理API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime
from typing import List, Optional
import uuid
from asvl.db.session import get_session
from asvl.db.repositories.task_repo import TaskRepository
from asvl.db.models.video_task import VideoTask
from asvl.models.schemas import (
    TaskCreateRequest,
    TaskCreateResponse,
    TaskStatusResponse,
    TaskStatus,
    TaskProgress,
)
from configs.logging import log

router = APIRouter()


@router.post("/", response_model=TaskCreateResponse)
async def create_task(
    request: TaskCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    """创建视频处理任务"""
    task_id = f"task_{uuid.uuid4().hex[:12]}"
    video_id = request.video_id or f"vid_{uuid.uuid4().hex[:8]}"

    repo = TaskRepository(session)
    task = await repo.create(
        task_id=task_id,
        video_id=video_id,
        video_url=request.video_url,
        options=request.options.model_dump() if request.options else None,
    )

    log.info(f"Created task: {task_id} for video: {video_id}")

    # 触发Celery任务处理流水线
    from asvl.workers.pipelines.full_pipeline import trigger_pipeline
    options = request.options.model_dump() if request.options else {}
    trigger_pipeline(task_id, request.video_url, options)

    return TaskCreateResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        created_at=task.created_at,
    )


@router.get("/", response_model=List[TaskStatusResponse])
async def list_tasks(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """获取任务列表"""
    query = select(VideoTask).order_by(desc(VideoTask.created_at))

    if status:
        query = query.where(VideoTask.status == status)

    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    tasks = result.scalars().all()

    return [
        TaskStatusResponse(
            task_id=task.task_id,
            status=TaskStatus(task.status),
            progress=TaskProgress(
                asr=TaskStatus(task.progress.get("asr", "pending")),
                llm=TaskStatus(task.progress.get("llm", "pending")),
                clip=TaskStatus(task.progress.get("clip", "pending")),
                vl=TaskStatus(task.progress.get("vl", "pending")),
                fusion=TaskStatus(task.progress.get("fusion", "pending")),
            ),
            created_at=task.created_at,
            updated_at=task.updated_at,
            error_message=task.error_message,
        )
        for task in tasks
    ]


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    session: AsyncSession = Depends(get_session),
):
    """查询任务状态"""
    repo = TaskRepository(session)
    task = await repo.get_by_task_id(task_id)

    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    progress = TaskProgress(
        asr=TaskStatus(task.progress.get("asr", "pending")),
        llm=TaskStatus(task.progress.get("llm", "pending")),
        clip=TaskStatus(task.progress.get("clip", "pending")),
        vl=TaskStatus(task.progress.get("vl", "pending")),
        fusion=TaskStatus(task.progress.get("fusion", "pending")),
    )

    return TaskStatusResponse(
        task_id=task.task_id,
        status=TaskStatus(task.status),
        progress=progress,
        created_at=task.created_at,
        updated_at=task.updated_at,
        error_message=task.error_message,
    )


@router.delete("/{task_id}")
async def cancel_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
):
    """取消任务"""
    repo = TaskRepository(session)
    task = await repo.get_by_task_id(task_id)

    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
        raise HTTPException(status_code=400, detail="Task already completed or failed")

    await repo.update_status(task_id, TaskStatus.FAILED, "Cancelled by user")
    log.info(f"Cancelled task: {task_id}")

    return {"task_id": task_id, "status": "cancelled"}