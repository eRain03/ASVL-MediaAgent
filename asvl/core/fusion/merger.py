"""信息融合器"""
from typing import List, Dict, Optional
from asvl.core.llm.client import LLMClient
from asvl.models.schemas import LLMResult, VLResult, Highlight, AlignmentIssue, UserAttraction
from asvl.models.enums import SegmentType
from asvl.core.fusion.attraction_analyzer import AttractionAnalyzer
from configs.prompts.fusion_prompt import FUSION_PROMPT
from configs.settings import get_settings
from configs.logging import log
import json

settings = get_settings()


class InfoFusioner:
    """
    信息融合器

    将LLM和VL的分析结果融合：
    - 多源信息聚合
    - 权重计算
    - 冲突解决
    - 看点分析
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()
        self.attraction_analyzer = AttractionAnalyzer(llm_client)
        log.info("InfoFusioner initialized")

    async def merge(
        self,
        llm_results: List[LLMResult],
        vl_results: Dict[str, VLResult],
        min_importance: float = 0.3,  # 降低阈值，确保更多内容生成高亮
        alignment_issues: Optional[List[AlignmentIssue]] = None,
        audio_events_map: Optional[Dict[str, List[str]]] = None,
    ) -> List[Highlight]:
        """
        信息融合

        Args:
            llm_results: LLM分析结果列表
            vl_results: VL分析结果字典
            min_importance: 最小重要性阈值
            alignment_issues: 对齐问题列表（用于看点分析）
            audio_events_map: 音频事件映射（用于看点分析）

        Returns:
            List[Highlight]: 高亮片段列表
        """
        highlights = []

        # 构建对齐问题索引
        alignment_map = {}
        if alignment_issues:
            alignment_map = {a.segment_id: a for a in alignment_issues}

        for llm_result in llm_results:
            # 过滤低重要性分段
            if llm_result.importance < min_importance:
                continue

            vl_result = vl_results.get(llm_result.id)

            # 获取对齐问题
            alignment = alignment_map.get(llm_result.id)

            # 获取音频事件
            audio_events = None
            if audio_events_map:
                # 先尝试精确时间匹配
                time_key = f"{llm_result.start}-{llm_result.end}"
                audio_events = audio_events_map.get(time_key)

                # 如果没有精确匹配，使用全局音频事件
                if not audio_events and "_global" in audio_events_map:
                    audio_events = audio_events_map["_global"]

            try:
                highlight = await self._fuse_single(
                    llm_result, vl_result, alignment, audio_events
                )
                highlights.append(highlight)
            except Exception as e:
                log.error(f"Fusion failed for {llm_result.id}: {e}")
                # 使用简单融合
                highlight = self._simple_fuse(llm_result, vl_result)
                highlights.append(highlight)

        # 按重要性排序
        highlights.sort(key=lambda x: x.importance, reverse=True)

        log.info(f"Fusion complete: {len(highlights)} highlights generated")
        return highlights

    async def _fuse_single(
        self,
        llm_result: LLMResult,
        vl_result: Optional[VLResult],
        alignment_issue: Optional[AlignmentIssue] = None,
        audio_events: Optional[List[str]] = None,
    ) -> Highlight:
        """融合单个分段"""
        # 看点分析
        user_attraction = None
        if self.attraction_analyzer.enabled:
            user_attraction = await self.attraction_analyzer.analyze(
                llm_result, vl_result, alignment_issue, audio_events
            )

        # 音频上下文
        audio_context = self._build_audio_context(audio_events)

        if vl_result:
            # 使用LLM融合
            prompt = FUSION_PROMPT.format(
                text_result=json.dumps({
                    "text": llm_result.text,
                    "importance": llm_result.importance,
                    "type": llm_result.type.value,
                }, ensure_ascii=False),
                vision_result=json.dumps({
                    "summary": vl_result.vision_summary,
                    "actions": vl_result.actions,
                    "objects": vl_result.objects,
                }, ensure_ascii=False),
            )

            response = await self.llm.complete_json(
                prompt=prompt,
                temperature=0.3,
            )

            return Highlight(
                type=llm_result.type,
                text=response.get("text", llm_result.text[:200]),
                visual_explanation=response.get("visual_explanation"),
                time=[llm_result.start, llm_result.end],
                importance=response.get("importance", llm_result.importance),
                user_attraction=user_attraction,
                audio_context=audio_context,
            )
        else:
            # 无VL结果，直接使用LLM结果
            highlight = self._simple_fuse(llm_result, None)
            highlight.user_attraction = user_attraction
            highlight.audio_context = audio_context
            return highlight

    def _build_audio_context(self, audio_events: Optional[List[str]]) -> Optional[str]:
        """构建音频上下文描述"""
        if not audio_events:
            return None

        # 判断主要音频类型
        has_speech = "Speech" in audio_events
        has_bgm = "BGM" in audio_events or "Music" in audio_events

        if has_speech and has_bgm:
            return "人声+背景音乐"
        elif has_speech:
            return "有人声讲解"
        elif has_bgm:
            return "背景音乐"
        else:
            return f"音频类型: {', '.join(audio_events)}"

    def _simple_fuse(
        self,
        llm_result: LLMResult,
        vl_result: Optional[VLResult],
    ) -> Highlight:
        """简单融合（不使用LLM）"""
        visual_explanation = None

        if vl_result:
            # 构建视觉补充说明
            parts = []
            if vl_result.actions:
                parts.append(f"动作: {', '.join(vl_result.actions)}")
            if vl_result.objects:
                parts.append(f"元素: {', '.join(vl_result.objects)}")
            if vl_result.vision_summary:
                parts.append(f"场景: {vl_result.vision_summary[:100]}")

            visual_explanation = " | ".join(parts)

        return Highlight(
            type=llm_result.type,
            text=llm_result.text[:500],
            visual_explanation=visual_explanation,
            time=[llm_result.start, llm_result.end],
            importance=llm_result.importance,
        )


class SemanticEnhancer:
    """
    语义增强器

    对融合结果进行语义增强：
    - 信息补全
    - 结构化输出
    - 摘要生成
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    async def enhance(
        self,
        highlight: Highlight,
        vl_result: Optional[VLResult] = None,
    ) -> Highlight:
        """
        语义增强

        Args:
            highlight: 高亮片段
            vl_result: VL结果

        Returns:
            Highlight: 增强后的高亮片段
        """
        # 如果已经有视觉说明，跳过
        if highlight.visual_explanation:
            return highlight

        # 如果没有VL结果，跳过
        if not vl_result:
            return highlight

        # 生成视觉补充说明
        prompt = f"""请根据以下视觉分析结果，为文本描述添加视觉补充说明。

文本：{highlight.text}

视觉发现：
- 动作：{', '.join(vl_result.actions) if vl_result.actions else '无'}
- 元素：{', '.join(vl_result.objects) if vl_result.objects else '无'}
- 场景：{vl_result.vision_summary}

请用一句话补充视觉信息（不超过50字）："""

        try:
            enhancement = await self.llm.complete(
                prompt=prompt,
                temperature=0.3,
                max_tokens=100,
            )
            highlight.visual_explanation = enhancement.strip()
        except Exception as e:
            log.warning(f"Enhancement failed: {e}")

        return highlight

    async def generate_summary(
        self,
        highlights: List[Highlight],
    ) -> str:
        """
        生成视频摘要

        Args:
            highlights: 高亮片段列表

        Returns:
            str: 摘要
        """
        if not highlights:
            return "无内容"

        # 取Top 5高亮片段
        top_highlights = highlights[:5]
        texts = [h.text for h in top_highlights]

        prompt = f"""请根据以下关键片段，生成视频内容摘要（100字以内）：

{chr(10).join([f'{i+1}. {t[:100]}' for i, t in enumerate(texts)])}

摘要："""

        try:
            summary = await self.llm.complete(
                prompt=prompt,
                temperature=0.5,
                max_tokens=150,
            )
            return summary.strip()
        except Exception as e:
            log.error(f"Summary generation failed: {e}")
            return "视频内容分析完成"


async def fuse_results(
    llm_results: List[LLMResult],
    vl_results: Dict[str, VLResult],
    llm_client: Optional[LLMClient] = None,
) -> List[Highlight]:
    """
    便捷函数：融合LLM和VL结果
    """
    fusioner = InfoFusioner(llm_client)
    return await fusioner.merge(llm_results, vl_results)