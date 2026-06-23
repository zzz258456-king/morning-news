from typing import List, Optional
from pydantic import BaseModel


class OutlinePage(BaseModel):
    id: str
    title: str
    content: Optional[str] = None
    notes: Optional[str] = None


class TemplateOption(BaseModel):
    id: str
    name: str
    colors: List[str]
    layout: str
    source: str


class SlideImage(BaseModel):
    source: str
    url: Optional[str] = None
    local_path: Optional[str] = None
    position: str = "right"


class SlideConfig(BaseModel):
    page_id: str
    title: str
    body: str
    image: Optional[SlideImage] = None
    layout: str = "default"


class ProjectConfig(BaseModel):
    id: str
    title: str
    outline: List[OutlinePage]
    template: TemplateOption
    slides: List[SlideConfig]
    output_path: Optional[str] = None


class GenerateRequest(BaseModel):
    config: ProjectConfig
