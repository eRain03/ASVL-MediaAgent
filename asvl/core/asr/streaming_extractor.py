"""流式音频提取器"""
import asyncio
import os
from pathlib import Path
from typing import Optional

from configs.logging import log


class StreamingAudioExtractor:
    """
    流式音频提取器

    直接从 URL 提取音频，不需要下载完整视频

    使用方式：
    - FFmpeg 直接从 URL 读取
    - -ss 参数放在 -i 前面实现快速定位
    - 输出 16kHz 单声道 WAV
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        audio_format: str = "wav",
    ):
        """
        初始化流式音频提取器

        Args:
            sample_rate: 采样率（默认16kHz）
            channels: 声道数（默认单声道）
            audio_format: 输出格式（默认WAV）
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.audio_format = audio_format
        self.temp_dir = Path("temp/audio")
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        log.info(
            f"StreamingAudioExtractor initialized: sample_rate={sample_rate}, "
            f"channels={channels}, format={audio_format}"
        )

    async def extract_from_url(
        self,
        video_url: str,
        output_path: str,
        start_time: Optional[float] = None,
        duration: Optional[float] = None,
    ) -> str:
        """
        从 URL 直接提取音频

        Args:
            video_url: 视频 URL
            output_path: 输出音频路径
            start_time: 开始时间（秒）
            duration: 持续时间（秒）

        Returns:
            str: 输出音频文件路径
        """
        cmd = ["ffmpeg", "-y"]

        # -ss 放在 -i 前面实现快速定位（不解码整个视频）
        if start_time is not None and start_time > 0:
            cmd.extend(["-ss", str(start_time)])

        cmd.extend(["-i", video_url])

        if duration is not None:
            cmd.extend(["-t", str(duration)])

        # 输出 16kHz 单声道 WAV
        cmd.extend([
            "-vn",  # 不包含视频
            "-acodec", "pcm_s16le",  # 16-bit PCM
            "-ar", str(self.sample_rate),  # 采样率
            "-ac", str(self.channels),  # 声道数
            output_path,
        ])

        log.info(f"Extracting audio from URL: {video_url} -> {output_path}")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            log.error(f"FFmpeg streaming extraction failed: {error_msg}")
            raise RuntimeError(f"FFmpeg error: {error_msg}")

        # 检查输出文件
        if not os.path.exists(output_path):
            raise RuntimeError(f"Output file not created: {output_path}")

        file_size = os.path.getsize(output_path)
        log.info(f"Audio extracted: {output_path} ({file_size} bytes)")

        return output_path

    async def extract_segment_from_url(
        self,
        video_url: str,
        start_time: float,
        end_time: float,
        output_path: Optional[str] = None,
    ) -> str:
        """
        从 URL 提取指定时间段的音频

        Args:
            video_url: 视频 URL
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            output_path: 输出路径（可选）

        Returns:
            str: 输出音频文件路径
        """
        duration = end_time - start_time

        if output_path is None:
            output_path = str(
                self.temp_dir / f"segment_{int(start_time)}_{int(end_time)}.{self.audio_format}"
            )

        return await self.extract_from_url(
            video_url=video_url,
            output_path=output_path,
            start_time=start_time,
            duration=duration,
        )

    async def extract_segments_from_url(
        self,
        video_url: str,
        segments: list,  # [(start, end), ...]
        output_dir: Optional[str] = None,
    ) -> list:
        """
        从 URL 批量提取多个时间段

        Args:
            video_url: 视频 URL
            segments: 时间段列表 [(start, end), ...]
            output_dir: 输出目录

        Returns:
            list: 提取结果 [{path, start, end}, ...]
        """
        if output_dir is None:
            output_dir = str(self.temp_dir)

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        results = []
        for idx, (start, end) in enumerate(segments):
            output_path = str(
                Path(output_dir) / f"segment_{idx:03d}_{int(start)}_{int(end)}.{self.audio_format}"
            )

            await self.extract_segment_from_url(
                video_url=video_url,
                start_time=start,
                end_time=end,
                output_path=output_path,
            )

            results.append({
                "path": output_path,
                "start": start,
                "end": end,
            })

        return results

    def cleanup(self, audio_path: str) -> None:
        """清理临时音频文件"""
        if os.path.exists(audio_path):
            os.remove(audio_path)
            log.debug(f"Cleaned up temp audio: {audio_path}")