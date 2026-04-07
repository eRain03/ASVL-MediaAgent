"""VL视觉理解抽象基类"""
from abc import ABC, abstractmethod
from typing import List, Optional
from asvl.models.schemas import VLResult


class VLBase(ABC):
    """VL视觉理解模块抽象基类"""

    @abstractmethod
    async def extract_frames(
        self,
        video_path: str,
        output_dir: str,
        fps: Optional[float] = None,
        max_frames: Optional[int] = None,
    ) -> List[str]:
        """
        提取视频帧

        Args:
            video_path: 视频路径
            output_dir: 输出目录
            fps: 帧率（可选，默认提取关键帧）
            max_frames: 最大帧数

        Returns:
            List[str]: 帧图片路径列表
        """
        pass

    @abstractmethod
    async def analyze_frames(
        self,
        frames: List[str],
        context: Optional[str] = None,
    ) -> VLResult:
        """
        分析视频帧

        Args:
            frames: 帧图片路径列表
            context: 上下文信息（如ASR文本）

        Returns:
            VLResult: 视觉分析结果
        """
        pass

    @abstractmethod
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
        pass