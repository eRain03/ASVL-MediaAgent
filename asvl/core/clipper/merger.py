"""片段合并器"""
from typing import List, Tuple
from asvl.models.schemas import LLMResult
from configs.settings import get_settings
from configs.logging import log

settings = get_settings()


class ClipMerger:
    """
    片段合并器

    处理相邻片段的合并逻辑：
    - 合并时间间隔小于阈值的片段
    - 限制合并后的最大时长
    """

    def __init__(
        self,
        merge_gap: float = 5.0,  # 小于5秒间隔的片段合并
        max_merged_duration: float = 300.0,  # 合并后最大5分钟
    ):
        self.merge_gap = merge_gap
        self.max_merged_duration = max_merged_duration

        log.info(f"ClipMerger initialized: gap={merge_gap}s, max={max_merged_duration}s")

    def merge_adjacent(
        self,
        segments: List[LLMResult],
    ) -> List[LLMResult]:
        """
        合并相邻片段

        Args:
            segments: 分段列表

        Returns:
            List[LLMResult]: 合并后的分段列表
        """
        if len(segments) <= 1:
            return segments

        # 按开始时间排序
        sorted_segments = sorted(segments, key=lambda x: x.start)

        merged = []
        current = sorted_segments[0]

        for seg in sorted_segments[1:]:
            gap = seg.start - current.end

            # 检查是否需要合并
            if gap <= self.merge_gap:
                # 合并
                new_duration = seg.end - current.start

                if new_duration <= self.max_merged_duration:
                    current = self._merge_two(current, seg)
                    continue

            # 不合并，保存当前片段
            merged.append(current)
            current = seg

        # 添加最后一个片段
        merged.append(current)

        log.info(f"Merged {len(segments)} segments into {len(merged)}")
        return merged

    def _merge_two(self, seg1: LLMResult, seg2: LLMResult) -> LLMResult:
        """合并两个片段"""
        return LLMResult(
            id=f"{seg1.id}_merged",
            start=seg1.start,
            end=seg2.end,
            text=f"{seg1.text} {seg2.text}",
            importance=max(seg1.importance, seg2.importance),
            type=seg1.type if seg1.importance >= seg2.importance else seg2.type,
            need_vision=seg1.need_vision or seg2.need_vision,
            confidence=min(seg1.confidence, seg2.confidence),
        )

    def get_clip_ranges(
        self,
        segments: List[LLMResult],
        padding: float = 2.0,
    ) -> List[Tuple[float, float]]:
        """
        获取需要裁剪的时间范围

        Args:
            segments: 分段列表
            padding: 时间padding

        Returns:
            List[Tuple[float, float]]: 时间范围列表 [(start, end), ...]
        """
        # 先合并相邻片段
        merged = self.merge_adjacent(segments)

        # 生成时间范围（带padding）
        ranges = []
        for seg in merged:
            start = max(0, seg.start - padding)
            end = seg.end + padding
            ranges.append((start, end))

        return ranges