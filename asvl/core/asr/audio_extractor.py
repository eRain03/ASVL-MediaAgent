"""FFmpeg音频提取器"""
import asyncio
import os
from pathlib import Path
from typing import Optional
from configs.settings import get_settings
from configs.logging import log

settings = get_settings()


class AudioExtractor:
    """
    FFmpeg音频提取器

    从视频中提取音频，支持：
    - 多种视频格式
    - 长视频分段处理
    - 自动采样率转换
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        audio_format: str = "wav",
    ):
        """
        初始化音频提取器

        Args:
            sample_rate: 采样率（默认16kHz，适合ASR）
            channels: 声道数（默认单声道）
            audio_format: 输出格式（默认WAV）
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.audio_format = audio_format
        self.temp_dir = Path("temp/audio")
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        log.info(
            f"AudioExtractor initialized: sample_rate={sample_rate}, "
            f"channels={channels}, format={audio_format}"
        )

    async def extract(
        self,
        video_path: str,
        output_path: Optional[str] = None,
        start_time: Optional[float] = None,
        duration: Optional[float] = None,
    ) -> str:
        """
        从视频提取音频

        Args:
            video_path: 视频文件路径
            output_path: 输出音频路径（可选，自动生成）
            start_time: 开始时间（秒，用于分段提取）
            duration: 持续时间（秒，用于分段提取）

        Returns:
            str: 输出音频文件路径
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # 生成输出路径
        if not output_path:
            video_name = Path(video_path).stem
            segment_suffix = f"_{int(start_time)}s" if start_time else ""
            output_path = str(
                self.temp_dir / f"{video_name}{segment_suffix}.{self.audio_format}"
            )

        # 构建FFmpeg命令
        cmd = [
            "ffmpeg",
            "-y",  # 覆盖输出
            "-i", video_path,
            "-vn",  # 不包含视频
            "-acodec", "pcm_s16le",  # 16-bit PCM编码
            "-ar", str(self.sample_rate),  # 采样率
            "-ac", str(self.channels),  # 声道数
        ]

        # 分段提取参数
        if start_time is not None:
            cmd.extend(["-ss", str(start_time)])
        if duration is not None:
            cmd.extend(["-t", str(duration)])

        cmd.append(output_path)

        # 执行命令
        log.info(f"Extracting audio: {video_path} -> {output_path}")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            log.error(f"FFmpeg audio extraction failed: {error_msg}")
            raise RuntimeError(f"FFmpeg error: {error_msg}")

        log.info(f"Audio extracted successfully: {output_path}")
        return output_path

    async def extract_segments(
        self,
        video_path: str,
        segment_duration: float = 600.0,  # 10分钟
        overlap: float = 2.0,  # 2秒重叠
    ) -> list:
        """
        分段提取长视频音频

        Args:
            video_path: 视频文件路径
            segment_duration: 每段时长（秒）
            overlap: 段间重叠（秒）

        Returns:
            list: 音频分段路径列表 [{path, start, end, duration}, ...]
        """
        # 获取视频总时长
        total_duration = await self._get_duration(video_path)
        log.info(f"Video duration: {total_duration}s, segmenting into {segment_duration}s chunks")

        segments = []
        start = 0.0
        segment_idx = 0

        while start < total_duration:
            # 计算当前段时长
            current_duration = min(segment_duration, total_duration - start)

            # 提取音频段
            video_name = Path(video_path).stem
            output_path = str(
                self.temp_dir / f"{video_name}_seg{segment_idx:03d}.{self.audio_format}"
            )

            await self.extract(
                video_path=video_path,
                output_path=output_path,
                start_time=start,
                duration=current_duration,
            )

            segments.append({
                "path": output_path,
                "start": start,
                "end": start + current_duration,
                "duration": current_duration,
                "index": segment_idx,
            })

            # 移动到下一段（考虑重叠）
            start += segment_duration - overlap
            segment_idx += 1

        log.info(f"Extracted {len(segments)} audio segments")
        return segments

    async def _get_duration(self, video_path: str) -> float:
        """获取视频时长"""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"FFprobe error: {stderr.decode()}")

        return float(stdout.decode().strip())

    def cleanup(self, audio_path: str) -> None:
        """清理临时音频文件"""
        if os.path.exists(audio_path):
            os.remove(audio_path)
            log.debug(f"Cleaned up temp audio: {audio_path}")