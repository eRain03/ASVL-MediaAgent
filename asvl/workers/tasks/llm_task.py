"""LLM处理任务 - 完整实现"""
import asyncio
from datetime import datetime
from typing import List, Dict, Any

from asvl.workers.celery_app import celery_app
from asvl.core.llm import (
    LLMClient,
    SemanticSegmenter,
    ImportanceScorer,
    VisionDetector,
)
from asvl.db.session import get_new_engine, get_new_session_factory
from asvl.db.repositories.task_repo import TaskRepository
from asvl.db.models.segment_result import SegmentResultModel
from asvl.db.models.asr_result import ASRResultModel
from asvl.models.schemas import ASRSegment, LLMResult
from asvl.models.enums import TaskStatus
from configs.settings import get_settings
from configs.logging import log

settings = get_settings()


@celery_app.task(
    bind=True,
    name="asvl.workers.tasks.llm_task.process_llm",
    retry_backoff=True,
    max_retries=3,
)
def process_llm(self, asr_result: dict, task_id: str):
    """
    LLM处理任务

    Args:
        asr_result: ASR结果（从上一个任务传递）
        task_id: 任务ID

    Returns:
        dict: 处理结果
    """
    log.info(f"Starting LLM task for {task_id}")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_process_llm_async(self, asr_result, task_id))
    finally:
        loop.close()


async def _process_llm_async(
    task,
    asr_result: dict,
    task_id: str,
) -> dict:
    """异步LLM处理"""
    start_time = datetime.now()

    # 为当前任务创建独立的引擎和会话工厂（在当前event loop中）
    engine = get_new_engine()
    session_factory = get_new_session_factory(engine)

    try:
        # 1. 更新任务状态
        await _update_task_progress(session_factory, task_id, "llm", TaskStatus.PROCESSING)

        # 2. 获取ASR结果（从参数或数据库）
        if not asr_result or "segments" not in asr_result:
            asr_result = await _get_asr_result(session_factory, task_id)

        if not asr_result or "segments" not in asr_result:
            raise ValueError("No ASR result found")

        # 获取任务选项
        video_task = await _get_video_task(session_factory, task_id)
        options = video_task.options if video_task else {}

        # 3. 转换ASR分段格式
        asr_segments = [
            ASRSegment(
                start=seg["start"],
                end=seg["end"],
                text=seg["text"],
                confidence=seg.get("confidence", 0.8),
            )
            for seg in asr_result["segments"]
        ]

        log.info(f"Processing {len(asr_segments)} ASR segments")

        # 4. 初始化LLM客户端（带限流控制）
        llm_client = LLMClient()

        # 5. 语义分段
        log.info("Running semantic segmentation...")
        segmenter = SemanticSegmenter(llm_client)
        segments = await segmenter.segment(
            asr_segments=asr_segments,
            video_duration=asr_result.get("duration"),
        )
        log.info(f"Segmentation complete: {len(segments)} segments")

        # 6. 重要性评分
        log.info("Scoring segment importance...")
        scorer = ImportanceScorer(llm_client)
        segments = await scorer.score(segments)
        log.info("Importance scoring complete")

        # 7. 视觉需求判定
        log.info("Detecting vision needs...")
        detector = VisionDetector(llm_client)

        # 检查是否强制启用VL
        force_vl = options.get("force_vl", False)
        if force_vl:
            log.info("Force VL enabled, marking top segments as need_vision")
            # 对Top 30%重要性的分段强制启用视觉分析
            sorted_segments = sorted(segments, key=lambda x: x.importance, reverse=True)
            top_k = max(1, int(len(segments) * 0.3))
            for seg in sorted_segments[:top_k]:
                seg.need_vision = True
        else:
            segments = await detector.detect(segments, use_llm=True)

        # 统计需要视觉分析的分段
        vision_count = sum(1 for s in segments if s.need_vision)
        log.info(f"Vision detection complete: {vision_count}/{len(segments)} need vision")

        # 8. 生成摘要
        summary = await _generate_summary(llm_client, segments)

        # 9. 保存结果到数据库
        await _save_segment_result(
            session_factory=session_factory,
            task_id=task_id,
            segments=segments,
            summary=summary,
            processing_time=(datetime.now() - start_time).total_seconds(),
        )

        # 10. 更新任务进度
        await _update_task_progress(session_factory, task_id, "llm", TaskStatus.COMPLETED)

        processing_time = (datetime.now() - start_time).total_seconds()
        log.info(f"LLM task completed for {task_id} in {processing_time:.1f}s")

        await engine.dispose()

        return {
            "task_id": task_id,
            "status": "completed",
            "segments_count": len(segments),
            "vision_segments_count": vision_count,
            "processing_time": processing_time,
        }

    except Exception as e:
        log.error(f"LLM task failed for {task_id}: {e}")
        await _update_task_progress(session_factory, task_id, "llm", TaskStatus.FAILED)
        await engine.dispose()
        raise


