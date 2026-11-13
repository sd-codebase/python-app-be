from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.database import get_database
from app.models.course import Course
from app.models.response import APIResponse

router = APIRouter(prefix="/courses", tags=["courses"])


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
