"""多模态融合模块"""
from asvl.core.fusion.base import FusionBase
from asvl.core.fusion.aligner import CrossModalAligner, align_text_vision
from asvl.core.fusion.merger import InfoFusioner, SemanticEnhancer, fuse_results
from asvl.core.fusion.attraction_analyzer import AttractionAnalyzer

__all__ = [
    "FusionBase",
    "CrossModalAligner",
    "align_text_vision",
    "InfoFusioner",
    "SemanticEnhancer",
    "fuse_results",
    "AttractionAnalyzer",
]