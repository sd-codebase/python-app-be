from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from uuid import uuid4

from app.database import get_database
from app.models.subject import Subject, SubjectCreate, SubjectUpdate
from app.models.response import APIResponse

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.post("/", response_model=APIResponse[Subject], status_code=201)
async def create_subject(subject: SubjectCreate):
    db = get_database()
    now = datetime.utcnow()

    subject_dict = subject.model_dump()
    subject_dict["id"] = str(uuid4())
    subject_dict["created_at"] = now
    subject_dict["updated_at"] = now

    # Validate course_id if provided
    if subject_dict.get("course_id"):
        course = await db.courses.find_one({"id": subject_dict["course_id"]})
        if not course:
            raise HTTPException(status_code=400, detail="Course not found")

    await db.subjects.insert_one(subject_dict)
    return {"data": subject_dict, "message": "Subject created successfully"}


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


@router.put("/{subject_id}", response_model=APIResponse[Subject])
async def update_subject(subject_id: str, subject_update: SubjectUpdate):
    db = get_database()

    update_data = subject_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Validate course_id if being updated
    if "course_id" in update_data and update_data["course_id"]:
        course = await db.courses.find_one({"id": update_data["course_id"]})
        if not course:
            raise HTTPException(status_code=400, detail="Course not found")

    update_data["updated_at"] = datetime.utcnow()

    result = await db.subjects.update_one(
        {"id": subject_id},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Subject not found")

    subject = await db.subjects.find_one({"id": subject_id})
    return {"data": subject, "message": "Subject updated successfully"}


@router.delete("/{subject_id}", response_model=APIResponse)
async def delete_subject(subject_id: str):
    db = get_database()
    result = await db.subjects.delete_one({"id": subject_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Subject not found")
    return {"data": None, "message": "Subject deleted successfully"}
