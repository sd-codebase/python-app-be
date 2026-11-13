from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.database import get_database
from app.models.question import Question
from app.models.response import APIResponse

router = APIRouter(prefix="/questions", tags=["questions"])


@router.get("/", response_model=APIResponse[List[Question]])
async def get_questions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    topic_id: Optional[str] = None,
    level: Optional[int] = None,
    is_active: Optional[bool] = None,
    is_marked_for_review: Optional[bool] = None,
    verified_in_app: Optional[bool] = None,
):
    db = get_database()
    query = {}
    if topic_id:
        query["topic_id"] = topic_id
    if level is not None:
        query["level"] = level
    if is_active is not None:
        query["is_active"] = is_active
    if is_marked_for_review is not None:
        query["is_marked_for_review"] = is_marked_for_review
    if verified_in_app is not None:
        query["verified_in_app"] = verified_in_app

    cursor = db.questions.find(query).skip(skip).limit(limit)
    questions = await cursor.to_list(length=limit)
    return {"data": questions, "message": "Questions retrieved successfully"}


@router.get("/{question_id}", response_model=APIResponse[Question])
async def get_question(question_id: str):
    db = get_database()
    question = await db.questions.find_one({"id": question_id})
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return {"data": question, "message": "Question retrieved successfully"}
