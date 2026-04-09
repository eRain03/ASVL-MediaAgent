"""视频裁剪任务 - 完整实现"""
import asyncio
import os
from datetime import datetime
from typing import List

from asvl.workers.celery_app import celery_app
from asvl.core.clipper import FFmpegClipper, ClipMerger
from asvl.db.session import get_new_engine, get_new_session_factory
from asvl.db.repositories.task_repo import TaskRepository
from asvl.db.models.clip_result import ClipResultModel
from asvl.db.models.segment_result import SegmentResultModel
from asvl.models.schemas import LLMResult
from asvl.models.enums import TaskStatus
from asvl.storage.local_storage import LocalStorage
from configs.settings import get_settings
from configs.logging import log

settings = get_settings()


@celery_app.task(
    bind=True,
    name="asvl.workers.tasks.clip_task.process_clip",
)
def process_clip(self, segments: list, task_id: str, video_url: str = None):
    """
    视频裁剪任务

    Args:
        segments: 需要裁剪的分段列表（从上一个任务传递）
        task_id: 任务ID
        video_url: 视频URL（可选，用于下载视频）

    Returns:
        dict: 处理结果
    """
    log.info(f"Starting Clip task for {task_id}")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_process_clip_async(self, segments, task_id, video_url))
    finally:
        loop.close()


async def _process_clip_async(
    task,
    segments: list,
    task_id: str,
    video_url: str,
) -> dict:
    """异步裁剪处理"""
    start_time = datetime.now()

    # 为当前任务创建独立的引擎和会话工厂（在当前event loop中）
    engine = get_new_engine()
    session_factory = get_new_session_factory(engine)

    try:
        # 1. 更新任务状态
        await _update_task_progress(session_factory, task_id, "clip", TaskStatus.PROCESSING)

        # 2. 获取分段结果（如果没有提供或者是 dict 则从数据库获取）
        if not segments or isinstance(segments, dict):
            segments = await _get_segment_result(session_factory, task_id)

        if not segments:
            log.warning(f"No segments found for {task_id}, skipping clip")
            await _update_task_progress(session_factory, task_id, "clip", TaskStatus.COMPLETED)
            await engine.dispose()
            return {"task_id": task_id, "status": "skipped", "clips_count": 0}

        # 3. 转换分段格式
        llm_segments = [
            LLMResult(
                id=s["id"],
                start=s["start"],
                end=s["end"],
                text=s["text"],
                importance=s.get("importance", 0.5),
                type=s.get("type", "背景信息"),
                need_vision=s.get("need_vision", False),
                confidence=s.get("confidence", 0.8),
            )
            for s in segments
        ]

        # 4. 获取视频路径
        video_path = await _get_video_path(task_id, video_url)

        if not video_path or not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found for {task_id}")

        # 5. 初始化裁剪器
        clipper = FFmpegClipper()

        # 6. 批量裁剪（只裁剪need_vision的分段）
        log.info(f"Clipping {len(llm_segments)} segments, filtering need_vision=True")
        clip_results = await clipper.batch_clip(
            video_path=video_path,
            segments=llm_segments,
            filter_vision_only=True,
        )

        # 7. 保存裁剪结果
        await _save_clip_results(session_factory, task_id, clip_results)

        # 8. 更新任务进度
        await _update_task_progress(session_factory, task_id, "clip", TaskStatus.COMPLETED)

        processing_time = (datetime.now() - start_time).total_seconds()
        log.info(f"Clip task completed for {task_id}: {len(clip_results)} clips in {processing_time:.1f}s")

        await engine.dispose()

        return {
            "task_id": task_id,
            "status": "completed",
            "clips_count": len(clip_results),
            "processing_time": processing_time,
        }

    except Exception as e:
        log.error(f"Clip task failed for {task_id}: {e}")
        await _update_task_progress(session_factory, task_id, "clip", TaskStatus.FAILED)
        await engine.dispose()
        raise


async def _get_segment_result(session_factory, task_id: str) -> list:
    """从数据库获取分段结果"""
    from sqlalchemy import select

    async with session_factory() as session:
        result = await session.execute(
            select(SegmentResultModel).where(SegmentResultModel.task_id == task_id)
        )
        seg_result = result.scalar_one_or_none()

        if not seg_result:
            return None

        return seg_result.segments


async def _get_video_path(task_id: str, video_url: str = None) -> str:
    """获取视频路径"""
    storage = LocalStorage()

    # 先检查本地是否已有视频
    local_path = storage.get_video_path(f"{task_id}_video.mp4")
    if os.path.exists(local_path):
        return local_path

    # 已上传的本地视频直接复用
    if video_url and os.path.exists(video_url):
        return video_url

    # TODO: 如果没有本地视频，从URL下载或从OSS获取

    return None


async def _save_clip_results(session_factory, task_id: str, clips: list) -> None:
    """保存裁剪结果"""
    async with session_factory() as session:
        for clip in clips:
            clip_model = ClipResultModel(
                task_id=task_id,
                segment_id=clip.segment_id,
                clip_url=clip.clip_url,
                start_time=clip.start_time,
                end_time=clip.end_time,
                duration=clip.duration,
                storage_path=clip.storage_path,
            )
            session.add(clip_model)

        await session.commit()
        log.info(f"Saved {len(clips)} clip results for {task_id}")


async def _update_task_progress(
    session_factory,
    task_id: str,
    stage: str,
    status: TaskStatus,
) -> None:
    """更新任务进度"""
    async with session_factory() as session:
        repo = TaskRepository(session)
        await repo.update_progress(task_id, stage, status)