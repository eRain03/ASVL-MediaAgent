"""视频片段模型"""
from sqlalchemy import Column, String, Text, Float, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import ForeignKey
from datetime import datetime
import uuid
from asvl.db.session import Base


class ClipResultModel(Base):
    """视频片段表"""
    __tablename__ = "clip_result"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(String(64), ForeignKey("video_task.task_id"), nullable=False, index=True)
    segment_id = Column(String(64), nullable=False)
    clip_url = Column(Text, nullable=True)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    duration = Column(Float, nullable=True)
    storage_path = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<ClipResultModel(task_id={self.task_id}, segment_id={self.segment_id})>"