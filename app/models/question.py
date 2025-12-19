from datetime import datetime
from typing import Any, Optional, List
from pydantic import BaseModel


class QuestionBase(BaseModel):
    question: str
    options: Optional[dict[str, Any]] = None
    has_integer_answer: Optional[bool] = None
    answer: str
    solutions: Optional[List[str]] = None
    level: Optional[int] = None
    is_marked_for_review: Optional[bool] = False
    review_in_app: Optional[bool] = False
    sr_no: Optional[int] = None
    pyo: Optional[str] = None
    extra: Optional[dict[str, Any]] = None
    topic_id: Optional[str] = None
    chapter_id: Optional[str] = None
    subject_id: Optional[str] = None
    course_id: Optional[str] = None
    is_active: Optional[bool] = True
    verified_in_app: bool = False


class QuestionCreate(QuestionBase):
    pass


class QuestionUpdate(BaseModel):
    question: Optional[str] = None
    options: Optional[dict[str, Any]] = None
    has_integer_answer: Optional[bool] = None
    answer: Optional[str] = None
    solutions: Optional[List[str]] = None
    level: Optional[int] = None
    is_marked_for_review: Optional[bool] = None
    review_in_app: Optional[bool] = None
    sr_no: Optional[int] = None
    pyo: Optional[str] = None
    extra: Optional[dict[str, Any]] = None
    topic_id: Optional[str] = None
    chapter_id: Optional[str] = None
    subject_id: Optional[str] = None
    course_id: Optional[str] = None
    is_active: Optional[bool] = None
    verified_in_app: Optional[bool] = None


class Question(QuestionBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
