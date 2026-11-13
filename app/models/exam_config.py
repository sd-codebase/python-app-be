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


class ExamConfig(ExamConfigBase):
    # Configs are written directly to the database (no write API), so these
    # metadata fields may be absent.
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