async def _get_asr_result(session_factory, task_id: str) -> dict:
    """从数据库获取ASR结果"""
    from sqlalchemy import select

    async with session_factory() as session:
        result = await session.execute(
            select(ASRResultModel).where(ASRResultModel.task_id == task_id)
        )
        asr = result.scalar_one_or_none()

        if not asr:
            return None

        return {
            "language": asr.language,
            "duration": asr.duration,
            "segments": asr.segments,
            "confidence": asr.confidence,
        }


async def _generate_summary(llm_client: LLMClient, segments: List[LLMResult]) -> str:
    """生成视频内容摘要"""
    # 获取Top 5最重要的分段
    top_segments = sorted(segments, key=lambda x: x.importance, reverse=True)[:5]

    texts = [s.text for s in top_segments]
    combined_text = "\n".join([f"- {t}" for t in texts])

    prompt = f"""请根据以下关键内容片段，生成一个简洁的视频内容摘要（100字以内）：

{combined_text}

摘要："""

    try:
        summary = await llm_client.complete(prompt=prompt, temperature=0.5, max_tokens=150)
        return summary.strip()
    except Exception as e:
        log.error(f"Summary generation failed: {e}")
        return "视频内容分析完成"


async def _save_segment_result(
    session_factory,
    task_id: str,
    segments: List[LLMResult],
    summary: str,
    processing_time: float,
) -> None:
    """保存分段结果到数据库"""
    async with session_factory() as session:
        # 转换为可序列化格式
        segments_data = [
            {
                "id": s.id,
                "start": s.start,
                "end": s.end,
                "text": s.text,
                "importance": s.importance,
                "type": s.type.value,
                "need_vision": s.need_vision,
                "confidence": s.confidence,
            }
            for s in segments
        ]

        segment_result = SegmentResultModel(
            task_id=task_id,
            segments=segments_data,
            summary=summary,
            processing_time=processing_time,
        )

        session.add(segment_result)
        await session.commit()

        log.info(f"Segment result saved: {task_id}, {len(segments)} segments")


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


async def _get_video_task(session_factory, task_id: str):
    """获取视频任务"""
    from sqlalchemy import select
    from asvl.db.models.video_task import VideoTask

    async with session_factory() as session:
        result = await session.execute(
            select(VideoTask).where(VideoTask.task_id == task_id)
        )
        return result.scalar_one_or_none()


@celery_app.task(name="asvl.workers.tasks.llm_task.get_segment_result")
def get_segment_result(task_id: str) -> dict:
    """获取分段处理结果"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_get_segment_result_async(task_id))
    finally:
        loop.close()


async def _get_segment_result_async(task_id: str) -> dict:
    """异步获取分段结果"""
    from sqlalchemy import select

    engine = get_new_engine()
    session_factory = get_new_session_factory(engine)

    async with session_factory() as session:
        result = await session.execute(
            select(SegmentResultModel).where(SegmentResultModel.task_id == task_id)
        )
        seg_result = result.scalar_one_or_none()

        await engine.dispose()

        if not seg_result:
            return {"error": "Segment result not found"}

        return {
            "task_id": task_id,
            "summary": seg_result.summary,
            "segments": seg_result.segments,
            "processing_time": seg_result.processing_time,
        }