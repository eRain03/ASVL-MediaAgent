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
from asvl.db.session import async_session
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
def process_fusion(self, task_id: str, llm_result: dict = None, vl_results: dict = None):
    """
    多模态融合任务

    Args:
        task_id: 任务ID
        llm_result: LLM结果（可选）
        vl_results: VL结果（可选）

    Returns:
        dict: 处理结果
    """
    log.info(f"Starting Fusion task for {task_id}")
    return asyncio.run(_process_fusion_async(self, task_id, llm_result, vl_results))


async def _process_fusion_async(
    task,
    task_id: str,
    llm_result: dict,
    vl_results: dict,
) -> dict:
    """异步融合处理"""
    start_time = datetime.now()

    try:
        # 1. 更新任务状态
        await _update_task_progress(task_id, "fusion", TaskStatus.PROCESSING)

        # 2. 获取LLM结果
        if not llm_result:
            llm_result = await _get_segment_result(task_id)

        if not llm_result:
            raise ValueError(f"No LLM result found for {task_id}")

        # 3. 获取VL结果
        if not vl_results:
            vl_results = await _get_vl_results(task_id)

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

        # 9. 生成摘要
        summary = await enhancer.generate_summary(highlights)

        # 10. 保存最终结果
        await _save_final_output(
            task_id=task_id,
            summary=summary,
            highlights=highlights,
            alignment_issues=alignment_issues,
        )

        # 11. 更新任务状态为完成
        await _update_task_status(task_id, TaskStatus.COMPLETED)

        processing_time = (datetime.now() - start_time).total_seconds()
        log.info(f"Fusion task completed for {task_id}: {len(highlights)} highlights in {processing_time:.1f}s")

        return {
            "task_id": task_id,
            "status": "completed",
            "highlights_count": len(highlights),
            "alignment_conflicts": sum(1 for a in alignment_issues if a.status == "conflict"),
            "processing_time": processing_time,
        }

    except Exception as e:
        log.error(f"Fusion task failed for {task_id}: {e}")
        await _update_task_status(task_id, TaskStatus.FAILED)
        raise


async def _get_segment_result(task_id: str) -> dict:
    """获取分段结果"""
    from sqlalchemy import select

    async with async_session() as session:
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


async def _get_vl_results(task_id: str) -> dict:
    """获取VL结果"""
    from sqlalchemy import select

    async with async_session() as session:
        result = await session.execute(
            select(VLResultModel).where(VLResultModel.task_id == task_id)
        )
        vl_results = result.scalars().all()

        return {
            vl.clip_id: {
                "clip_id": vl.clip_id,
                "vision_summary": vl.vision_summary,
                "actions": vl.actions or [],
                "objects": vl.objects or [],
                "scene_description": vl.scene_description,
                "confidence": vl.confidence,
            }
            for vl in vl_results
        }


async def _save_final_output(
    task_id: str,
    summary: str,
    highlights: List[Highlight],
    alignment_issues: List,
) -> None:
    """保存最终输出"""
    async with async_session() as session:
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
    task_id: str,
    stage: str,
    status: TaskStatus,
) -> None:
    """更新任务进度"""
    async with async_session() as session:
        repo = TaskRepository(session)
        await repo.update_progress(task_id, stage, status)


async def _update_task_status(
    task_id: str,
    status: TaskStatus,
    error_message: str = None,
) -> None:
    """更新任务状态"""
    async with async_session() as session:
        repo = TaskRepository(session)
        await repo.update_status(task_id, status, error_message)