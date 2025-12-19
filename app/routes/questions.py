from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from uuid import uuid4

from app.database import get_database
from app.models.question import Question, QuestionCreate, QuestionUpdate
from app.models.response import APIResponse

router = APIRouter(prefix="/questions", tags=["questions"])


@router.post("/", response_model=APIResponse[Question], status_code=201)
async def create_question(question: QuestionCreate):
    db = get_database()
    now = datetime.utcnow()

    question_dict = question.model_dump()
    question_dict["id"] = str(uuid4())
    question_dict["created_at"] = now
    question_dict["updated_at"] = now

    # Validate topic_id if provided
    if question_dict.get("topic_id"):
        topic = await db.topics.find_one({"id": question_dict["topic_id"]})
        if not topic:
            raise HTTPException(status_code=400, detail="Topic not found")

    # Check unique constraint on question + answer
    existing_qa = await db.questions.find_one({
        "question": question_dict["question"],
        "answer": question_dict["answer"]
    })
    if existing_qa:
        raise HTTPException(
            status_code=400,
            detail="Question with this question-answer combination already exists"
        )

    await db.questions.insert_one(question_dict)
    return {"data": question_dict, "message": "Question created successfully"}


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


@router.put("/{question_id}", response_model=APIResponse[Question])
async def update_question(question_id: str, question_update: QuestionUpdate):
    db = get_database()

    update_data = question_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Validate topic_id if being updated
    if "topic_id" in update_data and update_data["topic_id"]:
        topic = await db.topics.find_one({"id": update_data["topic_id"]})
        if not topic:
            raise HTTPException(status_code=400, detail="Topic not found")

    # Check unique constraint if question or answer is being updated
    if "question" in update_data or "answer" in update_data:
        current = await db.questions.find_one({"id": question_id})
        if not current:
            raise HTTPException(status_code=404, detail="Question not found")

        new_question = update_data.get("question", current["question"])
        new_answer = update_data.get("answer", current["answer"])

        existing = await db.questions.find_one({
            "question": new_question,
            "answer": new_answer,
            "id": {"$ne": question_id}
        })
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Question with this question-answer combination already exists"
            )

    update_data["updated_at"] = datetime.utcnow()

    result = await db.questions.update_one(
        {"id": question_id},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Question not found")

    question = await db.questions.find_one({"id": question_id})
    return {"data": question, "message": "Question updated successfully"}


@router.delete("/{question_id}", response_model=APIResponse)
async def delete_question(question_id: str):
    db = get_database()
    result = await db.questions.delete_one({"id": question_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Question not found")
    return {"data": None, "message": "Question deleted successfully"}
