from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class ScorePercentilePoint(BaseModel):
    score: int
    percentile: float


class ExamConfigBase(BaseModel):
    exam_type: str = Field(..., description="Exam type identifier (e.g., NEET, JEE_MAIN)")
    exam_max_score: int = Field(..., description="Maximum score for the exam")
    total_candidates: int = Field(..., description="Total number of candidates")
    score_percentile: List[ScorePercentilePoint] = Field(
        ..., description="Score-percentile data points sorted by score descending"
    )
    data_year: str = Field(..., description="Year of the exam data (e.g., 2025)")
    is_active: bool = Field(default=True, description="Whether this config is active")


class ExamConfigCreate(ExamConfigBase):
    pass


class ExamConfigUpdate(BaseModel):
    exam_max_score: Optional[int] = None
    total_candidates: Optional[int] = None
    score_percentile: Optional[List[ScorePercentilePoint]] = None
    data_year: Optional[str] = None
    is_active: Optional[bool] = None


class ExamConfig(ExamConfigBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
