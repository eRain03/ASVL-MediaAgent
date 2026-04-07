"""分段结果模型"""
from sqlalchemy import Column, String, Text, Float, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import ForeignKey
from datetime import datetime
import uuid
from asvl.db.session import Base


class SegmentResultModel(Base):
    """分段结果表"""
    __tablename__ = "segment_result"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(String(64), ForeignKey("video_task.task_id"), nullable=False, index=True)
    segments = Column(JSON, nullable=False)  # [{id, start, end, text, importance, type, need_vision}]
    summary = Column(Text, nullable=True)
    processing_time = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<SegmentResultModel(task_id={self.task_id})>"