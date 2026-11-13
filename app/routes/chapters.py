from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.database import get_database
from app.models.chapter import Chapter
from app.models.response import APIResponse

router = APIRouter(prefix="/chapters", tags=["chapters"])


@router.get("/", response_model=APIResponse[List[Chapter]])
async def get_chapters(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    subject_id: Optional[str] = None,
    is_active: Optional[bool] = None,
):
    db = get_database()
    query = {}
    if subject_id:
        query["subject_id"] = subject_id
    if is_active is not None:
        query["is_active"] = is_active

    cursor = db.chapters.find(query).sort("order_num", 1).skip(skip).limit(limit)
    chapters = await cursor.to_list(length=limit)
    return {"data": chapters, "message": "Chapters retrieved successfully"}


@router.get("/{chapter_id}", response_model=APIResponse[Chapter])
async def get_chapter(chapter_id: str):
    db = get_database()
    chapter = await db.chapters.find_one({"id": chapter_id})
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return {"data": chapter, "message": "Chapter retrieved successfully"}
