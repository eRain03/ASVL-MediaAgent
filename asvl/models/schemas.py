"""Pydantic数据模型"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from asvl.models.enums import TaskStatus, SegmentType, AlignmentStatus


class TaskProgress(BaseModel):
    """任务进度"""
    asr: TaskStatus = TaskStatus.PENDING
    llm: TaskStatus = TaskStatus.PENDING
    clip: TaskStatus = TaskStatus.PENDING
    vl: TaskStatus = TaskStatus.PENDING
    fusion: TaskStatus = TaskStatus.PENDING


class TaskOptions(BaseModel):
    """任务选项"""
    language: Optional[str] = "zh"
    vl_enabled: bool = True
    vl_top_k: int = Field(default=20, ge=1, le=100)
    callback_url: Optional[str] = None


class TaskCreateRequest(BaseModel):
    """创建任务请求"""
    video_url: str
    video_id: Optional[str] = None
    options: Optional[TaskOptions] = None


class TaskCreateResponse(BaseModel):
    """创建任务响应"""
    task_id: str
    status: TaskStatus
    created_at: datetime


class ASRSegment(BaseModel):
    """ASR分段"""
    start: float = Field(ge=0, description="开始时间(秒)")
    end: float = Field(ge=0, description="结束时间(秒)")
    text: str = Field(description="文本内容")
    confidence: float = Field(ge=0, le=1, description="置信度")


class ASRResult(BaseModel):
    """ASR结果"""
    language: Optional[str] = None
    duration: float
    segments: List[ASRSegment]
    confidence: float = Field(ge=0, le=1)


class LLMResult(BaseModel):
    """LLM分析结果"""
    id: str
    start: float
    end: float
    text: str
    importance: float = Field(ge=0, le=1, description="重要性评分")
    type: SegmentType = Field(description="片段类型")
    need_vision: bool = Field(description="是否需要视觉分析")
    confidence: float = Field(ge=0, le=1)


class SegmentResult(BaseModel):
    """分段结果"""
    summary: Optional[str] = None
    segments: List[LLMResult]


class VLResult(BaseModel):
    """VL视觉理解结果"""
    clip_id: str
    vision_summary: str
    actions: List[str] = Field(default_factory=list)
    objects: List[str] = Field(default_factory=list)
    scene_description: Optional[str] = None
    confidence: float = Field(ge=0, le=1)


class ClipResult(BaseModel):
    """视频片段结果"""
    clip_id: str
    segment_id: str
    clip_url: Optional[str] = None
    start_time: float
    end_time: float
    duration: float
    storage_path: Optional[str] = None


class AlignmentIssue(BaseModel):
    """对齐问题"""
    segment_id: str
    status: AlignmentStatus
    text_claim: str
    vision_finding: str
    reason: Optional[str] = None


class Highlight(BaseModel):
    """高亮片段"""
    type: SegmentType
    text: str
    time: List[float] = Field(description="[start, end]")
    importance: float = Field(ge=0, le=1)
    visual_explanation: Optional[str] = None
    clip_url: Optional[str] = None


class TaskResult(BaseModel):
    """任务最终结果"""
    task_id: str
    video_id: str
    status: TaskStatus
    summary: Optional[str] = None
    duration: Optional[float] = None
    segments: Optional[List[LLMResult]] = None
    highlights: Optional[List[Highlight]] = None
    alignment_issues: Optional[List[AlignmentIssue]] = None


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    status: TaskStatus
    progress: TaskProgress
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None