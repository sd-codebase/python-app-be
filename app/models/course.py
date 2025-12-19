from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class CourseBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = True


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class Course(CourseBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
