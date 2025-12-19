from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from uuid import uuid4

from app.database import get_database
from app.models.course import Course, CourseCreate, CourseUpdate
from app.models.response import APIResponse

router = APIRouter(prefix="/courses", tags=["courses"])


@router.post("/", response_model=APIResponse[Course], status_code=201)
async def create_course(course: CourseCreate):
    db = get_database()
    now = datetime.utcnow()

    course_dict = course.model_dump()
    course_dict["id"] = str(uuid4())
    course_dict["created_at"] = now
    course_dict["updated_at"] = now

    await db.courses.insert_one(course_dict)
    return {"data": course_dict, "message": "Course created successfully"}


@router.get("/", response_model=APIResponse[List[Course]])
async def get_courses(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_active: Optional[bool] = None,
):
    db = get_database()
    query = {}
    if is_active is not None:
        query["is_active"] = is_active

    cursor = db.courses.find(query).skip(skip).limit(limit)
    courses = await cursor.to_list(length=limit)
    return {"data": courses, "message": "Courses retrieved successfully"}


@router.get("/{course_id}", response_model=APIResponse[Course])
async def get_course(course_id: str):
    db = get_database()
    course = await db.courses.find_one({"id": course_id})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return {"data": course, "message": "Course retrieved successfully"}


@router.put("/{course_id}", response_model=APIResponse[Course])
async def update_course(course_id: str, course_update: CourseUpdate):
    db = get_database()

    update_data = course_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    update_data["updated_at"] = datetime.utcnow()

    result = await db.courses.update_one(
        {"id": course_id},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Course not found")

    course = await db.courses.find_one({"id": course_id})
    return {"data": course, "message": "Course updated successfully"}


@router.delete("/{course_id}", response_model=APIResponse)
async def delete_course(course_id: str):
    db = get_database()
    result = await db.courses.delete_one({"id": course_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Course not found")
    return {"data": None, "message": "Course deleted successfully"}
