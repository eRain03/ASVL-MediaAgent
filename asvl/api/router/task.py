"""任务管理API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime
from pathlib import Path
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
from asvl.core.utils.video_info import get_video_info_from_url
from asvl.core.utils.fingerprint import VideoFingerprint
from asvl.core.utils.dedup_cache import get_dedup_cache
from asvl.core.strategy_selector import get_strategy_selector
from asvl.storage.local_storage import LocalStorage
from configs.settings import get_settings
from configs.logging import log

router = APIRouter()
settings = get_settings()


@router.post("/", response_model=TaskCreateResponse)
async def create_task(
    request: TaskCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    """创建视频处理任务 - 支持智能预筛选和去重"""
    task_id = f"task_{uuid.uuid4().hex[:12]}"
    video_id = request.video_id or f"vid_{uuid.uuid4().hex[:8]}"

    repo = TaskRepository(session)
    options = request.options.model_dump() if request.options else {}

    video_source = request.video_url
    if not video_source and request.video_id:
        storage = LocalStorage()
        for suffix in (".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"):
            candidate = storage.get_video_path(f"{request.video_id}{suffix}")
            if Path(candidate).exists():
                video_source = candidate
                break

    if not video_source:
        raise HTTPException(status_code=400, detail="请提供视频URL或先上传视频文件")

    # 1. 视频指纹去重检查
    video_hash = None
    if settings.DEDUP_ENABLED:
        try:
            fingerprint = VideoFingerprint()
            video_hash = await fingerprint.compute(video_source)

            if video_hash:
                dedup_cache = get_dedup_cache()

                # 检查是否已处理过
                cached = await dedup_cache.get_cached_result(video_hash)
                if cached:
                    log.info(f"Found cached result for video: {video_hash[:16]}...")
                    # 返回缓存的任务 ID
                    return TaskCreateResponse(
                        task_id=cached["task_id"],
                        status=TaskStatus.COMPLETED,
                        created_at=datetime.fromisoformat(cached["timestamp"]),
                    )

                # 检查相似视频
                similar_task = await dedup_cache.check_similarity(video_hash)
                if similar_task:
                    log.info(f"Found similar video, task: {similar_task}")
                    # 可以选择返回相似任务或继续处理
                    # 这里选择返回相似任务
                    return TaskCreateResponse(
                        task_id=similar_task,
                        status=TaskStatus.COMPLETED,
                        created_at=datetime.utcnow(),
                    )
        except Exception as e:
            log.warning(f"Fingerprint computation failed: {e}")

    # 2. 获取视频信息（时长等）
    video_duration = None
    strategy_name = None

    try:
        video_info = await get_video_info_from_url(video_source)
        video_duration = video_info.duration

        # 3. 根据时长选择处理策略
        strategy_selector = get_strategy_selector()
        strategy_config = strategy_selector.select(video_duration)
        strategy_name = strategy_config.strategy.value

        # 更新 options
        options["vl_percent"] = strategy_config.vl_percent
        if strategy_config.sample_segments:
            options["sample_segments"] = strategy_config.sample_segments

        log.info(
            f"Task {task_id}: duration={video_duration:.1f}s, "
            f"strategy={strategy_name}, vl_percent={strategy_config.vl_percent}"
        )

    except Exception as e:
        log.warning(f"Failed to get video info, using defaults: {e}")
        strategy_name = "standard"

    # 4. 创建任务
    task = await repo.create(
        task_id=task_id,
        video_id=video_id,
        video_url=video_source,
        options=options,
        video_duration=video_duration,
        video_hash=video_hash,
        strategy=strategy_name,
    )

    log.info(f"Created task: {task_id} for video: {video_id}")

    # 5. 触发Celery任务处理流水线
    from asvl.workers.pipelines.full_pipeline import trigger_pipeline
    trigger_pipeline(task_id, video_source, options)

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