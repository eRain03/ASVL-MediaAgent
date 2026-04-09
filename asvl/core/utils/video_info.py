"""视频信息获取工具"""
import asyncio
import json
from typing import Optional
from dataclasses import dataclass

from configs.logging import log


@dataclass
class VideoInfo:
    """视频信息"""
    duration: float  # 时长（秒）
    size: int  # 文件大小（字节）
    format: str  # 格式名称
    width: Optional[int] = None  # 视频宽度
    height: Optional[int] = None  # 视频高度
    has_audio: bool = True  # 是否有音频流
    has_video: bool = True  # 是否有视频流


async def get_video_info_from_url(video_url: str) -> VideoInfo:
    """
    使用 ffprobe 获取视频信息

    Args:
        video_url: 视频URL或本地路径

    Returns:
        VideoInfo: 视频信息

    Raises:
        RuntimeError: ffprobe 执行失败
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",  # 格式信息（时长、大小等）
        "-show_streams",  # 流信息
        video_url,
    ]

    log.debug(f"Getting video info: {video_url}")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        error_msg = stderr.decode() if stderr else "Unknown error"
        log.error(f"ffprobe failed: {error_msg}")
        raise RuntimeError(f"ffprobe error: {error_msg}")

    try:
        info = json.loads(stdout.decode())
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse ffprobe output: {e}")

    format_info = info.get("format", {})
    streams = info.get("streams", [])

    # 解析视频流信息
    video_stream = None
    audio_stream = None
    for stream in streams:
        if stream.get("codec_type") == "video" and video_stream is None:
            video_stream = stream
        elif stream.get("codec_type") == "audio" and audio_stream is None:
            audio_stream = stream

    return VideoInfo(
        duration=float(format_info.get("duration", 0)),
        size=int(format_info.get("size", 0)),
        format=format_info.get("format_name", "unknown"),
        width=int(video_stream.get("width", 0)) if video_stream else None,
        height=int(video_stream.get("height", 0)) if video_stream else None,
        has_audio=audio_stream is not None,
        has_video=video_stream is not None,
    )


async def get_video_duration(video_url: str) -> float:
    """
    快速获取视频时长

    Args:
        video_url: 视频URL或本地路径

    Returns:
        float: 时长（秒）
    """
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
        error_msg = stderr.decode() if stderr else "Unknown error"
        log.error(f"ffprobe failed: {error_msg}")
        raise RuntimeError(f"ffprobe error: {error_msg}")

    return float(stdout.decode().strip())