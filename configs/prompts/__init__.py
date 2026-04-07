"""Prompt模板包"""
from configs.prompts.segment_prompt import SEGMENT_PROMPT, SEGMENT_IMPORTANCE_PROMPT
from configs.prompts.vision_detect_prompt import VISION_DETECT_PROMPT, VL_ANALYSIS_PROMPT
from configs.prompts.fusion_prompt import ALIGNMENT_PROMPT, FUSION_PROMPT

__all__ = [
    "SEGMENT_PROMPT",
    "SEGMENT_IMPORTANCE_PROMPT",
    "VISION_DETECT_PROMPT",
    "VL_ANALYSIS_PROMPT",
    "ALIGNMENT_PROMPT",
    "FUSION_PROMPT",
]