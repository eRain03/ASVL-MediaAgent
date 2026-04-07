"""VL结果模型"""
from sqlalchemy import Column, String, Text, Float, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import ForeignKey
from datetime import datetime
import uuid
from asvl.db.session import Base


class VLResultModel(Base):
    """VL结果表"""
    __tablename__ = "vl_result"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(String(64), ForeignKey("video_task.task_id"), nullable=False, index=True)
    clip_id = Column(String(64), nullable=False)
    vision_summary = Column(Text, nullable=True)
    actions = Column(JSON, nullable=True)  # ["点击", "输入"]
    objects = Column(JSON, nullable=True)  # ["按钮", "菜单"]
    scene_description = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    processing_time = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<VLResultModel(task_id={self.task_id}, clip_id={self.clip_id})>"