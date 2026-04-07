"""视觉需求判定器"""
from typing import List, Optional, Tuple
from asvl.core.llm.client import LLMClient
from asvl.models.schemas import LLMResult
from configs.prompts.vision_detect_prompt import VISION_DETECT_PROMPT
from configs.settings import get_settings
from configs.logging import log
import json

settings = get_settings()


class VisionDetector:
    """
    视觉需求判定器

    判断哪些分段需要视觉分析才能完整理解。
    这是成本控制的关键组件！

    判断规则：
    1. UI操作描述（点击、滑动、输入等）
    2. 图表/数据可视化描述
    3. 实物展示或演示操作
    4. 界面布局描述
    5. 非语言信息（表情、动作、姿态）
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()
        self.top_k_percent = settings.VL_TOP_K_PERCENT  # Top 20%

        # 规则关键词（快速判断）
        self.vision_keywords = [
            # UI操作
            "点击", "滑动", "输入", "选择", "拖动", "按钮", "菜单", "界面",
            "页面", "窗口", "对话框", "选项卡", "工具栏",
            # 数据可视化
            "图表", "曲线", "柱状图", "饼图", "折线图", "数据", "趋势",
            # 展示
            "展示", "演示", "示例", "实物", "产品", "设备", "机器",
            # 动作
            "动作", "手势", "表情", "姿态", "移动",
            # 场景
            "场景", "环境", "背景", "位置", "布局", "结构",
        ]

        log.info(f"VisionDetector initialized, top_k_percent={self.top_k_percent}")

    async def detect(
        self,
        segments: List[LLMResult],
        use_llm: bool = True,
    ) -> List[LLMResult]:
        """
        检测需要视觉分析的分段

        Args:
            segments: 语义分段列表
            use_llm: 是否使用LLM判断（否则只用关键词）

        Returns:
            List[LLMResult]: 更新need_vision标记的分段列表
        """
        if not segments:
            return segments

        log.info(f"Detecting vision needs for {len(segments)} segments")

        for seg in segments:
            # 先用关键词快速判断
            keyword_match = self._keyword_check(seg.text)

            if keyword_match:
                seg.need_vision = True
                log.debug(f"Segment {seg.id} needs vision (keyword match)")
            elif use_llm:
                # 使用LLM精细判断
                try:
                    need_vision, reason = await self._llm_check(seg.text)
                    seg.need_vision = need_vision
                    log.debug(f"Segment {seg.id} vision check: {need_vision} - {reason}")
                except Exception as e:
                    log.warning(f"LLM vision check failed for {seg.id}: {e}")
                    seg.need_vision = False

        # 统计
        vision_count = sum(1 for s in segments if s.need_vision)
        log.info(f"Vision detection complete: {vision_count}/{len(segments)} segments need vision")

        return segments

    def _keyword_check(self, text: str) -> bool:
        """关键词快速检查"""
        text_lower = text.lower()
        for keyword in self.vision_keywords:
            if keyword in text_lower:
                return True
        return False

    async def _llm_check(self, text: str) -> Tuple[bool, str]:
        """使用LLM精细判断"""
        prompt = VISION_DETECT_PROMPT.format(text=text[:500])

        response = await self.llm.complete_json(
            prompt=prompt,
            temperature=0.1,  # 低温度保证稳定输出
        )

        need_vision = response.get("need_vision", False)
        reason = response.get("reason", "")

        return need_vision, reason

    async def get_vision_segments(
        self,
        segments: List[LLMResult],
        top_k: Optional[int] = None,
    ) -> List[LLMResult]:
        """
        获取需要视觉分析的分段（Top-K筛选）

        成本控制关键：只处理重要性最高的need_vision分段

        Args:
            segments: 分段列表
            top_k: 最大数量（默认使用配置中的比例）

        Returns:
            List[LLMResult]: 需要视觉分析的分段
        """
        # 过滤need_vision的分段
        vision_segments = [s for s in segments if s.need_vision]

        # 按重要性排序
        vision_segments.sort(key=lambda x: x.importance, reverse=True)

        # 限制数量
        if top_k is None:
            top_k = max(1, int(len(segments) * self.top_k_percent))

        result = vision_segments[:top_k]

        log.info(
            f"Selected {len(result)}/{len(vision_segments)} vision segments "
            f"(top {self.top_k_percent*100:.0f}%)"
        )

        return result

    async def batch_detect(
        self,
        segments: List[LLMResult],
        batch_size: int = 5,
    ) -> List[LLMResult]:
        """
        批量检测（优化API调用）

        将多个分段合并到一个请求中处理。
        """
        if not segments:
            return segments

        # 先用关键词筛选
        for seg in segments:
            seg.need_vision = self._keyword_check(seg.text)

        # 只对关键词未匹配的使用LLM
        unchecked = [s for s in segments if not s.need_vision]

        if not unchecked:
            return segments

        log.info(f"Batch LLM check for {len(unchecked)} segments")

        # 分批处理
        for i in range(0, len(unchecked), batch_size):
            batch = unchecked[i : i + batch_size]
            batch_text = "\n---\n".join([f"[{j}] {s.text[:200]}" for j, s in enumerate(batch)])

            try:
                prompt = f"""判断以下{len(batch)}个文本片段是否需要视觉分析。
每个片段格式为 [序号] 文本内容。

{batch_text}

请返回JSON格式：
{{"results": [{{"index": 0, "need_vision": true/false, "reason": "原因"}}]}}
"""
                response = await self.llm.complete_json(prompt=prompt, temperature=0.1)

                # 更新结果
                for result in response.get("results", []):
                    idx = result.get("index", 0)
                    if idx < len(batch):
                        batch[idx].need_vision = result.get("need_vision", False)

            except Exception as e:
                log.error(f"Batch detection failed: {e}")

        return segments


async def detect_vision_needs(
    segments: List[LLMResult],
    llm_client: Optional[LLMClient] = None,
) -> List[LLMResult]:
    """
    便捷函数：检测视觉需求
    """
    detector = VisionDetector(llm_client)
    return await detector.detect(segments)