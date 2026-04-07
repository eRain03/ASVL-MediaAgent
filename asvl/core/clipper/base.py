"""视频裁剪抽象基类"""
from abc import ABC, abstractmethod
from typing import List, Optional
from asvl.models.schemas import ClipResult


class ClipperBase(ABC):
    """视频裁剪模块抽象基类"""

    @abstractmethod
    async def clip(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        output_path: str,
        padding: Optional[float] = None,
    ) -> ClipResult:
        """
        裁剪视频片段

        Args:
            video_path: 源视频路径
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            output_path: 输出路径
            padding: 时间padding（前后扩展）

        Returns:
            ClipResult: 裁剪结果
        """
        pass

    @abstractmethod
    async def merge_clips(
        self,
        clips: List[str],
        output_path: str,
    ) -> str:
        """
        合并多个视频片段

        Args:
            clips: 片段路径列表
            output_path: 输出路径

        Returns:
            str: 合合后的视频路径
        """
        pass