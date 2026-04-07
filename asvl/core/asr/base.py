"""ASR抽象基类"""
from abc import ABC, abstractmethod
from typing import List, Optional
from asvl.models.schemas import ASRSegment, ASRResult


class ASRBase(ABC):
    """ASR模块抽象基类"""

    @abstractmethod
    async def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
    ) -> ASRResult:
        """
        转录音频文件

        Args:
            audio_path: 音频文件路径
            language: 语言代码 (如 'zh', 'en')

        Returns:
            ASRResult: 转录结果，包含分段和置信度
        """
        pass

    @abstractmethod
    async def extract_audio(
        self,
        video_path: str,
        output_path: str,
    ) -> str:
        """
        从视频中提取音频

        Args:
            video_path: 视频文件路径
            output_path: 输出音频路径

        Returns:
            str: 输出音频文件路径
        """
        pass