from fastapi import APIRouter, HTTPException, Request

from app.database import get_database
from app.models.question import Question
from app.models.response import APIResponse
from app.utils.rate_limiter import limiter

router = APIRouter(prefix="/public/questions", tags=["public"])


@router.get("/{question_id}", response_model=APIResponse[Question])
@limiter.limit("500/minute")
async def get_question_public(request: Request, question_id: str):
    """
    Fetch a question by ID without authentication (public endpoint).

    This endpoint is rate-limited to 500 requests per minute per IP to prevent abuse.
    """
    db = get_database()
    question = await db.questions.find_one({"id": question_id})
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return {"data": question, "message": "Question retrieved successfully"}
