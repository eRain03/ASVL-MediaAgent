"""多模态融合任务 - 完整实现"""
import asyncio
from datetime import datetime
from typing import List, Dict

from asvl.workers.celery_app import celery_app
from asvl.core.fusion import (
    CrossModalAligner,
    InfoFusioner,
    SemanticEnhancer,
)
from asvl.core.llm.client import LLMClient
from asvl.db.session import get_new_engine, get_new_session_factory
from asvl.db.repositories.task_repo import TaskRepository
from asvl.db.models.final_output import FinalOutputModel
from asvl.db.models.segment_result import SegmentResultModel
from asvl.db.models.vl_result import VLResultModel
from asvl.models.schemas import LLMResult, VLResult, Highlight
from asvl.models.enums import TaskStatus
from configs.settings import get_settings
from configs.logging import log
import json

settings = get_settings()


@celery_app.task(
    bind=True,
    name="asvl.workers.tasks.fusion_task.process_fusion",
)
def process_fusion(self, vl_results: dict, task_id: str):
    """
    多模态融合任务

    Args:
        vl_results: VL结果（从上一个任务传递）
        task_id: 任务ID

    Returns:
        dict: 处理结果
    """
    log.info(f"Starting Fusion task for {task_id}")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_process_fusion_async(self, vl_results, task_id))
    finally:
        loop.close()


async def _process_fusion_async(
    task,
    vl_results: dict,
    task_id: str,
) -> dict:
    """异步融合处理"""
    start_time = datetime.now()

    # 为当前任务创建独立的引擎和会话工厂（在当前event loop中）
    engine = get_new_engine()
    session_factory = get_new_session_factory(engine)

    try:
        # 1. 更新任务状态
        await _update_task_progress(session_factory, task_id, "fusion", TaskStatus.PROCESSING)

        # 2. 获取LLM结果
        llm_result = await _get_segment_result(session_factory, task_id)

        if not llm_result:
            raise ValueError(f"No LLM result found for {task_id}")

        # 3. 获取VL结果（如果参数是 dict 且不是 VL 结果格式，则从数据库获取）
        if not vl_results or (isinstance(vl_results, dict) and "task_id" in vl_results):
            vl_results = await _get_vl_results(session_factory, task_id)

        # 4. 转换数据格式
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
            for s in llm_result.get("segments", [])
        ]

        vl_dict = {}
        for clip_id, vl in vl_results.items():
            vl_dict[clip_id] = VLResult(
                clip_id=vl.get("clip_id", clip_id),
                vision_summary=vl.get("vision_summary", ""),
                actions=vl.get("actions", []),
                objects=vl.get("objects", []),
                scene_description=vl.get("scene_description"),
                confidence=vl.get("confidence", 0.8),
            )

        log.info(f"Fusing {len(llm_segments)} segments with {len(vl_dict)} VL results")

        # 5. 初始化LLM客户端
        llm_client = LLMClient()

        # 6. 双模态对齐
        log.info("Running cross-modal alignment...")
        aligner = CrossModalAligner(llm_client)
        alignment_issues = await aligner.batch_align(llm_segments, vl_dict)

        # 7. 信息融合
        log.info("Fusing information...")
        fusioner = InfoFusioner(llm_client)
        highlights = await fusioner.merge(llm_segments, vl_dict)

        # 8. 语义增强
        log.info("Enhancing semantics...")
        enhancer = SemanticEnhancer(llm_client)
        for highlight in highlights:
            vl_result = vl_dict.get(highlight.type.value)  # 简化匹配
            await enhancer.enhance(highlight, vl_result)

        # 9. 生成摘要（优先使用VL结果）
        if vl_dict:
            # 有VL结果，基于视觉内容生成摘要
            vl_summaries = [vl.vision_summary for vl in vl_dict.values() if vl.vision_summary]
            if vl_summaries:
                summary = await _generate_vl_summary(llm_client, vl_summaries, llm_segments)
            else:
                summary = await enhancer.generate_summary(highlights)
        else:
            summary = await enhancer.generate_summary(highlights)

        # 10. 保存最终结果
        await _save_final_output(
            session_factory=session_factory,
            task_id=task_id,
            summary=summary,
            highlights=highlights,
            alignment_issues=alignment_issues,
        )

        # 11. 更新任务进度为完成
        await _update_task_progress(session_factory, task_id, "fusion", TaskStatus.COMPLETED)

        # 12. 更新任务状态为完成
        await _update_task_status(session_factory, task_id, TaskStatus.COMPLETED)

        processing_time = (datetime.now() - start_time).total_seconds()
        log.info(f"Fusion task completed for {task_id}: {len(highlights)} highlights in {processing_time:.1f}s")

        await engine.dispose()

        return {
            "task_id": task_id,
            "status": "completed",
            "highlights_count": len(highlights),
            "alignment_conflicts": sum(1 for a in alignment_issues if a.status == "conflict"),
            "processing_time": processing_time,
        }

    except Exception as e:
        log.error(f"Fusion task failed for {task_id}: {e}")
        await _update_task_status(session_factory, task_id, TaskStatus.FAILED)
        await engine.dispose()
        raise


