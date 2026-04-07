"""视频处理工具"""
import subprocess
import asyncio
from typing import Optional
from configs.logging import log


async def extract_audio(
    video_path: str,
    output_path: str,
    audio_format: str = "wav",
) -> str:
    """
    从视频提取音频

    Args:
        video_path: 视频文件路径
        output_path: 输出音频路径
        audio_format: 音频格式

    Returns:
        str: 输出音频路径
    """
    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vn",  # 不包含视频
        "-acodec", "pcm_s16le",  # WAV格式
        "-ar", "16000",  # 16kHz采样率
        "-ac", "1",  # 单声道
        "-y",  # 覆盖输出
        output_path,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        log.error(f"FFmpeg audio extraction failed: {stderr.decode()}")
        raise RuntimeError(f"FFmpeg error: {stderr.decode()}")

    log.info(f"Extracted audio: {video_path} -> {output_path}")
    return output_path


async def get_video_duration(video_path: str) -> float:
    """
    获取视频时长

    Args:
        video_path: 视频文件路径

    Returns:
        float: 时长（秒）
    """
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
        log.error(f"FFprobe failed: {stderr.decode()}")
        raise RuntimeError(f"FFprobe error: {stderr.decode()}")

    duration = float(stdout.decode().strip())
    return duration


async def clip_video(
    video_path: str,
    output_path: str,
    start_time: float,
    end_time: float,
    padding: Optional[float] = None,
) -> str:
    """
    裁剪视频片段

    Args:
        video_path: 源视频路径
        output_path: 输出路径
        start_time: 开始时间（秒）
        end_time: 结束时间（秒）
        padding: 时间padding

    Returns:
        str: 输出视频路径
    """
    if padding:
        start_time = max(0, start_time - padding)
        end_time = end_time + padding

    duration = end_time - start_time

    cmd = [
        "ffmpeg",
        "-ss", str(start_time),
        "-i", video_path,
        "-t", str(duration),
        "-c", "copy",  # 直接复制，不重新编码
        "-y",
        output_path,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        log.error(f"FFmpeg clip failed: {stderr.decode()}")
        raise RuntimeError(f"FFmpeg error: {stderr.decode()}")

    log.info(f"Clipped video: {start_time}-{end_time}s -> {output_path}")
    return output_path


async def extract_frames(
    video_path: str,
    output_dir: str,
    fps: Optional[float] = None,
    max_frames: Optional[int] = None,
) -> list:
    """
    提取视频帧

    Args:
        video_path: 视频路径
        output_dir: 输出目录
        fps: 帧率（可选，默认提取关键帧）
        max_frames: 最大帧数

    Returns:
        list: 帧图片路径列表
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    # 使用fps提取帧，或使用关键帧
    if fps:
        filter_arg = f"fps={fps}"
    else:
        # 提取关键帧
        filter_arg = "select='eq(pict_type,I)'"

    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vf", filter_arg,
        "-vsync", "vfr",  # 变帧率
        "-q:v", "2",  # 高质量
        "-y",
        f"{output_dir}/frame_%04d.jpg",
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        log.error(f"FFmpeg frame extraction failed: {stderr.decode()}")
        raise RuntimeError(f"FFmpeg error: {stderr.decode()}")

    # 获取生成的帧文件列表
    frames = sorted([
        os.path.join(output_dir, f)
        for f in os.listdir(output_dir)
        if f.startswith("frame_") and f.endswith(".jpg")
    ])

    if max_frames and len(frames) > max_frames:
        frames = frames[:max_frames]

    log.info(f"Extracted {len(frames)} frames from {video_path}")
    return frames