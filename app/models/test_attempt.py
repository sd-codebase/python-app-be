from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from enum import Enum


class TestSource(str, Enum):
    USER_GENERATED = "user_generated"
    PREDEFINED = "predefined"


# Request Models
class SubmitAnswerItem(BaseModel):
    question_id: str
    user_answer: Optional[str] = None


class SubmitTestRequest(BaseModel):
    test_id: str
    test_source: TestSource
    answers: List[SubmitAnswerItem]


# Response Models
class QuestionResult(BaseModel):
    question_id: str
    correct_answer: str
    user_answer: Optional[str]
    is_correct: bool


class SubmitTestResponse(BaseModel):
    attempt_id: str
    test_id: str
    test_name: str
    test_source: str
    total_questions: int
    correct_count: int
    wrong_count: int
    unanswered: int
    score: float
    max_score: float
    percentage: float
    negative_marking_applied: bool
    results: List[QuestionResult]
    submitted_at: datetime


class AttemptHistoryResponse(BaseModel):
    attempt_id: str
    test_id: str
    test_name: str
    test_source: str
    test_type: str
    reference_name: str
    total_questions: int
    correct_count: int
    wrong_count: int
    unanswered: int
    score: float
    max_score: float
    percentage: float
    submitted_at: datetime


class AttemptDetailResponse(BaseModel):
    attempt_id: str
    test_id: str
    test_name: str
    test_source: str
    test_type: str
    reference_name: str
    total_questions: int
    correct_count: int
    wrong_count: int
    unanswered: int
    score: float
    max_score: float
    percentage: float
    negative_marking_applied: bool
    results: List[QuestionResult]
    submitted_at: datetime
