"""VL视觉理解模块"""
import asyncio
from typing import List, Optional, Dict, Any
import os

from asvl.core.vl.base import VLBase
from asvl.core.vl.frame_extractor import FrameExtractor
from asvl.core.llm.client import LLMClient
from asvl.models.schemas import VLResult
from configs.prompts.vision_detect_prompt import VL_ANALYSIS_PROMPT
from configs.settings import get_settings
from configs.logging import log
import json

settings = get_settings()


class QwenVLProcessor(VLBase):
    """
    Qwen-VL视觉理解处理器

    使用qwen3-vl-plus模型进行视觉理解：
    - 动作识别
    - UI元素识别
    - 场景理解
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        max_frames: int = 10,
    ):
        self.llm = llm_client or LLMClient()
        self.max_frames = max_frames
        self.frame_extractor = FrameExtractor(max_frames=max_frames)

        log.info(f"QwenVLProcessor initialized: max_frames={max_frames}")

    async def extract_frames(
        self,
        video_path: str,
        output_dir: str = None,
        fps: Optional[float] = None,
        max_frames: Optional[int] = None,
    ) -> List[str]:
        """提取视频帧"""
        if output_dir:
            self.frame_extractor.output_dir = output_dir

        return await self.frame_extractor.extract(
            video_path=video_path,
            fps=fps,
            max_frames=max_frames or self.max_frames,
            method="uniform",  # 均匀采样
        )

    async def analyze_frames(
        self,
        frames: List[str],
        context: Optional[str] = None,
    ) -> VLResult:
        """
        分析视频帧

        Args:
            frames: 帧图片路径列表
            context: 上下文信息

        Returns:
            VLResult: 视觉分析结果
        """
        if not frames:
            raise ValueError("No frames to analyze")

        log.info(f"Analyzing {len(frames)} frames")

        # 转换帧为Base64
        frame_b64_list = [self.frame_extractor.to_base64(f) for f in frames[:self.max_frames]]

        # 构建prompt
        prompt = VL_ANALYSIS_PROMPT.format(context=context or "无上下文")

        # 调用VL模型
        try:
            response = await self.llm.complete_with_images(
                prompt=prompt,
                images=frame_b64_list,
                temperature=0.3,
            )

            # 解析JSON响应
            result = self._parse_response(response)

            log.info(f"VL analysis complete: {len(result.actions)} actions, {len(result.objects)} objects")
            return result

        except Exception as e:
            log.error(f"VL analysis failed: {e}")
            # 返回默认结果
            return VLResult(
                clip_id="unknown",
                vision_summary="视觉分析失败",
                actions=[],
                objects=[],
                confidence=0.0,
            )

    async def recognize_actions(
        self,
        frames: List[str],
    ) -> List[str]:
        """
        识别动作

        Args:
            frames: 帧图片路径列表

        Returns:
            List[str]: 动作列表
        """
        prompt = """请分析这些视频帧，识别其中的动作行为。

返回JSON格式：
{"actions": ["动作1", "动作2", ...]}

动作类型示例：点击、滑动、输入、拖动、缩放、滚动等。"""

        frame_b64_list = [self.frame_extractor.to_base64(f) for f in frames[:self.max_frames]]

        try:
            response = await self.llm.complete_with_images(
                prompt=prompt,
                images=frame_b64_list,
                temperature=0.2,
            )

            result = json.loads(response)
            return result.get("actions", [])

        except Exception as e:
            log.error(f"Action recognition failed: {e}")
            return []

    async def analyze_clip(
        self,
        clip_path: str,
        segment_text: Optional[str] = None,
    ) -> VLResult:
        """
        分析视频片段

        Args:
            clip_path: 片段路径
            segment_text: 相关文本

        Returns:
            VLResult: 分析结果
        """
        # 提取帧
        frames = await self.extract_frames(clip_path)

        # 分析帧
        result = await self.analyze_frames(frames, context=segment_text)

        # 设置clip_id
        result.clip_id = os.path.basename(clip_path).split(".")[0]

        # 清理临时帧
        self.frame_extractor.cleanup(frames)

        return result

    def _parse_response(self, response: str) -> VLResult:
        """解析VL响应"""
        try:
            # 尝试解析JSON
            data = json.loads(response)

            return VLResult(
                clip_id="",
                vision_summary=data.get("vision_summary", ""),
                actions=data.get("actions", []),
                objects=data.get("objects", []),
                scene_description=data.get("scene_description"),
                confidence=data.get("confidence", 0.8),
            )
        except json.JSONDecodeError:
            # 如果不是JSON，直接作为summary
            return VLResult(
                clip_id="",
                vision_summary=response,
                actions=[],
                objects=[],
                confidence=0.5,
            )


async def analyze_video_clip(
    clip_path: str,
    context: Optional[str] = None,
    llm_client: Optional[LLMClient] = None,
) -> VLResult:
    """
    便捷函数：分析视频片段
    """
    processor = QwenVLProcessor(llm_client)
    return await processor.analyze_clip(clip_path, context)