"""数据库ORM模型"""
from asvl.db.models.video_task import VideoTask
from asvl.db.models.asr_result import ASRResultModel as ASRResult
from asvl.db.models.segment_result import SegmentResultModel as SegmentResult
from asvl.db.models.clip_result import ClipResultModel as ClipResult
from asvl.db.models.vl_result import VLResultModel as VLResult
from asvl.db.models.final_output import FinalOutputModel as FinalOutput

__all__ = [
    "VideoTask",
    "ASRResult",
    "SegmentResult",
    "ClipResult",
    "VLResult",
    "FinalOutput",
]