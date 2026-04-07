"""多模态融合抽象基类"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from asvl.models.schemas import LLMResult, VLResult, AlignmentIssue, Highlight


class FusionBase(ABC):
    """多模态融合模块抽象基类"""

    @abstractmethod
    async def align(
        self,
        llm_result: LLMResult,
        vl_result: Optional[VLResult],
    ) -> AlignmentIssue:
        """
        文本-视觉对齐

        Args:
            llm_result: LLM分析结果
            vl_result: VL分析结果（可选）

        Returns:
            AlignmentIssue: 对齐结果
        """
        pass

    @abstractmethod
    async def merge(
        self,
        llm_results: List[LLMResult],
        vl_results: Dict[str, VLResult],
    ) -> List[Highlight]:
        """
        信息融合

        Args:
            llm_results: LLM分析结果列表
            vl_results: VL分析结果字典（key为segment_id）

        Returns:
            List[Highlight]: 高亮片段列表
        """
        pass

    @abstractmethod
    async def enhance(
        self,
        highlight: Highlight,
        vl_result: Optional[VLResult],
    ) -> Highlight:
        """
        语义增强

        Args:
            highlight: 高亮片段
            vl_result: VL结果（可选）

        Returns:
            Highlight: 增强后的高亮片段
        """
        pass