"""信息融合器"""
from typing import List, Dict, Optional
from asvl.core.llm.client import LLMClient
from asvl.models.schemas import LLMResult, VLResult, Highlight
from asvl.models.enums import SegmentType
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
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()
        log.info("InfoFusioner initialized")

    async def merge(
        self,
        llm_results: List[LLMResult],
        vl_results: Dict[str, VLResult],
        min_importance: float = 0.5,
    ) -> List[Highlight]:
        """
        信息融合

        Args:
            llm_results: LLM分析结果列表
            vl_results: VL分析结果字典
            min_importance: 最小重要性阈值

        Returns:
            List[Highlight]: 高亮片段列表
        """
        highlights = []

        for llm_result in llm_results:
            # 过滤低重要性分段
            if llm_result.importance < min_importance:
                continue

            vl_result = vl_results.get(llm_result.id)

            try:
                highlight = await self._fuse_single(llm_result, vl_result)
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
    ) -> Highlight:
        """融合单个分段"""
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
            )
        else:
            # 无VL结果，直接使用LLM结果
            return self._simple_fuse(llm_result, None)

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