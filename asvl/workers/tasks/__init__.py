"""Tasks模块"""
from asvl.workers.tasks.asr_task import process_asr
from asvl.workers.tasks.llm_task import process_llm
from asvl.workers.tasks.clip_task import process_clip
from asvl.workers.tasks.vl_task import process_vl
from asvl.workers.tasks.fusion_task import process_fusion

__all__ = ["process_asr", "process_llm", "process_clip", "process_vl", "process_fusion"]