async def _get_segment_result(session_factory, task_id: str) -> dict:
    """获取分段结果"""
    from sqlalchemy import select

    async with session_factory() as session:
        result = await session.execute(
            select(SegmentResultModel).where(SegmentResultModel.task_id == task_id)
        )
        seg_result = result.scalar_one_or_none()

        if not seg_result:
            return None

        return {
            "summary": seg_result.summary,
            "segments": seg_result.segments,
        }


async def _get_vl_results(session_factory, task_id: str) -> dict:
    """获取VL结果"""
    from sqlalchemy import select

    async with session_factory() as session:
        result = await session.execute(
            select(VLResultModel).where(VLResultModel.task_id == task_id)
        )
        vl_results = result.scalars().all()

        # 使用segment_id作为key
        return {
            vl.segment_id or vl.clip_id: {
                "clip_id": vl.clip_id,
                "segment_id": vl.segment_id,
                "vision_summary": vl.vision_summary,
                "actions": vl.actions or [],
                "objects": vl.objects or [],
                "scene_description": vl.scene_description,
                "confidence": vl.confidence,
            }
            for vl in vl_results
        }


async def _save_final_output(
    session_factory,
    task_id: str,
    summary: str,
    highlights: List[Highlight],
    alignment_issues: List,
) -> None:
    """保存最终输出"""
    async with session_factory() as session:
        # 转换为可序列化格式
        highlights_data = [
            {
                "type": h.type.value if hasattr(h.type, 'value') else str(h.type),
                "text": h.text,
                "visual_explanation": h.visual_explanation,
                "time": h.time,
                "importance": h.importance,
            }
            for h in highlights
        ]

        alignment_data = [
            {
                "segment_id": a.segment_id,
                "status": a.status.value if hasattr(a.status, 'value') else str(a.status),
                "text_claim": a.text_claim,
                "vision_finding": a.vision_finding,
                "reason": a.reason,
            }
            for a in alignment_issues
        ]

        full_result = {
            "summary": summary,
            "highlights": highlights_data,
            "alignment_issues": alignment_data,
        }

        output = FinalOutputModel(
            task_id=task_id,
            summary=summary,
            highlights=highlights_data,
            alignment_issues=alignment_data,
            full_result=full_result,
        )

        session.add(output)
        await session.commit()

        log.info(f"Final output saved for {task_id}")


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


async def _update_task_status(
    session_factory,
    task_id: str,
    status: TaskStatus,
    error_message: str = None,
) -> None:
    """更新任务状态"""
    async with session_factory() as session:
        repo = TaskRepository(session)
        await repo.update_status(task_id, status, error_message)


async def _generate_vl_summary(
    llm_client: LLMClient,
    vl_summaries: List[str],
    llm_segments: List[LLMResult],
) -> str:
    """基于VL结果生成摘要"""
    # 组合VL摘要
    vl_text = "\n".join([f"- {s}" for s in vl_summaries[:3]])

    # 获取文本内容
    text_content = "\n".join([f"- {s.text[:100]}" for s in llm_segments[:3]])

    prompt = f"""请根据以下视觉分析和文本内容，生成视频内容摘要（100字以内）：

视觉分析：
{vl_text}

文本内容：
{text_content}

注意：如果视觉内容与文本内容不一致，以视觉内容为准。

摘要："""

    try:
        summary = await llm_client.complete(
            prompt=prompt,
            temperature=0.5,
            max_tokens=200,
        )
        return summary.strip()
    except Exception as e:
        log.error(f"VL summary generation failed: {e}")
        # 返回VL摘要
        return vl_summaries[0] if vl_summaries else "视频内容分析完成"