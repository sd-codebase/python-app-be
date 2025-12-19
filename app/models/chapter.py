from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ChapterBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    order_num: int
    subject_id: Optional[str] = None
    is_active: Optional[bool] = True


class ChapterCreate(ChapterBase):
    pass


class ChapterUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    order_num: Optional[int] = None
    subject_id: Optional[str] = None
    is_active: Optional[bool] = None


class Chapter(ChapterBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
