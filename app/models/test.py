from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from enum import Enum


class TestType(str, Enum):
    TOPIC = "topic"
    CHAPTER = "chapter"
    SUBJECT = "subject"
    COURSE = "course"


class GenerationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# Request Models
class GenerateTestRequest(BaseModel):
    set_test_id: str
    reference_id: str


class AnswerItem(BaseModel):
    question_id: str
    user_answer: Optional[str] = None


class SubmitTestRequest(BaseModel):
    answers: List[AnswerItem]


# Embedded Models (for DB storage - minimal data)
class TestQuestion(BaseModel):
    question_id: str
    has_integer_answer: Optional[bool] = False
    answer: str
    user_answer: Optional[str] = None


# Response Models
class TestGenerationResponse(BaseModel):
    id: str
    name: str  # Auto-generated name
    set_test_id: str
    set_test_name: str
    test_type: str
    reference_id: str
    reference_name: str
    generation_status: str
    error_message: Optional[str] = None
    created_at: datetime


class QuestionMinimal(BaseModel):
    """Minimal question info without heavy data."""
    question_id: str
    has_integer_answer: bool


class TestMetadataResponse(BaseModel):
    id: str
    name: str  # Auto-generated name
    set_test_id: str
    set_test_name: str
    test_type: str
    reference_id: str
    reference_name: str
    total_questions: int
    generation_status: str
    is_submitted: bool
    score: Optional[float] = None
    questions: List[QuestionMinimal]  # Just IDs and has_integer_answer
    created_at: datetime


class QuestionForTaking(BaseModel):
    question_id: str
    question: str
    options: Optional[dict] = None
    has_integer_answer: Optional[bool] = False
    user_answer: Optional[str] = None


class TestDetailResponse(BaseModel):
    id: str
    name: str  # Auto-generated name
    set_test_id: str
    set_test_name: str
    test_type: str
    reference_id: str
    reference_name: str
    total_questions: int
    time_limit_minutes: int
    generation_status: str
    is_submitted: bool
    score: Optional[float] = None
    questions: List[QuestionForTaking]
    created_at: datetime


class QuestionResult(BaseModel):
    question_id: str
    user_answer: Optional[str]
    correct_answer: str
    is_correct: bool


class SubmitTestResponse(BaseModel):
    test_id: str
    total_questions: int
    correct_count: int
    wrong_count: int
    unanswered: int
    score: float
    max_score: float
    percentage: float
    negative_marking_applied: bool
    results: List[QuestionResult]
