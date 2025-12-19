from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from uuid import uuid4

from app.database import get_database
from app.models.topic import Topic, TopicCreate, TopicUpdate
from app.models.response import APIResponse

router = APIRouter(prefix="/topics", tags=["topics"])


@router.post("/", response_model=APIResponse[Topic], status_code=201)
async def create_topic(topic: TopicCreate):
    db = get_database()
    now = datetime.utcnow()

    topic_dict = topic.model_dump()
    topic_dict["id"] = str(uuid4())
    topic_dict["created_at"] = now
    topic_dict["updated_at"] = now

    # Validate chapter_id if provided
    if topic_dict.get("chapter_id"):
        chapter = await db.chapters.find_one({"id": topic_dict["chapter_id"]})
        if not chapter:
            raise HTTPException(status_code=400, detail="Chapter not found")

    # Check unique constraint on order_num + chapter_id
    existing_order = await db.topics.find_one({
        "order_num": topic_dict["order_num"],
        "chapter_id": topic_dict.get("chapter_id")
    })
    if existing_order:
        raise HTTPException(
            status_code=400,
            detail="Topic with this order_num already exists for this chapter"
        )

    await db.topics.insert_one(topic_dict)
    return {"data": topic_dict, "message": "Topic created successfully"}


@router.get("/", response_model=APIResponse[List[Topic]])
async def get_topics(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    chapter_id: Optional[str] = None,
    is_active: Optional[bool] = None,
):
    db = get_database()
    query = {}
    if chapter_id:
        query["chapter_id"] = chapter_id
    if is_active is not None:
        query["is_active"] = is_active

    cursor = db.topics.find(query).sort("order_num", 1).skip(skip).limit(limit)
    topics = await cursor.to_list(length=limit)
    return {"data": topics, "message": "Topics retrieved successfully"}


@router.get("/{topic_id}", response_model=APIResponse[Topic])
async def get_topic(topic_id: str):
    db = get_database()
    topic = await db.topics.find_one({"id": topic_id})
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return {"data": topic, "message": "Topic retrieved successfully"}


@router.put("/{topic_id}", response_model=APIResponse[Topic])
async def update_topic(topic_id: str, topic_update: TopicUpdate):
    db = get_database()

    update_data = topic_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Validate chapter_id if being updated
    if "chapter_id" in update_data and update_data["chapter_id"]:
        chapter = await db.chapters.find_one({"id": update_data["chapter_id"]})
        if not chapter:
            raise HTTPException(status_code=400, detail="Chapter not found")

    # Check unique constraint if order_num or chapter_id is being updated
    if "order_num" in update_data or "chapter_id" in update_data:
        current = await db.topics.find_one({"id": topic_id})
        if not current:
            raise HTTPException(status_code=404, detail="Topic not found")

        new_order = update_data.get("order_num", current["order_num"])
        new_chapter = update_data.get("chapter_id", current.get("chapter_id"))

        existing = await db.topics.find_one({
            "order_num": new_order,
            "chapter_id": new_chapter,
            "id": {"$ne": topic_id}
        })
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Topic with this order_num already exists for this chapter"
            )

    update_data["updated_at"] = datetime.utcnow()

    result = await db.topics.update_one(
        {"id": topic_id},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Topic not found")

    topic = await db.topics.find_one({"id": topic_id})
    return {"data": topic, "message": "Topic updated successfully"}


@router.delete("/{topic_id}", response_model=APIResponse)
async def delete_topic(topic_id: str):
    db = get_database()
    result = await db.topics.delete_one({"id": topic_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Topic not found")
    return {"data": None, "message": "Topic deleted successfully"}
