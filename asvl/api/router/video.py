"""视频管理API"""
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from asvl.db.session import get_session
from asvl.db.repositories.task_repo import TaskRepository
from asvl.storage.local_storage import LocalStorage
from configs.settings import get_settings
from configs.logging import log

router = APIRouter()
settings = get_settings()


@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    """上传本地视频文件到本地存储"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="未提供文件名")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}:
        raise HTTPException(status_code=400, detail="不支持的视频格式")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")

    video_id = f"vid_{uuid.uuid4().hex[:8]}"
    storage = LocalStorage()
    saved_filename = f"{video_id}{suffix}"
    video_path = await storage.save_video(saved_filename, content)

    log.info(f"Uploaded video saved: {video_path}")

    return {
        "video_id": video_id,
        "video_url": video_path,
        "filename": file.filename,
        "size": len(content),
    }


@router.post("/upload-url")
async def get_upload_url(
    filename: str,
    content_type: str = "video/mp4",
    session: AsyncSession = Depends(get_session),
):
    """获取视频上传URL"""
    video_id = f"vid_{uuid.uuid4().hex[:8]}"

    # TODO: 实现OSS预签名URL生成

    return {
        "video_id": video_id,
        "upload_url": f"https://{settings.OSS_BUCKET}.{settings.OSS_ENDPOINT}/{video_id}/{filename}",
        "expires_at": "2026-04-08T00:00:00Z",
    }


@router.get("/{video_id}")
async def get_video_info(
    video_id: str,
    session: AsyncSession = Depends(get_session),
):
    """获取视频信息"""
    repo = TaskRepository(session)
    tasks = await repo.get_by_video_id(video_id)

    return {
        "video_id": video_id,
        "tasks": [{"task_id": t.task_id, "status": t.status} for t in tasks],
    }