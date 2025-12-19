from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class TopicBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    order_num: int
    chapter_id: Optional[str] = None
    is_active: Optional[bool] = True
    resources_directory: Optional[str] = None


class TopicCreate(TopicBase):
    pass


class TopicUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    order_num: Optional[int] = None
    chapter_id: Optional[str] = None
    is_active: Optional[bool] = None
    resources_directory: Optional[str] = None


class Topic(TopicBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
