"""视频裁剪模块"""
from asvl.core.clipper.base import ClipperBase
from asvl.core.clipper.ffmpeg_clipper import FFmpegClipper, clip_segments
from asvl.core.clipper.merger import ClipMerger

__all__ = ["ClipperBase", "FFmpegClipper", "ClipMerger", "clip_segments"]