from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from enum import Enum


class PredefinedTestStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PUBLISHED = "published"
    FAILED = "failed"
    ARCHIVED = "archived"


# Request Models
class CreatePredefinedTestRequest(BaseModel):
    set_test_id: str
    reference_id: str
    name: Optional[str] = None  # Optional custom name, defaults to set_test_name


class UpdatePredefinedTestRequest(BaseModel):
    is_published: Optional[bool] = None


# Embedded Models (for DB storage - minimal data)
class PredefinedTestQuestion(BaseModel):
    question_id: str
    has_integer_answer: Optional[bool] = False
    answer: str
    marks_per_question: float = 4.0
    negative_marks: float = 1.0


# Response Models - Admin
class PredefinedTestAdminResponse(BaseModel):
    id: str
    name: str
    set_test_id: str
    set_test_name: str
    test_type: str
    reference_id: str
    reference_name: str
    time_limit_minutes: int
    total_questions: int
    status: str
    error_message: Optional[str] = None
    created_by: str
    created_at: datetime
    published_at: Optional[datetime] = None


class PredefinedTestDetailAdminResponse(BaseModel):
    id: str
    name: str
    set_test_id: str
    set_test_name: str
    test_type: str
    reference_id: str
    reference_name: str
    time_limit_minutes: int
    total_questions: int
    status: str
    error_message: Optional[str] = None
    questions: List[PredefinedTestQuestion]
    created_by: str
    created_at: datetime
    published_at: Optional[datetime] = None


# Response Models - User
class QuestionMinimalPredefined(BaseModel):
    """Minimal question info without heavy data."""
    question_id: str
    has_integer_answer: Optional[bool] = False


class PredefinedTestUserResponse(BaseModel):
    id: str
    name: str
    test_type: str
    reference_id: str
    reference_name: str
    time_limit_minutes: int
    total_questions: int
    has_attempted: bool = False
    best_score: Optional[float] = None
    attempt_count: int = 0


class PredefinedTestMetadataResponse(BaseModel):
    """Detailed test metadata with minimal question data (similar to user-tests)."""
    id: str
    name: str
    test_type: str
    reference_id: str
    reference_name: str
    time_limit_minutes: int
    total_questions: int
    questions: List[QuestionMinimalPredefined]


class QuestionForAttempt(BaseModel):
    question_id: str
    question: str
    options: Optional[dict] = None
    has_integer_answer: Optional[bool] = False
    user_answer: Optional[str] = None


class PredefinedTestAttemptResponse(BaseModel):
    attempt_id: str
    test_id: str
    test_name: str
    test_type: str
    reference_name: str
    time_limit_minutes: int
    total_questions: int
    questions: List[QuestionForAttempt]
    started_at: datetime


# Attempt Models
class AttemptAnswerItem(BaseModel):
    question_id: str
    user_answer: Optional[str] = None


class SubmitAttemptRequest(BaseModel):
    answers: List[AttemptAnswerItem]


class AttemptQuestionResult(BaseModel):
    question_id: str
    user_answer: Optional[str]
    correct_answer: str
    is_correct: bool


class SubmitAttemptResponse(BaseModel):
    attempt_id: str
    test_id: str
    total_questions: int
    correct_count: int
    wrong_count: int
    unanswered: int
    score: float
    max_score: float
    percentage: float
    negative_marking_applied: bool
    results: List[AttemptQuestionResult]


class UserAttemptHistoryResponse(BaseModel):
    attempt_id: str
    test_id: str
    test_name: str
    test_type: str
    reference_name: str
    total_questions: int
    score: float
    max_score: float
    percentage: float
    started_at: datetime
    submitted_at: datetime
