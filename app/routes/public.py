from fastapi import APIRouter, HTTPException, Request

from app.database import get_database
from app.models.question import PublicQuestion
from app.models.response import APIResponse
from app.utils.rate_limiter import limiter

router = APIRouter(prefix="/public/questions", tags=["public"])


@router.get("/{question_id}", response_model=APIResponse[PublicQuestion])
@limiter.limit("500/minute")
async def get_question_public(request: Request, question_id: str):
    """
    Fetch a question by ID without authentication (public endpoint).

    This endpoint is rate-limited to 500 requests per minute per IP to prevent abuse.
    Returns limited fields: id, question, options, has_integer_answer, resources_directory, level, pyo.
    """
    db = get_database()
    question = await db.questions.find_one({"id": question_id})
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # Get resources_directory from topics collection
    resources_directory = None
    if question.get("topic_id"):
        topic = await db.topics.find_one({"id": question["topic_id"]})
        if topic:
            resources_directory = topic.get("resources_directory")

    # Build public response with only required fields
    public_question = {
        "id": question["id"],
        "question": question["question"],
        "options": question.get("options") or {},  # Ensure it's always a dict, never None
        "has_integer_answer": question.get("has_integer_answer") or False,
        "resources_directory": resources_directory,
        "level": question.get("level") or 0,
        "pyo": question.get("pyo"),
    }

    return {"data": public_question, "message": "Question retrieved successfully"}
