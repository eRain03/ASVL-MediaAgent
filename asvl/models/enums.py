"""枚举定义"""
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStage(str, Enum):
    """任务阶段"""
    ASR = "asr"
    LLM = "llm"
    CLIP = "clip"
    VL = "vl"
    FUSION = "fusion"


class SegmentType(str, Enum):
    """片段类型"""
    CORE_VIEWPOINT = "核心观点"
    OPERATION_DEMO = "操作演示"
    EMOTIONAL_EXPRESSION = "情绪表达"
    BACKGROUND_INFO = "背景信息"
    DATA_ANALYSIS = "数据分析"
    UI_OPERATION = "UI操作"


class AlignmentStatus(str, Enum):
    """对齐状态"""
    CONSISTENT = "consistent"
    CONFLICT = "conflict"
    INSUFFICIENT = "insufficient"


class ASRProvider(str, Enum):
    """ASR提供商"""
    ALIYUN = "aliyun"
    FASTER_WHISPER = "faster_whisper"