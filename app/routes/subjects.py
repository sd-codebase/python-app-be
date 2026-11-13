from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.database import get_database
from app.models.subject import Subject
from app.models.response import APIResponse

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.get("/", response_model=APIResponse[List[Subject]])
async def get_subjects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    course_id: Optional[str] = None,
    is_active: Optional[bool] = None,
):
    db = get_database()
    query = {}
    if course_id:
        query["course_id"] = course_id
    if is_active is not None:
        query["is_active"] = is_active

    cursor = db.subjects.find(query).skip(skip).limit(limit)
    subjects = await cursor.to_list(length=limit)
    return {"data": subjects, "message": "Subjects retrieved successfully"}


@router.get("/{subject_id}", response_model=APIResponse[Subject])
async def get_subject(subject_id: str):
    db = get_database()
    subject = await db.subjects.find_one({"id": subject_id})
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    return {"data": subject, "message": "Subject retrieved successfully"}
