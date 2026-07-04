"""SQLAlchemy 数据库模型。"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PPTJob(Base):
    """PPT 渲染任务记录。"""

    __tablename__ = "ppt_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), nullable=False, index=True, comment="关联的项目 ID")
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        comment="任务状态: pending/running/completed/failed",
    )
    input_data = Column(Text, nullable=True, comment="任务输入数据的 JSON 字符串")
    output_path = Column(Text, nullable=True, comment="生成文件路径")
    error_message = Column(Text, nullable=True, comment="失败时的错误信息")
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    def __repr__(self) -> str:
        return f"<PPTJob(id={self.id}, project_id={self.project_id}, status={self.status})>"
