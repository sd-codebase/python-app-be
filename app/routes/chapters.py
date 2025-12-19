from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from uuid import uuid4

from app.database import get_database
from app.models.chapter import Chapter, ChapterCreate, ChapterUpdate
from app.models.response import APIResponse

router = APIRouter(prefix="/chapters", tags=["chapters"])


@router.post("/", response_model=APIResponse[Chapter], status_code=201)
async def create_chapter(chapter: ChapterCreate):
    db = get_database()
    now = datetime.utcnow()

    chapter_dict = chapter.model_dump()
    chapter_dict["id"] = str(uuid4())
    chapter_dict["created_at"] = now
    chapter_dict["updated_at"] = now

    # Validate subject_id if provided
    if chapter_dict.get("subject_id"):
        subject = await db.subjects.find_one({"id": chapter_dict["subject_id"]})
        if not subject:
            raise HTTPException(status_code=400, detail="Subject not found")

    # Check unique constraint on order_num + subject_id
    existing_order = await db.chapters.find_one({
        "order_num": chapter_dict["order_num"],
        "subject_id": chapter_dict.get("subject_id")
    })
    if existing_order:
        raise HTTPException(
            status_code=400,
            detail="Chapter with this order_num already exists for this subject"
        )

    await db.chapters.insert_one(chapter_dict)
    return {"data": chapter_dict, "message": "Chapter created successfully"}


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


@router.put("/{chapter_id}", response_model=APIResponse[Chapter])
async def update_chapter(chapter_id: str, chapter_update: ChapterUpdate):
    db = get_database()

    update_data = chapter_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Validate subject_id if being updated
    if "subject_id" in update_data and update_data["subject_id"]:
        subject = await db.subjects.find_one({"id": update_data["subject_id"]})
        if not subject:
            raise HTTPException(status_code=400, detail="Subject not found")

    # Check unique constraint if order_num or subject_id is being updated
    if "order_num" in update_data or "subject_id" in update_data:
        current = await db.chapters.find_one({"id": chapter_id})
        if not current:
            raise HTTPException(status_code=404, detail="Chapter not found")

        new_order = update_data.get("order_num", current["order_num"])
        new_subject = update_data.get("subject_id", current.get("subject_id"))

        existing = await db.chapters.find_one({
            "order_num": new_order,
            "subject_id": new_subject,
            "id": {"$ne": chapter_id}
        })
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Chapter with this order_num already exists for this subject"
            )

    update_data["updated_at"] = datetime.utcnow()

    result = await db.chapters.update_one(
        {"id": chapter_id},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Chapter not found")

    chapter = await db.chapters.find_one({"id": chapter_id})
    return {"data": chapter, "message": "Chapter updated successfully"}


@router.delete("/{chapter_id}", response_model=APIResponse)
async def delete_chapter(chapter_id: str):
    db = get_database()
    result = await db.chapters.delete_one({"id": chapter_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return {"data": None, "message": "Chapter deleted successfully"}
