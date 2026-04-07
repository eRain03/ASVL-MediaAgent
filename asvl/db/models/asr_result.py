"""ASR结果模型"""
from sqlalchemy import Column, String, Text, Float, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from asvl.db.session import Base


class ASRResultModel(Base):
    """ASR结果表"""
    __tablename__ = "asr_result"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(String(64), ForeignKey("video_task.task_id"), nullable=False, index=True)
    language = Column(String(16), nullable=True)
    duration = Column(Float, nullable=True)
    segments = Column(JSON, nullable=False)  # [{start, end, text, confidence}]
    confidence = Column(Float, nullable=True)
    processing_time = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<ASRResultModel(task_id={self.task_id}, language={self.language})>"