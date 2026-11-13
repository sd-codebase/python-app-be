from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.database import get_database
from app.models.topic import Topic
from app.models.response import APIResponse

router = APIRouter(prefix="/topics", tags=["topics"])


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
