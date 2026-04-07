"""视频帧提取器"""
import asyncio
import os
from pathlib import Path
from typing import List, Optional
import base64

from configs.settings import get_settings
from configs.logging import log

settings = get_settings()


class FrameExtractor:
    """
    视频帧提取器

    支持：
    - 关键帧提取
    - 均匀采样
    - 自定义帧率
    - Base64编码输出
    """

    def __init__(
        self,
        output_dir: str = "temp/frames",
        default_fps: Optional[float] = None,
        max_frames: int = 20,
        image_format: str = "jpg",
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.default_fps = default_fps
        self.max_frames = max_frames
        self.image_format = image_format

        log.info(f"FrameExtractor initialized: max_frames={max_frames}")

    async def extract(
        self,
        video_path: str,
        fps: Optional[float] = None,
        max_frames: Optional[int] = None,
        method: str = "keyframe",  # keyframe, uniform, custom
    ) -> List[str]:
        """
        提取视频帧

        Args:
            video_path: 视频路径
            fps: 帧率（仅custom模式）
            max_frames: 最大帧数
            method: 提取方法

        Returns:
            List[str]: 帧图片路径列表
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")

        max_frames = max_frames or self.max_frames
        fps = fps or self.default_fps

        # 清理输出目录
        output_prefix = Path(video_path).stem

        if method == "keyframe":
            frames = await self._extract_keyframes(video_path, output_prefix, max_frames)
        elif method == "uniform":
            frames = await self._extract_uniform(video_path, output_prefix, max_frames)
        else:
            frames = await self._extract_custom_fps(video_path, output_prefix, fps, max_frames)

        log.info(f"Extracted {len(frames)} frames from {video_path}")
        return frames

    async def _extract_keyframes(
        self,
        video_path: str,
        output_prefix: str,
        max_frames: int,
    ) -> List[str]:
        """提取关键帧（I帧）"""
        output_pattern = str(self.output_dir / f"{output_prefix}_%04d.{self.image_format}")

        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-vf", "select='eq(pict_type,I)'",
            "-vsync", "vfr",
            "-q:v", "2",
            "-y",
            output_pattern,
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        await proc.communicate()

        # 获取生成的帧
        frames = sorted([
            str(f) for f in self.output_dir.glob(f"{output_prefix}_*.{self.image_format}")
        ])

        # 限制数量
        if len(frames) > max_frames:
            # 均匀采样
            step = len(frames) / max_frames
            frames = [frames[int(i * step)] for i in range(max_frames)]

        return frames

    async def _extract_uniform(
        self,
        video_path: str,
        output_prefix: str,
        max_frames: int,
    ) -> List[str]:
        """均匀采样"""
        # 先获取视频时长
        duration = await self._get_duration(video_path)

        # 计算采样间隔
        interval = duration / (max_frames + 1)

        frames = []
        for i in range(max_frames):
            timestamp = interval * (i + 1)
            output_path = str(self.output_dir / f"{output_prefix}_{i:04d}.{self.image_format}")

            cmd = [
                "ffmpeg",
                "-ss", str(timestamp),
                "-i", video_path,
                "-frames:v", "1",
                "-q:v", "2",
                "-y",
                output_path,
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            await proc.communicate()

            if os.path.exists(output_path):
                frames.append(output_path)

        return frames

    async def _extract_custom_fps(
        self,
        video_path: str,
        output_prefix: str,
        fps: float,
        max_frames: int,
    ) -> List[str]:
        """按指定帧率提取"""
        output_pattern = str(self.output_dir / f"{output_prefix}_%04d.{self.image_format}")

        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-vf", f"fps={fps}",
            "-frames:v", str(max_frames),
            "-q:v", "2",
            "-y",
            output_pattern,
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        await proc.communicate()

        frames = sorted([
            str(f) for f in self.output_dir.glob(f"{output_prefix}_*.{self.image_format}")
        ])

        return frames

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

        stdout, _ = await proc.communicate()
        return float(stdout.decode().strip())

    def to_base64(self, frame_path: str) -> str:
        """将帧图片转换为Base64"""
        with open(frame_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def cleanup(self, frames: List[str] = None) -> None:
        """清理临时帧文件"""
        if frames:
            for frame in frames:
                if os.path.exists(frame):
                    os.remove(frame)
        else:
            # 清理整个目录
            for f in self.output_dir.glob(f"*.{self.image_format}"):
                f.unlink()

        log.debug("Cleaned up frame files")