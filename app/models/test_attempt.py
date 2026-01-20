from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from enum import Enum


class TestSource(str, Enum):
    USER_GENERATED = "user_generated"
    PREDEFINED = "predefined"


class RankRange(BaseModel):
    lower: int
    upper: int


class RankPrediction(BaseModel):
    percentile: float
    predicted_rank: int
    rank_range: RankRange
    normalized_score: float
    exam_max_score: int
    exam_type: str
    prediction_data_year: str


# Request Models
class SubmitAnswerItem(BaseModel):
    question_id: str
    user_answer: Optional[str] = None


class SubmitTestRequest(BaseModel):
    test_id: str
    test_source: TestSource
    answers: List[SubmitAnswerItem]
    time_taken_seconds: Optional[int] = None  # Time taken by user in seconds


# Response Models
class QuestionResult(BaseModel):
    question_id: str
    has_integer_answer: Optional[bool] = False
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
    time_taken_seconds: Optional[int] = None
    results: List[QuestionResult]
    submitted_at: datetime
    rank_prediction: Optional[RankPrediction] = None


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
    rank_prediction: Optional[RankPrediction] = None


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
    time_taken_seconds: Optional[int] = None
    results: List[QuestionResult]
    submitted_at: datetime
    rank_prediction: Optional[RankPrediction] = None
