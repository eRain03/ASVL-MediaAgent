"""用户看点分析器"""
from typing import List, Optional
import json

from asvl.core.llm.client import LLMClient
from asvl.models.schemas import (
    LLMResult,
    VLResult,
    AlignmentIssue,
    UserAttraction,
)
from asvl.models.enums import SegmentType, AlignmentStatus
from configs.prompts.attraction_prompt import ATTRACTION_PROMPT
from configs.settings import get_settings
from configs.logging import log

settings = get_settings()


class AttractionAnalyzer:
    """
    用户看点分析器

    根据对齐结果分析用户看点：
    - 一致性内容：看点在于内容本身的信息价值
    - 冲突内容：看点在于矛盾或悬念
    - 视觉丰富内容：看点在于画面表现
    - 纯BGM内容：看点在于氛围
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()
        self.enabled = settings.ATTRACTION_ANALYSIS_ENABLED

    async def analyze(
        self,
        llm_result: LLMResult,
        vl_result: Optional[VLResult],
        alignment_issue: Optional[AlignmentIssue],
        audio_events: Optional[List[str]] = None,
    ) -> Optional[UserAttraction]:
        """
        分析用户看点

        Args:
            llm_result: LLM分析结果
            vl_result: VL视觉结果
            alignment_issue: 对齐结果
            audio_events: 音频事件类型

        Returns:
            UserAttraction: 看点分析结果
        """
        if not self.enabled:
            return None

        # 构建分析上下文
        context = self._build_context(
            llm_result, vl_result, alignment_issue, audio_events
        )

        # 使用LLM分析看点
        prompt = ATTRACTION_PROMPT.format(**context)

        try:
            response = await self.llm.complete(
                prompt=prompt,
                temperature=0.3,
                max_tokens=500,
            )

            # 解析JSON响应
            result = self._parse_response(response)

            if result:
                return UserAttraction(
                    attraction_type=result.get("attraction_type", "信息价值"),
                    description=result.get("description", ""),
                    confidence=result.get("confidence", 0.8),
                    evidence=result.get("evidence", []),
                )

        except Exception as e:
            log.warning(f"Attraction analysis failed: {e}")

        # Fallback分析
        return self._fallback_analyze(llm_result, vl_result, alignment_issue, audio_events)

    def _build_context(
        self,
        llm_result: LLMResult,
        vl_result: Optional[VLResult],
        alignment_issue: Optional[AlignmentIssue],
        audio_events: Optional[List[str]],
    ) -> dict:
        """构建分析上下文"""
        context = {
            "text": llm_result.text[:300] if llm_result.text else "无",
            "segment_type": llm_result.type.value if llm_result.type else "未知",
            "importance": f"{llm_result.importance:.2f}" if llm_result.importance else "0.50",
            "vision_summary": vl_result.vision_summary if vl_result and vl_result.vision_summary else "无视觉分析",
            "actions": ", ".join(vl_result.actions) if vl_result and vl_result.actions else "无",
            "alignment_status": alignment_issue.status.value if alignment_issue else "unknown",
            "alignment_reason": alignment_issue.reason if alignment_issue else "",
            "audio_events": ", ".join(audio_events) if audio_events else "无",
        }
        return context

    def _parse_response(self, response: str) -> Optional[dict]:
        """解析LLM响应"""
        try:
            # 尝试提取JSON
            text = response.strip()

            # 查找JSON块
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                text = text[start:end].strip()
            elif "```" in text:
                start = text.find("```") + 3
                end = text.find("```", start)
                text = text[start:end].strip()

            # 查找大括号
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                text = text[start:end]

            return json.loads(text)

        except (json.JSONDecodeError, ValueError) as e:
            log.debug(f"Failed to parse attraction response: {e}")
            return None

    def _fallback_analyze(
        self,
        llm_result: LLMResult,
        vl_result: Optional[VLResult],
        alignment_issue: Optional[AlignmentIssue],
        audio_events: Optional[List[str]],
    ) -> UserAttraction:
        """fallback分析（不使用LLM）"""
        # 基于对齐状态和片段类型推断看点
        attraction_type = self._infer_attraction_type(
            llm_result.type,
            llm_result.importance,
            alignment_issue,
            vl_result,
            audio_events,
        )

        # 构建描述
        description = self._build_description(
            attraction_type,
            llm_result,
            vl_result,
            alignment_issue,
            audio_events,
        )

        # 构建证据
        evidence = self._build_evidence(
            llm_result,
            vl_result,
            alignment_issue,
            audio_events,
        )

        return UserAttraction(
            attraction_type=attraction_type,
            description=description,
            confidence=0.6,  # fallback置信度较低
            evidence=evidence,
        )

    def _infer_attraction_type(
        self,
        segment_type: SegmentType,
        importance: float,
        alignment_issue: Optional[AlignmentIssue],
        vl_result: Optional[VLResult],
        audio_events: Optional[List[str]],
    ) -> str:
        """推断看点类型"""
        # 冲突内容 -> 悬念冲突
        if alignment_issue and alignment_issue.status == AlignmentStatus.CONFLICT:
            return "悬念冲突"

        # 有视觉分析且内容丰富 -> 视觉冲击
        if vl_result and vl_result.vision_summary:
            if len(vl_result.actions) > 2 or len(vl_result.objects) > 3:
                return "视觉冲击"

        # BGM/音乐 -> 氛围营造
        if audio_events:
            if "BGM" in audio_events or "Music" in audio_events:
                if "Speech" not in audio_events:
                    return "氛围营造"

        # 情绪表达 -> 情感共鸣
        if segment_type == SegmentType.EMOTIONAL_EXPRESSION:
            return "情感共鸣"

        # 操作演示
        if segment_type == SegmentType.OPERATION_DEMO or segment_type == SegmentType.UI_OPERATION:
            return "操作演示"

        # 高重要性核心观点 -> 信息价值
        if segment_type == SegmentType.CORE_VIEWPOINT and importance > 0.7:
            return "信息价值"

        # 默认
        return "信息价值"

    def _build_description(
        self,
        attraction_type: str,
        llm_result: LLMResult,
        vl_result: Optional[VLResult],
        alignment_issue: Optional[AlignmentIssue],
        audio_events: Optional[List[str]],
    ) -> str:
        """构建看点描述"""
        parts = []

        if attraction_type == "悬念冲突":
            parts.append("该片段存在文本与视觉不一致的情况，可能引发用户好奇心。")

        elif attraction_type == "视觉冲击":
            if vl_result:
                parts.append(f"视觉内容丰富：{vl_result.vision_summary[:100]}")

        elif attraction_type == "氛围营造":
            parts.append("该片段具有背景音乐或音效，营造了特定氛围。")

        elif attraction_type == "情感共鸣":
            parts.append(f"该片段表达了情感内容，可能引发用户共鸣。")

        elif attraction_type == "操作演示":
            parts.append("该片段包含具体操作步骤，具有实用价值。")

        else:
            parts.append(f"该片段为{llm_result.type.value}，重要性评分{llm_result.importance:.2f}。")

        return "".join(parts)

    def _build_evidence(
        self,
        llm_result: LLMResult,
        vl_result: Optional[VLResult],
        alignment_issue: Optional[AlignmentIssue],
        audio_events: Optional[List[str]],
    ) -> List[str]:
        """构建证据列表"""
        evidence = []

        if llm_result.importance > 0.7:
            evidence.append(f"重要性评分高({llm_result.importance:.2f})")

        if alignment_issue and alignment_issue.status == AlignmentStatus.CONFLICT:
            evidence.append("文本与视觉存在冲突")

        if vl_result and vl_result.actions:
            evidence.append(f"检测到动作：{', '.join(vl_result.actions[:3])}")

        if audio_events:
            evidence.append(f"音频类型：{', '.join(audio_events)}")

        return evidence