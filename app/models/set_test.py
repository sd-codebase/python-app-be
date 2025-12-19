from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from enum import Enum


class SetTestType(str, Enum):
    TOPIC = "topic"
    CHAPTER = "chapter"
    SUBJECT = "subject"
    COURSE = "course"


class Difficulty(BaseModel):
    L1: int = Field(default=0, ge=0)
    L2: int = Field(default=0, ge=0)
    L3: int = Field(default=0, ge=0)


class Section(BaseModel):
    id: str
    name: str
    question_count: int = Field(ge=1)
    attempt_count: int = Field(ge=1)
    marks_per_question: float = Field(ge=0)
    negative_marks: float = Field(ge=0, default=0)
    is_numerical: bool = False
    difficulty: Difficulty


class SubjectSection(BaseModel):
    subject_id: str
    subject_name: str
    sections: List[Section]


# Base request model with common fields
class SetTestBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    time_limit_minutes: int = Field(ge=1)
    is_active: bool = True


# Topic Test - Simple format
class TopicTestCreate(SetTestBase):
    test_type: SetTestType = SetTestType.TOPIC
    topic_id: str
    question_count: int = Field(ge=1)
    marks_per_question: float = Field(ge=0)
    negative_marks: float = Field(ge=0, default=0)
    difficulty: Difficulty


class TopicTestUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    time_limit_minutes: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None
    topic_id: Optional[str] = None
    question_count: Optional[int] = Field(None, ge=1)
    marks_per_question: Optional[float] = Field(None, ge=0)
    negative_marks: Optional[float] = Field(None, ge=0)
    difficulty: Optional[Difficulty] = None


# Chapter Test - Similar to topic
class ChapterTestCreate(SetTestBase):
    test_type: SetTestType = SetTestType.CHAPTER
    chapter_id: str
    question_count: int = Field(ge=1)
    marks_per_question: float = Field(ge=0)
    negative_marks: float = Field(ge=0, default=0)
    difficulty: Difficulty


class ChapterTestUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    time_limit_minutes: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None
    chapter_id: Optional[str] = None
    question_count: Optional[int] = Field(None, ge=1)
    marks_per_question: Optional[float] = Field(None, ge=0)
    negative_marks: Optional[float] = Field(None, ge=0)
    difficulty: Optional[Difficulty] = None


# Subject Test - Has sections
class SubjectTestCreate(SetTestBase):
    test_type: SetTestType = SetTestType.SUBJECT
    subject_id: str
    sections: List[Section]


class SubjectTestUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    time_limit_minutes: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None
    subject_id: Optional[str] = None
    sections: Optional[List[Section]] = None


# Course Test - Has subject_sections
class CourseTestCreate(SetTestBase):
    test_type: SetTestType = SetTestType.COURSE
    course_id: str
    subject_sections: List[SubjectSection]


class CourseTestUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    time_limit_minutes: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None
    course_id: Optional[str] = None
    subject_sections: Optional[List[SubjectSection]] = None


# Response models
class SetTestResponse(BaseModel):
    id: str
    name: str
    time_limit_minutes: int
    is_active: bool
    test_type: str
    created_at: datetime
    updated_at: datetime

    # Optional fields based on test_type
    topic_id: Optional[str] = None
    chapter_id: Optional[str] = None
    subject_id: Optional[str] = None
    course_id: Optional[str] = None

    question_count: Optional[int] = None
    marks_per_question: Optional[float] = None
    negative_marks: Optional[float] = None
    difficulty: Optional[Difficulty] = None

    sections: Optional[List[Section]] = None
    subject_sections: Optional[List[SubjectSection]] = None


class SetTestListResponse(BaseModel):
    id: str
    name: str
    time_limit_minutes: int
    is_active: bool
    test_type: str
    created_at: datetime
    updated_at: datetime
