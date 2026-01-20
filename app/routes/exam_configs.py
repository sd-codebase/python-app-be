from datetime import datetime
from typing import List
from uuid import uuid4
from fastapi import APIRouter, HTTPException, status

from app.database import get_database
from app.models.response import APIResponse
from app.models.exam_config import (
    ExamConfig,
    ExamConfigCreate,
    ExamConfigUpdate,
)

router = APIRouter(prefix="/exam-configs", tags=["exam-configs"])


@router.post("/", response_model=APIResponse[ExamConfig], status_code=201)
async def create_exam_config(config: ExamConfigCreate):
    """Create a new exam configuration."""
    db = get_database()

    # Check if exam_type already exists
    existing = await db.exam_configs.find_one({"exam_type": config.exam_type})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Exam config for '{config.exam_type}' already exists"
        )

    now = datetime.utcnow()
    config_dict = config.model_dump()
    config_dict["id"] = str(uuid4())
    config_dict["created_at"] = now
    config_dict["updated_at"] = now

    # Convert score_percentile to list of dicts for storage
    config_dict["score_percentile"] = [
        {"score": sp["score"], "percentile": sp["percentile"]}
        for sp in config_dict["score_percentile"]
    ]

    await db.exam_configs.insert_one(config_dict)

    return {"data": config_dict, "message": "Exam config created successfully"}


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


@router.put("/{exam_type}", response_model=APIResponse[ExamConfig])
async def update_exam_config(exam_type: str, update: ExamConfigUpdate):
    """Update an exam configuration."""
    db = get_database()

    update_data = update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )

    update_data["updated_at"] = datetime.utcnow()

    # Convert score_percentile if provided
    if "score_percentile" in update_data and update_data["score_percentile"]:
        update_data["score_percentile"] = [
            {"score": sp["score"], "percentile": sp["percentile"]}
            for sp in update_data["score_percentile"]
        ]

    result = await db.exam_configs.update_one(
        {"exam_type": exam_type},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exam config for '{exam_type}' not found"
        )

    config = await db.exam_configs.find_one({"exam_type": exam_type})
    return {"data": config, "message": "Exam config updated successfully"}


@router.delete("/{exam_type}", response_model=APIResponse[None])
async def delete_exam_config(exam_type: str):
    """Delete an exam configuration."""
    db = get_database()

    result = await db.exam_configs.delete_one({"exam_type": exam_type})
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exam config for '{exam_type}' not found"
        )

    return {"data": None, "message": "Exam config deleted successfully"}
