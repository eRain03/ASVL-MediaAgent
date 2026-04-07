"""重要性评分器"""
from typing import List, Optional, Dict
from asvl.core.llm.client import LLMClient
from asvl.models.schemas import LLMResult
from configs.prompts.segment_prompt import SEGMENT_IMPORTANCE_PROMPT
from configs.logging import log
import json


class ImportanceScorer:
    """
    重要性评分器

    对语义分段进行多维度重要性评分：
    - 信息量：内容的信息密度和价值
    - 独特性：是否包含独特见解或关键信息
    - 相关性：与主题的相关程度
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()
        log.info("ImportanceScorer initialized")

    async def score(
        self,
        segments: List[LLMResult],
        context: Optional[str] = None,
    ) -> List[LLMResult]:
        """
        对分段进行重要性评分

        Args:
            segments: 语义分段列表
            context: 全局上下文（如视频标题、摘要）

        Returns:
            List[LLMResult]: 带评分的分段列表
        """
        if not segments:
            return segments

        log.info(f"Scoring {len(segments)} segments")

        # 批量评分
        for i, seg in enumerate(segments):
            try:
                scores = await self._score_segment(seg, context)
                seg.importance = scores["importance"]
                log.debug(f"Segment {i} scored: {scores['importance']:.2f}")
            except Exception as e:
                log.warning(f"Failed to score segment {i}: {e}")
                # 使用默认评分
                seg.importance = self._default_score(seg)

        # 归一化评分到0-1
        self._normalize_scores(segments)

        log.info(f"Scoring completed, avg importance: {sum(s.importance for s in segments)/len(segments):.2f}")
        return segments

    async def _score_segment(
        self,
        segment: LLMResult,
        context: Optional[str] = None,
    ) -> Dict:
        """对单个分段评分"""
        duration = segment.end - segment.start

        prompt = SEGMENT_IMPORTANCE_PROMPT.format(
            text=segment.text[:500],  # 限制长度
            type=segment.type.value,
            duration=duration,
        )

        response = await self.llm.complete_json(
            prompt=prompt,
            temperature=0.2,
        )

        return response

    def _default_score(self, segment: LLMResult) -> float:
        """默认评分（基于规则）"""
        base_score = 0.5

        # 根据类型调整
        type_scores = {
            "核心观点": 0.9,
            "操作演示": 0.7,
            "数据分析": 0.8,
            "UI操作": 0.6,
            "情绪表达": 0.4,
            "背景信息": 0.3,
        }
        type_score = type_scores.get(segment.type.value, 0.5)

        # 根据长度调整
        duration = segment.end - segment.start
        if duration < 10:
            length_factor = 0.8
        elif duration > 120:
            length_factor = 1.2
        else:
            length_factor = 1.0

        # 综合评分
        final_score = (base_score + type_score) / 2 * length_factor
        return min(1.0, max(0.0, final_score))

    def _normalize_scores(self, segments: List[LLMResult]) -> None:
        """归一化评分"""
        if not segments:
            return

        scores = [s.importance for s in segments]
        min_score = min(scores)
        max_score = max(scores)

        if max_score == min_score:
            return

        for seg in segments:
            seg.importance = (seg.importance - min_score) / (max_score - min_score)

    async def get_top_segments(
        self,
        segments: List[LLMResult],
        top_k: int = 10,
        min_importance: float = 0.5,
    ) -> List[LLMResult]:
        """
        获取最重要的K个分段

        Args:
            segments: 分段列表
            top_k: 返回数量
            min_importance: 最低重要性阈值

        Returns:
            List[LLMResult]: Top-K分段
        """
        # 过滤低重要性分段
        filtered = [s for s in segments if s.importance >= min_importance]

        # 按重要性排序
        sorted_segments = sorted(filtered, key=lambda x: x.importance, reverse=True)

        return sorted_segments[:top_k]


async def score_segments(
    segments: List[LLMResult],
    llm_client: Optional[LLMClient] = None,
) -> List[LLMResult]:
    """
    便捷函数：对分段进行重要性评分
    """
    scorer = ImportanceScorer(llm_client)
    return await scorer.score(segments)