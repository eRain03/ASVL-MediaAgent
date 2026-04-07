"""FFmpeg视频裁剪器"""
import asyncio
import os
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime

from asvl.core.clipper.base import ClipperBase
from asvl.models.schemas import ClipResult, LLMResult
from asvl.storage.local_storage import LocalStorage
from configs.settings import get_settings
from configs.logging import log

settings = get_settings()


class FFmpegClipper(ClipperBase):
    """
    FFmpeg视频裁剪器

    支持：
    - 精确时间裁剪
    - 关键帧对齐
    - 时间padding
    - 多格式输出
    """

    def __init__(
        self,
        padding: Optional[float] = None,
        min_duration: Optional[float] = None,
        max_duration: Optional[float] = None,
        output_format: str = "mp4",
    ):
        self.padding = padding or settings.CLIP_PADDING_SECONDS
        self.min_duration = min_duration or settings.MIN_CLIP_DURATION
        self.max_duration = max_duration or settings.MAX_CLIP_DURATION
        self.output_format = output_format
        self.storage = LocalStorage()

        self.clips_dir = Path("data/clips")
        self.clips_dir.mkdir(parents=True, exist_ok=True)

        log.info(
            f"FFmpegClipper initialized: padding={self.padding}s, "
            f"min={self.min_duration}s, max={self.max_duration}s"
        )

    async def clip(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        output_path: Optional[str] = None,
        padding: Optional[float] = None,
    ) -> ClipResult:
        """
        裁剪视频片段

        Args:
            video_path: 源视频路径
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            output_path: 输出路径（可选）
            padding: 时间padding（可选）

        Returns:
            ClipResult: 裁剪结果
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")

        # 应用padding
        padding = padding or self.padding
        actual_start = max(0, start_time - padding)
        actual_end = end_time + padding

        # 检查时长限制
        duration = actual_end - actual_start
        if duration < self.min_duration:
            log.warning(f"Clip too short ({duration}s), extending to {self.min_duration}s")
            actual_end = actual_start + self.min_duration
        elif duration > self.max_duration:
            log.warning(f"Clip too long ({duration}s), truncating to {self.max_duration}s")
            actual_end = actual_start + self.max_duration

        # 生成输出路径
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"clip_{timestamp}_{int(actual_start)}s.{self.output_format}"
            output_path = str(self.clips_dir / filename)

        # 构建FFmpeg命令
        cmd = [
            "ffmpeg",
            "-y",  # 覆盖
            "-ss", str(actual_start),  # 开始时间（放在-i前面加速）
            "-i", video_path,
            "-t", str(actual_end - actual_start),  # 持续时间
            "-c", "copy",  # 直接复制，不重新编码
            "-avoid_negative_ts", "make_zero",
            output_path,
        ]

        log.info(f"Clipping video: {actual_start:.1f}s - {actual_end:.1f}s -> {output_path}")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            # 如果copy失败，尝试重新编码
            log.warning(f"Copy mode failed, trying re-encode: {stderr.decode()}")
            return await self._clip_with_reencode(
                video_path, actual_start, actual_end, output_path
            )

        # 获取实际裁剪时长
        actual_duration = await self._get_duration(output_path)

        log.info(f"Clip created: {output_path} ({actual_duration:.1f}s)")

        return ClipResult(
            clip_id=f"clip_{int(actual_start)}_{int(actual_end)}",
            segment_id="",  # 由调用者设置
            clip_url=None,  # 本地路径，上传后更新
            start_time=actual_start,
            end_time=actual_end,
            duration=actual_duration,
            storage_path=output_path,
        )

    async def _clip_with_reencode(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        output_path: str,
    ) -> ClipResult:
        """重新编码方式裁剪（更精确但更慢）"""
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(start_time),
            "-i", video_path,
            "-t", str(end_time - start_time),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "fast",
            output_path,
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg re-encode failed: {stderr.decode()}")

        actual_duration = await self._get_duration(output_path)

        return ClipResult(
            clip_id=f"clip_{int(start_time)}_{int(end_time)}",
            segment_id="",
            clip_url=None,
            start_time=start_time,
            end_time=end_time,
            duration=actual_duration,
            storage_path=output_path,
        )

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
            str: 合并后的视频路径
        """
        if not clips:
            raise ValueError("No clips to merge")

        if len(clips) == 1:
            return clips[0]

        # 创建临时文件列表
        list_file = str(self.clips_dir / "merge_list.txt")
        with open(list_file, "w") as f:
            for clip in clips:
                f.write(f"file '{clip}'\n")

        # FFmpeg合并
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            output_path,
        ]

        log.info(f"Merging {len(clips)} clips -> {output_path}")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg merge failed: {stderr.decode()}")

        # 清理临时文件
        os.remove(list_file)

        log.info(f"Clips merged: {output_path}")
        return output_path

    async def batch_clip(
        self,
        video_path: str,
        segments: List[LLMResult],
        filter_vision_only: bool = True,
    ) -> List[ClipResult]:
        """
        批量裁剪片段

        Args:
            video_path: 源视频路径
            segments: 分段列表
            filter_vision_only: 只裁剪need_vision的分段

        Returns:
            List[ClipResult]: 裁剪结果列表
        """
        # 过滤需要视觉分析的分段
        if filter_vision_only:
            segments = [s for s in segments if s.need_vision]

        if not segments:
            log.info("No segments need clipping")
            return []

        log.info(f"Batch clipping {len(segments)} segments")

        results = []
        for seg in segments:
            try:
                result = await self.clip(
                    video_path=video_path,
                    start_time=seg.start,
                    end_time=seg.end,
                )
                result.segment_id = seg.id
                results.append(result)
            except Exception as e:
                log.error(f"Failed to clip segment {seg.id}: {e}")

        log.info(f"Batch clipping complete: {len(results)}/{len(segments)} clips created")
        return results

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


async def clip_segments(
    video_path: str,
    segments: List[LLMResult],
    filter_vision_only: bool = True,
) -> List[ClipResult]:
    """
    便捷函数：批量裁剪片段
    """
    clipper = FFmpegClipper()
    return await clipper.batch_clip(video_path, segments, filter_vision_only)