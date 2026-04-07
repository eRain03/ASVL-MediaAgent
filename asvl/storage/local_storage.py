"""本地存储"""
import os
import aiofiles
from typing import Optional
from pathlib import Path
from configs.settings import get_settings
from configs.logging import log

settings = get_settings()


class LocalStorage:
    """本地文件存储"""

    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path or "data")
        self.videos_path = self.base_path / "videos"
        self.clips_path = self.base_path / "clips"
        self.temp_path = self.base_path / "temp"

        # 创建目录
        for path in [self.videos_path, self.clips_path, self.temp_path]:
            path.mkdir(parents=True, exist_ok=True)

        log.info(f"LocalStorage initialized: base={self.base_path}")

    async def save_video(
        self,
        filename: str,
        data: bytes,
    ) -> str:
        """保存视频文件"""
        path = self.videos_path / filename
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)
        log.info(f"Saved video: {path}")
        return str(path)

    async def save_clip(
        self,
        filename: str,
        data: bytes,
    ) -> str:
        """保存片段文件"""
        path = self.clips_path / filename
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)
        log.info(f"Saved clip: {path}")
        return str(path)

    async def save_temp(
        self,
        filename: str,
        data: bytes,
    ) -> str:
        """保存临时文件"""
        path = self.temp_path / filename
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)
        return str(path)

    def get_video_path(self, filename: str) -> str:
        """获取视频路径"""
        return str(self.videos_path / filename)

    def get_clip_path(self, filename: str) -> str:
        """获取片段路径"""
        return str(self.clips_path / filename)

    async def cleanup_temp(self) -> None:
        """清理临时文件"""
        for file in self.temp_path.iterdir():
            file.unlink()
        log.info("Cleaned up temp files")