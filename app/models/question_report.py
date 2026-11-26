from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ReportReason(str, Enum):
    WRONG_ANSWER = "wrong_answer"            # answer key is wrong
    QUESTION_ERROR = "question_error"        # error in the question text
    OPTIONS_ERROR = "options_error"          # error in the options
    FORMATTING = "formatting"                # image / formatting / rendering issue
    OTHER = "other"


class ReportStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class CreateQuestionReportRequest(BaseModel):
    attempt_id: str = Field(..., min_length=1, max_length=100)
    question_id: str = Field(..., min_length=1, max_length=100)
    reason: ReportReason
    comment: Optional[str] = Field(None, max_length=300)


class QuestionReportResponse(BaseModel):
    id: str
    question_id: str
    attempt_id: str
    test_id: str
    test_name: Optional[str] = None
    reason: ReportReason
    comment: Optional[str] = None
    user_answer: Optional[str] = None
    correct_answer: Optional[str] = None
    status: ReportStatus
    created_at: datetime


class MyReportedQuestion(BaseModel):
    question_id: str
    status: ReportStatus


class AdminReportItem(BaseModel):
    id: str
    user_id: str
    user_name: Optional[str] = None
    reason: ReportReason
    comment: Optional[str] = None
    user_answer: Optional[str] = None
    test_name: Optional[str] = None
    created_at: datetime


class AdminReportedQuestion(BaseModel):
    question_id: str
    status: ReportStatus
    report_count: int
    reason_counts: Dict[str, int]
    correct_answer: Optional[str] = None
    has_integer_answer: bool = False
    type: Optional[str] = None
    first_reported_at: datetime
    last_reported_at: datetime
    admin_note: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    reports: List[AdminReportItem]


class AdminUpdateReportsRequest(BaseModel):
    status: ReportStatus
    admin_note: Optional[str] = Field(None, max_length=500)


class AdminUpdateReportsResponse(BaseModel):
    question_id: str
    status: ReportStatus
    updated_count: int


class AdminReportCounts(BaseModel):
    open: int
    resolved: int
    dismissed: int
