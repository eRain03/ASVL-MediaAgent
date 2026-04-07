"""视频任务模型"""
from sqlalchemy import Column, String, Text, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from asvl.db.session import Base


class VideoTask(Base):
    """视频任务表"""
    __tablename__ = "video_task"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(String(64), unique=True, nullable=False, index=True)
    video_id = Column(String(64), nullable=False)
    video_url = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="pending", index=True)
    options = Column(JSON, nullable=True)
    progress = Column(JSON, nullable=False, default=dict)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<VideoTask(task_id={self.task_id}, status={self.status})>"