"""视频指纹计算"""
import asyncio
import os
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from configs.logging import log


@dataclass
class FrameInfo:
    """帧信息"""
    path: str
    timestamp: float
    hash_value: Optional[str] = None


class VideoFingerprint:
    """
    视频指纹计算

    使用 perceptual hash 从采样帧计算视频指纹
    """

    def __init__(
        self,
        sample_count: int = 5,
        hash_size: int = 16,
    ):
        """
        初始化视频指纹计算器

        Args:
            sample_count: 采样帧数
            hash_size: perceptual hash 大小
        """
        self.sample_count = sample_count
        self.hash_size = hash_size
        self.temp_dir = Path("temp/frames")
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def compute(self, video_url: str) -> str:
        """
        计算视频指纹

        Args:
            video_url: 视频 URL 或本地路径

        Returns:
            str: 视频指纹（32字符十六进制）
        """
        log.debug(f"Computing fingerprint for: {video_url}")

        # 1. 提取采样帧
        frames = await self._extract_sample_frames(video_url)

        if not frames:
            log.warning("No frames extracted, returning empty fingerprint")
            return ""

        # 2. 计算每帧的 perceptual hash
        hashes = []
        for frame in frames:
            try:
                h = self._compute_frame_hash(frame.path)
                frame.hash_value = h
                hashes.append(h)
            except Exception as e:
                log.warning(f"Failed to compute hash for frame {frame.path}: {e}")

        # 3. 清理临时帧文件
        for frame in frames:
            if os.path.exists(frame.path):
                os.remove(frame.path)

        if not hashes:
            return ""

        # 4. 合成视频指纹
        combined_hash = self._combine_hashes(hashes)

        log.debug(f"Video fingerprint: {combined_hash}")
        return combined_hash

    async def _extract_sample_frames(self, video_url: str) -> List[FrameInfo]:
        """
        提取采样帧

        Args:
            video_url: 视频 URL

        Returns:
            List[FrameInfo]: 帧信息列表
        """
        # 先获取视频时长
        duration = await self._get_video_duration(video_url)

        if duration <= 0:
            return []

        # 计算采样时间点
        if duration < self.sample_count:
            # 短视频：尽可能均匀采样
            timestamps = [duration * i / (self.sample_count + 1) for i in range(1, self.sample_count + 1)]
        else:
            # 正常视频：均匀采样
            timestamps = [duration * i / self.sample_count for i in range(self.sample_count)]

        frames = []
        for idx, ts in enumerate(timestamps):
            output_path = str(self.temp_dir / f"frame_{idx:03d}.jpg")

            try:
                await self._extract_frame(video_url, ts, output_path)
                frames.append(FrameInfo(path=output_path, timestamp=ts))
            except Exception as e:
                log.warning(f"Failed to extract frame at {ts}s: {e}")

        return frames

    async def _extract_frame(self, video_url: str, timestamp: float, output_path: str) -> None:
        """提取单帧"""
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(timestamp),
            "-i", video_url,
            "-frames:v", "1",
            "-q:v", "2",  # 高质量 JPEG
            output_path,
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg frame extraction failed: {stderr.decode()}")

    async def _get_video_duration(self, video_url: str) -> float:
        """获取视频时长"""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_url,
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            return 0.0

        return float(stdout.decode().strip())

    def _compute_frame_hash(self, frame_path: str) -> str:
        """
        计算单帧的 perceptual hash

        Args:
            frame_path: 帧图片路径

        Returns:
            str: perceptual hash 值
        """
        try:
            from PIL import Image
            import imagehash

            img = Image.open(frame_path)
            h = imagehash.phash(img, hash_size=self.hash_size)
            return str(h)
        except ImportError:
            # 如果没有安装 imagehash，使用简单的像素均值作为替代
            log.warning("imagehash not installed, using simple hash")
            return self._simple_hash(frame_path)

    def _simple_hash(self, frame_path: str) -> str:
        """简单的哈希方法（无依赖）"""
        import hashlib
        from PIL import Image

        img = Image.open(frame_path)
        # 缩放到 8x8
        img = img.resize((8, 8), Image.Resampling.LANCZOS)
        # 转灰度
        img = img.convert('L')
        # 计算均值
        pixels = list(img.getdata())
        avg = sum(pixels) / len(pixels)
        # 生成哈希
        bits = ''.join('1' if p > avg else '0' for p in pixels)
        return hex(int(bits, 2))[2:].zfill(16)

    def _combine_hashes(self, hashes: List[str]) -> str:
        """
        合成多帧指纹

        Args:
            hashes: 各帧哈希列表

        Returns:
            str: 合成的视频指纹
        """
        # 简单拼接每个哈希的前 8 个字符
        combined = "".join(h[:8] for h in hashes)
        # 取前 32 个字符
        return combined[:32].ljust(32, '0')

    @staticmethod
    def hamming_distance(hash1: str, hash2: str) -> int:
        """
        计算两个哈希的汉明距离

        Args:
            hash1: 第一个哈希
            hash2: 第二个哈希

        Returns:
            int: 汉明距离
        """
        if len(hash1) != len(hash2):
            return max(len(hash1), len(hash2))

        # 转换为二进制比较
        try:
            val1 = int(hash1, 16)
            val2 = int(hash2, 16)
            return bin(val1 ^ val2).count('1')
        except ValueError:
            # 如果不是有效的十六进制，逐字符比较
            return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))