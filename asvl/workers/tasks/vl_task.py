"""VL视觉理解任务 - 完整实现"""
import asyncio
import os
from datetime import datetime
from typing import List, Dict

from asvl.workers.celery_app import celery_app
from asvl.core.vl import QwenVLProcessor
from asvl.core.llm.client import LLMClient
from asvl.db.session import get_new_engine, get_new_session_factory
from asvl.db.repositories.task_repo import TaskRepository
from asvl.db.models.vl_result import VLResultModel
from asvl.db.models.clip_result import ClipResultModel
from asvl.models.schemas import VLResult
from asvl.models.enums import TaskStatus
from configs.settings import get_settings
from configs.logging import log

settings = get_settings()


@celery_app.task(
    bind=True,
    name="asvl.workers.tasks.vl_task.process_vl",
)
def process_vl(self, clips: list, task_id: str):
    """
    VL视觉理解任务

    Args:
        clips: 需要分析的片段列表（从上一个任务传递）
        task_id: 任务ID

    Returns:
        dict: 处理结果
    """
    log.info(f"Starting VL task for {task_id}")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_process_vl_async(self, clips, task_id))
    finally:
        loop.close()


async def _process_vl_async(
    task,
    clips: list,
    task_id: str,
) -> dict:
    """异步VL处理"""
    start_time = datetime.now()

    # 为当前任务创建独立的引擎和会话工厂（在当前event loop中）
    engine = get_new_engine()
    session_factory = get_new_session_factory(engine)

    try:
        # 1. 更新任务状态
        await _update_task_progress(session_factory, task_id, "vl", TaskStatus.PROCESSING)

        # 2. 获取需要分析的片段（如果没有提供或者是 dict 则从数据库获取）
        if not clips or isinstance(clips, dict):
            clips = await _get_clip_results(session_factory, task_id)

        if not clips:
            log.info(f"No clips to analyze for {task_id}")
            await _update_task_progress(session_factory, task_id, "vl", TaskStatus.COMPLETED)
            await engine.dispose()
            return {"task_id": task_id, "status": "skipped", "vl_results_count": 0}

        log.info(f"Processing {len(clips)} clips for VL analysis")

        # 3. 初始化VL处理器
        llm_client = LLMClient()
        vl_processor = QwenVLProcessor(llm_client=llm_client)

        # 4. 获取相关文本（用于上下文）
        segment_texts = await _get_segment_texts(session_factory, task_id)

        # 5. 批量分析片段（串行处理，因为API限流）
        vl_results = []
        for i, clip in enumerate(clips):
            clip_path = clip.get("storage_path") or clip.get("clip_url")
            segment_id = clip.get("segment_id", "")

            if not clip_path or not os.path.exists(clip_path):
                log.warning(f"Clip file not found: {clip_path}")
                continue

            log.info(f"Analyzing clip {i+1}/{len(clips)}: {segment_id}")

            try:
                # 获取相关文本
                context = segment_texts.get(segment_id, "")

                # 分析片段
                result = await vl_processor.analyze_clip(
                    clip_path=clip_path,
                    segment_text=context,
                )
                # 设置clip_id和segment_id
                result.clip_id = os.path.basename(clip_path)
                result.segment_id = segment_id  # 直接使用clip中的segment_id

                vl_results.append(result)

            except Exception as e:
                log.error(f"Failed to analyze clip {segment_id}: {e}")
                continue

        # 6. 保存VL结果
        await _save_vl_results(session_factory, task_id, vl_results)

        # 7. 更新任务进度
        await _update_task_progress(session_factory, task_id, "vl", TaskStatus.COMPLETED)

        processing_time = (datetime.now() - start_time).total_seconds()
        log.info(f"VL task completed for {task_id}: {len(vl_results)} results in {processing_time:.1f}s")

        await engine.dispose()

        return {
            "task_id": task_id,
            "status": "completed",
            "vl_results_count": len(vl_results),
            "processing_time": processing_time,
        }

    except Exception as e:
        log.error(f"VL task failed for {task_id}: {e}")
        await _update_task_progress(session_factory, task_id, "vl", TaskStatus.FAILED)
        await engine.dispose()
        raise


async def _get_clip_results(session_factory, task_id: str) -> list:
    """从数据库获取裁剪结果"""
    from sqlalchemy import select

    async with session_factory() as session:
        result = await session.execute(
            select(ClipResultModel).where(ClipResultModel.task_id == task_id)
        )
        clips = result.scalars().all()

        return [
            {
                "clip_id": c.clip_id if hasattr(c, 'clip_id') else "",
                "segment_id": c.segment_id,
                "storage_path": c.storage_path,
                "start_time": c.start_time,
                "end_time": c.end_time,
            }
            for c in clips
        ]


async def _get_segment_texts(session_factory, task_id: str) -> Dict[str, str]:
    """获取分段文本（用于上下文）"""
    from sqlalchemy import select
    from asvl.db.models.segment_result import SegmentResultModel

    async with session_factory() as session:
        result = await session.execute(
            select(SegmentResultModel).where(SegmentResultModel.task_id == task_id)
        )
        seg_result = result.scalar_one_or_none()

        if not seg_result:
            return {}

        return {
            seg.get("id", ""): seg.get("text", "")
            for seg in seg_result.segments
        }


async def _save_vl_results(session_factory, task_id: str, results: List[VLResult]) -> None:
    """保存VL结果"""
    async with session_factory() as session:
        for result in results:
            vl_model = VLResultModel(
                task_id=task_id,
                clip_id=result.clip_id,
                segment_id=getattr(result, 'segment_id', None),  # 保存segment_id
                vision_summary=result.vision_summary,
                actions=result.actions,
                objects=result.objects,
                scene_description=result.scene_description,
                confidence=result.confidence,
            )
            session.add(vl_model)

        await session.commit()
        log.info(f"Saved {len(results)} VL results for {task_id}")


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