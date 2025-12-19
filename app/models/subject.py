from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SubjectBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    course_id: Optional[str] = None
    is_active: Optional[bool] = True


class SubjectCreate(SubjectBase):
    pass


class SubjectUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    course_id: Optional[str] = None
    is_active: Optional[bool] = None


class Subject(SubjectBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
