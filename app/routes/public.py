import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.database import get_database
from app.models.question import PublicQuestion, PublicSolution
from app.models.response import APIResponse
from app.utils.rate_limiter import limiter

router = APIRouter(prefix="/public/questions", tags=["public"])
solutions_router = APIRouter(prefix="/public/solutions", tags=["public"])

_VALID_ID = re.compile(r'^[a-zA-Z0-9_-]+$')


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


@solutions_router.get("/{solution_id}", response_model=APIResponse[PublicSolution])
@limiter.limit("500/minute")
async def get_solution_public(request: Request, solution_id: str):
    if not _VALID_ID.match(solution_id):
        return JSONResponse(status_code=400, content={"error": "Invalid solution ID"})

    db = get_database()
    question = await db.questions.find_one({"id": solution_id})
    if not question:
        return JSONResponse(status_code=404, content={"error": "Solution not found"})

    solutions = question.get("solutions") or []
    solution_text = solutions[0] if solutions else None
    if not solution_text:
        return JSONResponse(status_code=404, content={"error": "Solution not found"})

    return {"data": {"solution": solution_text}, "message": "Success"}
