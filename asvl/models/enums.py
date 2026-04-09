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


class AudioEventType(str, Enum):
    """音频事件类型"""
    SPEECH = "Speech"       # 人声/语音
    BGM = "BGM"             # 背景音乐
    MUSIC = "Music"         # 音乐
    LAUGHTER = "Laughter"   # 笑声
    APPLAUSE = "Applause"   # 掌声
    NOISE = "Noise"         # 噪音
    SILENCE = "Silence"     # 静音


class AttractionType(str, Enum):
    """看点类型"""
    INFORMATION = "信息价值"
    VISUAL_IMPACT = "视觉冲击"
    EMOTIONAL = "情感共鸣"
    SUSPENSE = "悬念冲突"
    DEMO = "操作演示"
    ATMOSPHERE = "氛围营造"