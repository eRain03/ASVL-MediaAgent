"""语义分段器"""
from typing import List, Optional
from asvl.core.llm.client import LLMClient
from asvl.models.schemas import ASRSegment, LLMResult
from asvl.models.enums import SegmentType
from configs.prompts.segment_prompt import SEGMENT_PROMPT
from configs.settings import get_settings
from configs.logging import log
import json

settings = get_settings()


class SemanticSegmenter:
    """
    语义分段器

    将ASR转录文本划分为语义完整的段落，并标注类型和重要性。
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()
        self.min_segment_duration = 10.0  # 最短段落时长（秒）
        self.max_segment_duration = 180.0  # 最长段落时长（秒）

        log.info("SemanticSegmenter initialized")

    async def segment(
        self,
        asr_segments: List[ASRSegment],
        video_duration: float = None,
    ) -> List[LLMResult]:
        """
        对ASR结果进行语义分段

        Args:
            asr_segments: ASR分段列表
            video_duration: 视频总时长

        Returns:
            List[LLMResult]: 语义分段结果
        """
        if not asr_segments:
            return []

        # 1. 合并ASR文本（按时间窗口）
        merged_text = self._merge_asr_segments(asr_segments)

        # 2. 调用LLM进行分段
        log.info(f"Segmenting {len(merged_text)} text chunks")

        all_results = []
        for i, text_chunk in enumerate(merged_text):
            log.info(f"Processing text chunk {i+1}/{len(merged_text)}")

            try:
                results = await self._segment_chunk(text_chunk)
                all_results.extend(results)
            except Exception as e:
                log.error(f"Segmentation failed for chunk {i}: {e}")
                # 使用默认分段
                fallback = self._fallback_segment(text_chunk, i)
                all_results.extend(fallback)

        # 3. 后处理：合并过短段落、拆分过长段落
        all_results = self._post_process(all_results)

        log.info(f"Segmentation completed: {len(all_results)} segments")
        return all_results

    def _merge_asr_segments(
        self,
        segments: List[ASRSegment],
        window_size: float = 300.0,  # 5分钟窗口
    ) -> List[dict]:
        """
        合并ASR分段为文本块

        按时间窗口合并，避免单个请求过长。
        """
        if not segments:
            return []

        merged = []
        current_chunk = {
            "start": segments[0].start,
            "end": segments[0].end,
            "text": segments[0].text,
        }

        for seg in segments[1:]:
            # 如果当前窗口超过限制，开始新窗口
            if seg.end - current_chunk["start"] > window_size:
                merged.append(current_chunk)
                current_chunk = {
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text,
                }
            else:
                current_chunk["end"] = seg.end
                current_chunk["text"] += " " + seg.text

        # 添加最后一个块
        merged.append(current_chunk)

        log.info(f"Merged {len(segments)} ASR segments into {len(merged)} chunks")
        return merged

    async def _segment_chunk(self, text_chunk: dict) -> List[LLMResult]:
        """使用LLM分段单个文本块"""
        prompt = SEGMENT_PROMPT.format(text=text_chunk["text"])

        response = await self.llm.complete_json(
            prompt=prompt,
            temperature=0.3,
        )

        results = []
        segments_data = response.get("segments", [])
        time_offset = text_chunk["start"]

        for i, seg in enumerate(segments_data):
            try:
                llm_result = LLMResult(
                    id=f"seg_{int(time_offset)}_{i:03d}",
                    start=seg.get("start", 0) + time_offset,
                    end=seg.get("end", 0) + time_offset,
                    text=seg.get("text", ""),
                    importance=seg.get("importance", 0.5),
                    type=self._parse_segment_type(seg.get("type", "背景信息")),
                    need_vision=seg.get("need_vision", False),
                    confidence=0.8,  # 默认置信度
                )
                results.append(llm_result)
            except Exception as e:
                log.warning(f"Failed to parse segment: {e}")
                continue

        return results

    def _parse_segment_type(self, type_str: str) -> SegmentType:
        """解析段落类型"""
        type_mapping = {
            "核心观点": SegmentType.CORE_VIEWPOINT,
            "操作演示": SegmentType.OPERATION_DEMO,
            "情绪表达": SegmentType.EMOTIONAL_EXPRESSION,
            "背景信息": SegmentType.BACKGROUND_INFO,
            "数据分析": SegmentType.DATA_ANALYSIS,
            "UI操作": SegmentType.UI_OPERATION,
        }
        return type_mapping.get(type_str, SegmentType.BACKGROUND_INFO)

    def _fallback_segment(
        self,
        text_chunk: dict,
        chunk_index: int,
    ) -> List[LLMResult]:
        """分段失败的降级处理"""
        return [
            LLMResult(
                id=f"seg_{chunk_index}_fallback",
                start=text_chunk["start"],
                end=text_chunk["end"],
                text=text_chunk["text"][:500],  # 截断
                importance=0.5,
                type=SegmentType.BACKGROUND_INFO,
                need_vision=False,
                confidence=0.3,
            )
        ]

    def _post_process(self, segments: List[LLMResult]) -> List[LLMResult]:
        """后处理：合并/拆分段落"""
        if not segments:
            return segments

        processed = []
        current = None

        for seg in segments:
            duration = seg.end - seg.start

            if current is None:
                current = seg
            elif (current.end - current.start) + duration < self.min_segment_duration:
                # 合并过短段落
                current = LLMResult(
                    id=current.id,
                    start=current.start,
                    end=seg.end,
                    text=current.text + " " + seg.text,
                    importance=max(current.importance, seg.importance),
                    type=current.type if current.importance >= seg.importance else seg.type,
                    need_vision=current.need_vision or seg.need_vision,
                    confidence=min(current.confidence, seg.confidence),
                )
            else:
                processed.append(current)
                current = seg

        if current:
            processed.append(current)

        return processed


async def segment_transcript(
    asr_segments: List[ASRSegment],
    llm_client: Optional[LLMClient] = None,
) -> List[LLMResult]:
    """
    便捷函数：对ASR结果进行语义分段

    Args:
        asr_segments: ASR分段列表
        llm_client: LLM客户端

    Returns:
        List[LLMResult]: 语义分段结果
    """
    segmenter = SemanticSegmenter(llm_client)
    return await segmenter.segment(asr_segments)