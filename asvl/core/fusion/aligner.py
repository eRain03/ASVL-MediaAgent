"""双模态对齐器"""
from typing import Optional, List, Dict
from asvl.core.llm.client import LLMClient
from asvl.models.schemas import LLMResult, VLResult, AlignmentIssue
from asvl.models.enums import AlignmentStatus
from configs.prompts.fusion_prompt import ALIGNMENT_PROMPT
from configs.logging import log
import json


class CrossModalAligner:
    """
    双模态对齐器

    验证文本描述与视觉发现是否一致：
    - 一致性校验
    - 冲突检测
    - 置信度调整

    这是系统可信度的关键组件！
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()
        log.info("CrossModalAligner initialized")

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
        # 如果没有VL结果，标记为不充分
        if not vl_result:
            return AlignmentIssue(
                segment_id=llm_result.id,
                status=AlignmentStatus.INSUFFICIENT,
                text_claim=llm_result.text[:200],
                vision_finding="无视觉分析",
                reason="该分段未进行视觉分析",
            )

        # 使用LLM判断一致性
        try:
            result = await self._check_alignment(llm_result, vl_result)
            return result
        except Exception as e:
            log.error(f"Alignment check failed for {llm_result.id}: {e}")
            return AlignmentIssue(
                segment_id=llm_result.id,
                status=AlignmentStatus.INSUFFICIENT,
                text_claim=llm_result.text[:200],
                vision_finding=vl_result.vision_summary[:200],
                reason=f"对齐分析失败: {str(e)}",
            )

    async def _check_alignment(
        self,
        llm_result: LLMResult,
        vl_result: VLResult,
    ) -> AlignmentIssue:
        """使用LLM检查一致性"""
        prompt = ALIGNMENT_PROMPT.format(
            text=llm_result.text[:500],
            vision_summary=vl_result.vision_summary,
            actions=vl_result.actions,
            objects=vl_result.objects,
        )

        response = await self.llm.complete_json(
            prompt=prompt,
            temperature=0.2,
        )

        status_str = response.get("status", "insufficient")
        status = AlignmentStatus(status_str) if status_str in ["consistent", "conflict", "insufficient"] else AlignmentStatus.INSUFFICIENT

        return AlignmentIssue(
            segment_id=llm_result.id,
            status=status,
            text_claim=response.get("text_claim", llm_result.text[:100]),
            vision_finding=response.get("vision_finding", vl_result.vision_summary[:100]),
            reason=response.get("reason"),
        )

    async def batch_align(
        self,
        llm_results: List[LLMResult],
        vl_results: Dict[str, VLResult],
    ) -> List[AlignmentIssue]:
        """
        批量对齐

        Args:
            llm_results: LLM结果列表
            vl_results: VL结果字典（key为segment_id）

        Returns:
            List[AlignmentIssue]: 对齐结果列表
        """
        issues = []

        for llm_result in llm_results:
            # 只对need_vision的分段进行对齐
            if not llm_result.need_vision:
                continue

            vl_result = vl_results.get(llm_result.id)
            issue = await self.align(llm_result, vl_result)
            issues.append(issue)

        # 统计
        consistent = sum(1 for i in issues if i.status == AlignmentStatus.CONSISTENT)
        conflict = sum(1 for i in issues if i.status == AlignmentStatus.CONFLICT)
        insufficient = sum(1 for i in issues if i.status == AlignmentStatus.INSUFFICIENT)

        log.info(
            f"Alignment complete: {consistent} consistent, "
            f"{conflict} conflicts, {insufficient} insufficient"
        )

        return issues

    def adjust_confidence(
        self,
        llm_result: LLMResult,
        alignment_issue: AlignmentIssue,
    ) -> float:
        """
        根据对齐结果调整置信度

        Args:
            llm_result: LLM结果
            alignment_issue: 对齐结果

        Returns:
            float: 调整后的置信度
        """
        base_confidence = llm_result.confidence

        if alignment_issue.status == AlignmentStatus.CONSISTENT:
            # 一致：提升置信度
            return min(1.0, base_confidence + 0.1)
        elif alignment_issue.status == AlignmentStatus.CONFLICT:
            # 冲突：降低置信度
            return max(0.0, base_confidence - 0.2)
        else:
            # 不充分：保持
            return base_confidence


async def align_text_vision(
    llm_result: LLMResult,
    vl_result: Optional[VLResult],
    llm_client: Optional[LLMClient] = None,
) -> AlignmentIssue:
    """
    便捷函数：文本-视觉对齐
    """
    aligner = CrossModalAligner(llm_client)
    return await aligner.align(llm_result, vl_result)