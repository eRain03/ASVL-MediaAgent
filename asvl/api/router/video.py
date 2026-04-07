"""视频管理API"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from asvl.db.session import get_session
from asvl.db.repositories.task_repo import TaskRepository
from configs.settings import get_settings
from configs.logging import log

router = APIRouter()
settings = get_settings()


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