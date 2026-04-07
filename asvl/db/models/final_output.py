"""最终输出模型"""
from sqlalchemy import Column, String, Text, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import ForeignKey
from datetime import datetime
import uuid
from asvl.db.session import Base


class FinalOutputModel(Base):
    """最终输出表"""
    __tablename__ = "final_output"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(String(64), ForeignKey("video_task.task_id"), unique=True, nullable=False, index=True)
    summary = Column(Text, nullable=True)
    highlights = Column(JSON, nullable=False)
    alignment_issues = Column(JSON, nullable=True)
    full_result = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<FinalOutputModel(task_id={self.task_id})>"