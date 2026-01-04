from datetime import datetime
from uuid import uuid4
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status

from app.database import get_database
from app.models.response import APIResponse
from app.models.test_attempt import (
    TestSource,
    SubmitTestRequest,
    SubmitTestResponse,
    QuestionResult,
    AttemptHistoryResponse,
    AttemptDetailResponse,
)
from app.dependencies import get_current_active_user

router = APIRouter(prefix="/tests", tags=["test-attempts"])


async def find_test(test_id: str):
    """Find test in either generated_tests or predefined_tests collection."""
    db = get_database()

    # Try generated_tests first
    test = await db.generated_tests.find_one({"id": test_id})
    if test:
        return test, TestSource.GENERATED

    # Try predefined_tests
    test = await db.predefined_tests.find_one({"id": test_id})
    if test:
        return test, TestSource.PREDEFINED

    return None, None


@router.post("/submit", response_model=APIResponse[SubmitTestResponse])
async def submit_test(
    request: SubmitTestRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Unified API to submit a test (works for both user-generated and predefined tests).
    Takes test_id, test_source, and answers in request body.
    Creates an attempt record in test_attempts collection.
    """
    db = get_database()

    test_id = request.test_id
    test_source = request.test_source

    # Fetch test based on test_source
    if test_source == TestSource.USER_GENERATED:
        test = await db.generated_tests.find_one({"id": test_id})
        if not test:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User-generated test not found"
            )
        # Check ownership
        if test.get("user_id") != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this test"
            )
        # Check if generation is complete
        if test.get("generation_status") != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Test generation is not complete"
            )

    elif test_source == TestSource.PREDEFINED:
        test = await db.predefined_tests.find_one({"id": test_id})
        if not test:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Predefined test not found"
            )
        # Check if published
        if test.get("status") != "published":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Test is not available"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid test_source"
        )

    # Create user answers map
    user_answers_map = {a.question_id: a.user_answer for a in request.answers}

    # Calculate results with per-question scoring
    results = []
    correct_count = 0
    wrong_count = 0
    score = 0.0
    max_score = 0.0

    for q in test["questions"]:
        question_id = q["question_id"]
        has_integer_answer = q.get("has_integer_answer", False)
        correct_answer = q["answer"]
        user_answer = user_answers_map.get(question_id)

        # Get per-question scoring (fallback to test-level or defaults)
        q_marks = q.get("marks_per_question", test.get("marks_per_question", 4.0))
        q_negative = q.get("negative_marks", test.get("negative_marks", 0.0))

        max_score += q_marks

        is_correct = user_answer is not None and user_answer == correct_answer

        if is_correct:
            correct_count += 1
            score += q_marks
        elif user_answer is not None and user_answer != "":
            wrong_count += 1
            score -= q_negative

        results.append({
            "question_id": question_id,
            "has_integer_answer": has_integer_answer,
            "correct_answer": correct_answer,
            "user_answer": user_answer,
            "is_correct": is_correct,
        })

    total = test["total_questions"]
    unanswered = total - correct_count - wrong_count
    percentage = (score / max_score) * 100 if max_score > 0 else 0

    # Get representative marks for storing (use first question's marks or test-level)
    marks_per_question = test["questions"][0].get("marks_per_question", test.get("marks_per_question", 4.0)) if test["questions"] else 4.0
    negative_marks = test["questions"][0].get("negative_marks", test.get("negative_marks", 0.0)) if test["questions"] else 0.0

    # Create attempt record
    attempt_id = str(uuid4())
    now = datetime.utcnow()

    attempt_doc = {
        "id": attempt_id,
        "user_id": current_user["id"],
        "test_source": test_source.value,
        "test_id": test_id,
        "test_name": test.get("name", test.get("set_test_name", "")),
        "test_type": test.get("test_type", ""),
        "reference_id": test.get("reference_id", ""),
        "reference_name": test.get("reference_name", ""),
        "set_test_id": test.get("set_test_id", ""),
        "set_test_name": test.get("set_test_name", ""),
        "time_limit_minutes": test.get("time_limit_minutes", 0),
        "total_questions": total,
        "marks_per_question": marks_per_question,
        "negative_marks": negative_marks,
        "questions": results,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "unanswered": unanswered,
        "score": score,
        "max_score": max_score,
        "percentage": round(percentage, 2),
        "time_taken_seconds": request.time_taken_seconds,
        "started_at": now,  # Using submission time as started time
        "submitted_at": now,
    }

    await db.test_attempts.insert_one(attempt_doc)

    # Update is_submitted in the original test document
    if test_source == TestSource.USER_GENERATED:
        await db.generated_tests.update_one(
            {"id": test_id},
            {"$set": {"is_submitted": True, "submitted_at": now, "score": score}}
        )

    return {
        "data": {
            "attempt_id": attempt_id,
            "test_id": test_id,
            "test_name": attempt_doc["test_name"],
            "test_source": test_source.value,
            "total_questions": total,
            "correct_count": correct_count,
            "wrong_count": wrong_count,
            "unanswered": unanswered,
            "score": score,
            "max_score": max_score,
            "percentage": round(percentage, 2),
            "negative_marking_applied": negative_marks > 0,
            "time_taken_seconds": request.time_taken_seconds,
            "results": [QuestionResult(**r).model_dump() for r in results],
            "submitted_at": now,
        },
        "message": "Test submitted successfully"
    }


@router.get("/attempts/history", response_model=APIResponse[List[AttemptHistoryResponse]])
async def get_attempt_history(
    test_source: Optional[TestSource] = None,
    test_type: Optional[str] = None,
    test_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    current_user: dict = Depends(get_current_active_user)
):
    """Get user's test attempt history."""
    db = get_database()

    query = {"user_id": current_user["id"]}

    if test_source:
        query["test_source"] = test_source.value
    if test_type:
        query["test_type"] = test_type
    if test_id:
        query["test_id"] = test_id

    cursor = db.test_attempts.find(
        query,
        {"questions": 0}  # Exclude questions array for list view
    ).sort("submitted_at", -1).skip(skip).limit(limit)

    attempts = await cursor.to_list(length=limit)

    return {
        "data": [
            {
                "attempt_id": a["id"],
                "test_id": a["test_id"],
                "test_name": a["test_name"],
                "test_source": a["test_source"],
                "test_type": a["test_type"],
                "reference_name": a["reference_name"],
                "total_questions": a["total_questions"],
                "correct_count": a["correct_count"],
                "wrong_count": a["wrong_count"],
                "unanswered": a["unanswered"],
                "score": a["score"],
                "max_score": a["max_score"],
                "percentage": a["percentage"],
                "submitted_at": a["submitted_at"],
            }
            for a in attempts
        ],
        "message": "Attempt history retrieved successfully"
    }


@router.get("/attempts/{attempt_id}", response_model=APIResponse[AttemptDetailResponse])
async def get_attempt_detail(
    attempt_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Get detailed results of a specific attempt."""
    db = get_database()

    # First check if attempt exists at all
    attempt_exists = await db.test_attempts.find_one({"id": attempt_id})

    if not attempt_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attempt with ID '{attempt_id}' does not exist"
        )

    # Then check if it belongs to current user
    attempt = await db.test_attempts.find_one({
        "id": attempt_id,
        "user_id": current_user["id"],
    })

    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this attempt"
        )

    return {
        "data": {
            "attempt_id": attempt["id"],
            "test_id": attempt["test_id"],
            "test_name": attempt["test_name"],
            "test_source": attempt["test_source"],
            "test_type": attempt["test_type"],
            "reference_name": attempt["reference_name"],
            "total_questions": attempt["total_questions"],
            "correct_count": attempt["correct_count"],
            "wrong_count": attempt["wrong_count"],
            "unanswered": attempt["unanswered"],
            "score": attempt["score"],
            "max_score": attempt["max_score"],
            "percentage": attempt["percentage"],
            "negative_marking_applied": attempt.get("negative_marks", 1.0) > 0,
            "time_taken_seconds": attempt.get("time_taken_seconds"),
            "results": [QuestionResult(**q).model_dump() for q in attempt["questions"]],
            "submitted_at": attempt["submitted_at"],
        },
        "message": "Attempt details retrieved successfully"
    }


@router.get("/attempts/by-test/{test_id}", response_model=APIResponse[List[AttemptHistoryResponse]])
async def get_attempts_for_test(
    test_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Get all attempts by the user for a specific test."""
    db = get_database()

    cursor = db.test_attempts.find(
        {"test_id": test_id, "user_id": current_user["id"]},
        {"questions": 0}
    ).sort("submitted_at", -1)

    attempts = await cursor.to_list(length=None)

    return {
        "data": [
            {
                "attempt_id": a["id"],
                "test_id": a["test_id"],
                "test_name": a["test_name"],
                "test_source": a["test_source"],
                "test_type": a["test_type"],
                "reference_name": a["reference_name"],
                "total_questions": a["total_questions"],
                "correct_count": a["correct_count"],
                "wrong_count": a["wrong_count"],
                "unanswered": a["unanswered"],
                "score": a["score"],
                "max_score": a["max_score"],
                "percentage": a["percentage"],
                "submitted_at": a["submitted_at"],
            }
            for a in attempts
        ],
        "message": "Attempts for test retrieved successfully"
    }
