"""API 请求/响应 Pydantic 模型。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """健康检查响应。"""

    status: str = Field(..., description="服务状态")
    database: str = Field(..., description="数据库连接状态")
    version: str = Field(..., description="API 版本")


class JobCreateRequest(BaseModel):
    """创建 PPT 渲染任务请求。"""

    project_id: str = Field(..., description="关联的项目 ID", min_length=1)
    input_data: Optional[str] = Field(None, description="任务输入数据的 JSON 字符串")


class JobResponse(BaseModel):
    """PPT 渲染任务响应。"""

    id: str = Field(..., description="任务 ID")
    project_id: str = Field(..., description="关联的项目 ID")
    status: str = Field(..., description="任务状态")
    input_data: Optional[str] = Field(None, description="任务输入数据的 JSON 字符串")
    output_path: Optional[str] = Field(None, description="生成文件路径")
    error_message: Optional[str] = Field(None, description="错误信息")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    """任务列表响应。"""

    items: list[JobResponse] = Field(default_factory=list, description="任务列表")
    total: int = Field(..., description="总数")
