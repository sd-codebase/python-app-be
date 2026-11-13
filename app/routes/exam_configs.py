from typing import List
from fastapi import APIRouter, HTTPException, status

from app.database import get_database
from app.models.response import APIResponse
from app.models.exam_config import ExamConfig

router = APIRouter(prefix="/exam-configs", tags=["exam-configs"])


@router.get("/", response_model=APIResponse[List[ExamConfig]])
async def get_exam_configs(is_active: bool = None):
    """Get all exam configurations."""
    db = get_database()

    query = {}
    if is_active is not None:
        query["is_active"] = is_active

    cursor = db.exam_configs.find(query).sort("exam_type", 1)
    configs = await cursor.to_list(length=100)

    return {"data": configs, "message": "Exam configs retrieved successfully"}


@router.get("/{exam_type}", response_model=APIResponse[ExamConfig])
async def get_exam_config(exam_type: str):
    """Get a specific exam configuration by exam type."""
    db = get_database()

    config = await db.exam_configs.find_one({"exam_type": exam_type})
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exam config for '{exam_type}' not found"
        )

    return {"data": config, "message": "Exam config retrieved successfully"}
