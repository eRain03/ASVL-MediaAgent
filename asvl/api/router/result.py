"""结果获取API"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from asvl.db.session import get_session
from asvl.db.repositories.task_repo import TaskRepository
from asvl.db.models.video_task import VideoTask
from asvl.db.models.final_output import FinalOutputModel
from asvl.db.models.segment_result import SegmentResultModel
from asvl.db.models.asr_result import ASRResultModel
from asvl.db.models.vl_result import VLResultModel
from asvl.models.schemas import TaskStatus
from pydantic import BaseModel
from typing import Optional, List, Any
from configs.logging import log

router = APIRouter()


class SegmentInfo(BaseModel):
    id: str
    start: float
    end: float
    text: str
    importance: float
    type: str
    need_vision: bool


class VLResultInfo(BaseModel):
    clip_id: str
    segment_id: Optional[str] = None
    vision_summary: str
    actions: List[str] = []
    objects: List[str] = []
    scene_description: Optional[str] = None
    confidence: float


class TaskResultResponse(BaseModel):
    task_id: str
    video_id: str
    status: str
    summary: Optional[str] = None
    segments: Optional[List[SegmentInfo]] = None
    vl_results: Optional[List[VLResultInfo]] = None
    highlights: Optional[List[Any]] = None
    alignment_issues: Optional[List[Any]] = None
    asr_segments: Optional[List[dict]] = None
    duration: Optional[float] = None


@router.get("/{task_id}", response_model=TaskResultResponse)
async def get_task_result(
    task_id: str,
    session: AsyncSession = Depends(get_session),
):
    """获取任务处理结果"""
    repo = TaskRepository(session)
    task = await repo.get_by_task_id(task_id)

    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    # 获取分段结果（LLM处理结果）
    seg_result = await session.execute(
        select(SegmentResultModel).where(SegmentResultModel.task_id == task_id)
    )
    segment_data = seg_result.scalar_one_or_none()

    # 获取最终输出（融合结果）
    final_result = await session.execute(
        select(FinalOutputModel).where(FinalOutputModel.task_id == task_id)
    )
    final_data = final_result.scalar_one_or_none()

    # 获取ASR结果
    asr_result = await session.execute(
        select(ASRResultModel).where(ASRResultModel.task_id == task_id)
    )
    asr_data = asr_result.scalar_one_or_none()

    # 获取VL结果
    vl_result = await session.execute(
        select(VLResultModel).where(VLResultModel.task_id == task_id)
    )
    vl_data = vl_result.scalars().all()

    # 构建响应
    segments = None
    if segment_data and segment_data.segments:
        segments = [
            SegmentInfo(
                id=s.get("id", f"seg_{i}"),
                start=s.get("start", 0),
                end=s.get("end", 0),
                text=s.get("text", ""),
                importance=s.get("importance", 0.5),
                type=s.get("type", "背景信息"),
                need_vision=s.get("need_vision", False),
            )
            for i, s in enumerate(segment_data.segments)
        ]

    # 构建VL结果
    vl_results = None
    if vl_data:
        vl_results = [
            VLResultInfo(
                clip_id=vl.clip_id,
                segment_id=vl.clip_id.split('_')[0] if '_' in vl.clip_id else None,
                vision_summary=vl.vision_summary or "",
                actions=vl.actions or [],
                objects=vl.objects or [],
                scene_description=vl.scene_description,
                confidence=vl.confidence or 0.8,
            )
            for vl in vl_data
        ]

    # 优先使用final_output的summary，如果没有则使用segment_result的summary
    # 排除"无内容"这样的占位符
    summary = None
    if final_data and final_data.summary and final_data.summary not in ['无内容', '', None]:
        summary = final_data.summary
    elif segment_data and segment_data.summary:
        summary = segment_data.summary

    # ASR分段
    asr_segments = None
    if asr_data and asr_data.segments:
        asr_segments = asr_data.segments

    return TaskResultResponse(
        task_id=task.task_id,
        video_id=task.video_id,
        status=task.status,
        summary=summary,
        segments=segments,
        vl_results=vl_results,
        highlights=final_data.highlights if final_data else None,
        alignment_issues=final_data.alignment_issues if final_data else None,
        asr_segments=asr_segments,
        duration=asr_data.duration if asr_data else task.video_duration,
    )