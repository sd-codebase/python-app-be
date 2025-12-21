from datetime import datetime
from uuid import uuid4
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status

from app.database import get_database
from app.models.response import APIResponse
from app.models.predefined_test import (
    PredefinedTestStatus,
    PredefinedTestUserResponse,
    PredefinedTestMetadataResponse,
    QuestionForAttempt,
    PredefinedTestAttemptResponse,
    SubmitAttemptRequest,
    SubmitAttemptResponse,
    AttemptQuestionResult,
    UserAttemptHistoryResponse,
)
from app.dependencies import get_current_active_user

router = APIRouter(prefix="/predefined-tests", tags=["predefined-tests"])


@router.get("", response_model=APIResponse[List[PredefinedTestUserResponse]])
async def get_available_tests(
    test_type: Optional[str] = None,
    reference_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    current_user: dict = Depends(get_current_active_user)
):
    """Get all published predefined tests available to the user."""
    db = get_database()

    query = {"status": PredefinedTestStatus.PUBLISHED.value}
    if test_type:
        query["test_type"] = test_type
    if reference_id:
        query["reference_id"] = reference_id

    cursor = db.predefined_tests.find(
        query,
        {"questions": 0}
    ).sort("created_at", -1).skip(skip).limit(limit)

    tests = await cursor.to_list(length=limit)

    # Get user's attempt info for each test
    result = []
    for t in tests:
        # Get user's attempts for this test
        attempts = await db.predefined_test_attempts.find(
            {"test_id": t["id"], "user_id": current_user["id"], "is_submitted": True}
        ).to_list(length=None)

        has_attempted = len(attempts) > 0
        best_score = None
        if attempts:
            best_score = max(a.get("score", 0) for a in attempts)

        result.append({
            "id": t["id"],
            "name": t.get("name", t["set_test_name"]),
            "test_type": t["test_type"],
            "reference_id": t["reference_id"],
            "reference_name": t["reference_name"],
            "time_limit_minutes": t["time_limit_minutes"],
            "total_questions": t["total_questions"],
            "has_attempted": has_attempted,
            "best_score": best_score,
            "attempt_count": len(attempts),
        })

    return {
        "data": result,
        "message": "Available tests retrieved successfully"
    }


@router.get("/by-reference/{test_type}/{reference_id}", response_model=APIResponse[List[PredefinedTestUserResponse]])
async def get_tests_by_reference(
    test_type: str,
    reference_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Get all published predefined tests for a specific topic/chapter/subject/course."""
    db = get_database()

    query = {
        "status": PredefinedTestStatus.PUBLISHED.value,
        "test_type": test_type,
        "reference_id": reference_id,
    }

    cursor = db.predefined_tests.find(query, {"questions": 0}).sort("created_at", -1)
    tests = await cursor.to_list(length=None)

    result = []
    for t in tests:
        attempts = await db.predefined_test_attempts.find(
            {"test_id": t["id"], "user_id": current_user["id"], "is_submitted": True}
        ).to_list(length=None)

        has_attempted = len(attempts) > 0
        best_score = None
        if attempts:
            best_score = max(a.get("score", 0) for a in attempts)

        result.append({
            "id": t["id"],
            "name": t.get("name", t["set_test_name"]),
            "test_type": t["test_type"],
            "reference_id": t["reference_id"],
            "reference_name": t["reference_name"],
            "time_limit_minutes": t["time_limit_minutes"],
            "total_questions": t["total_questions"],
            "has_attempted": has_attempted,
            "best_score": best_score,
            "attempt_count": len(attempts),
        })

    return {
        "data": result,
        "message": "Tests for reference retrieved successfully"
    }


@router.get("/{test_id}", response_model=APIResponse[PredefinedTestMetadataResponse])
async def get_predefined_test(
    test_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Get predefined test metadata by ID (lightweight response without question details)."""
    db = get_database()

    # Fetch the predefined test
    test = await db.predefined_tests.find_one({"id": test_id})

    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test with ID '{test_id}' does not exist"
        )

    # Only return published tests to regular users
    if test["status"] != PredefinedTestStatus.PUBLISHED.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This test is not available"
        )

    # Prepare minimal question data (just IDs and has_integer_answer)
    minimal_questions = [
        {
            "question_id": q["question_id"],
            "has_integer_answer": q.get("has_integer_answer", False)
        }
        for q in test.get("questions", [])
    ]

    # Return metadata with minimal question data
    return {
        "data": {
            "id": test["id"],
            "name": test.get("name", test["set_test_name"]),
            "test_type": test["test_type"],
            "reference_id": test["reference_id"],
            "reference_name": test["reference_name"],
            "time_limit_minutes": test["time_limit_minutes"],
            "total_questions": test["total_questions"],
            "questions": minimal_questions,
        },
        "message": "Test metadata retrieved successfully"
    }


@router.post("/{test_id}/start", response_model=APIResponse[PredefinedTestAttemptResponse], status_code=201)
async def start_test_attempt(
    test_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Start a new attempt for a predefined test."""
    db = get_database()

    # Get the predefined test
    test = await db.predefined_tests.find_one({"id": test_id})

    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test not found"
        )

    if test["status"] != PredefinedTestStatus.PUBLISHED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Test is not available"
        )

    # Check if user has an ongoing attempt
    ongoing_attempt = await db.predefined_test_attempts.find_one({
        "test_id": test_id,
        "user_id": current_user["id"],
        "is_submitted": False,
    })

    if ongoing_attempt:
        # Fetch full question details from questions collection
        question_ids = [q["question_id"] for q in ongoing_attempt["questions"]]
        questions_cursor = db.questions.find({"id": {"$in": question_ids}})
        questions_data = await questions_cursor.to_list(length=None)
        questions_map = {q["id"]: q for q in questions_data}

        questions = []
        for q in ongoing_attempt["questions"]:
            full_q = questions_map.get(q["question_id"], {})
            questions.append(QuestionForAttempt(
                question_id=q["question_id"],
                question=full_q.get("question", ""),
                options=full_q.get("options"),
                has_integer_answer=q.get("has_integer_answer", False),
                user_answer=q.get("user_answer")
            ).model_dump())

        return {
            "data": {
                "attempt_id": ongoing_attempt["id"],
                "test_id": test_id,
                "test_name": test.get("name", test["set_test_name"]),
                "test_type": test["test_type"],
                "reference_name": test["reference_name"],
                "time_limit_minutes": test["time_limit_minutes"],
                "total_questions": test["total_questions"],
                "questions": questions,
                "started_at": ongoing_attempt["started_at"],
            },
            "message": "Resuming existing attempt"
        }

    # Create new attempt
    attempt_id = str(uuid4())
    now = datetime.utcnow()

    # Copy minimal question data for the attempt
    attempt_questions = [
        {
            "question_id": q["question_id"],
            "has_integer_answer": q.get("has_integer_answer", False),
            "correct_answer": q["answer"],
            "user_answer": None,
        }
        for q in test["questions"]
    ]

    attempt_doc = {
        "id": attempt_id,
        "test_id": test_id,
        "user_id": current_user["id"],
        "test_name": test["set_test_name"],
        "test_type": test["test_type"],
        "reference_name": test["reference_name"],
        "time_limit_minutes": test["time_limit_minutes"],
        "total_questions": test["total_questions"],
        "marks_per_question": test.get("marks_per_question", 4.0),
        "negative_marks": test.get("negative_marks", 1.0),
        "questions": attempt_questions,
        "score": None,
        "max_score": None,
        "percentage": None,
        "is_submitted": False,
        "started_at": now,
        "submitted_at": None,
    }

    await db.predefined_test_attempts.insert_one(attempt_doc)

    # Fetch full question details from questions collection
    question_ids = [q["question_id"] for q in attempt_questions]
    questions_cursor = db.questions.find({"id": {"$in": question_ids}})
    questions_data = await questions_cursor.to_list(length=None)
    questions_map = {q["id"]: q for q in questions_data}

    # Prepare questions for response (without correct answers)
    questions = []
    for q in attempt_questions:
        full_q = questions_map.get(q["question_id"], {})
        questions.append(QuestionForAttempt(
            question_id=q["question_id"],
            question=full_q.get("question", ""),
            options=full_q.get("options"),
            has_integer_answer=q.get("has_integer_answer", False),
            user_answer=None
        ).model_dump())

    return {
        "data": {
            "attempt_id": attempt_id,
            "test_id": test_id,
            "test_name": test.get("name", test["set_test_name"]),
            "test_type": test["test_type"],
            "reference_name": test["reference_name"],
            "time_limit_minutes": test["time_limit_minutes"],
            "total_questions": test["total_questions"],
            "questions": questions,
            "started_at": now,
        },
        "message": "Test attempt started successfully"
    }


@router.get("/attempts/{attempt_id}", response_model=APIResponse[PredefinedTestAttemptResponse])
async def get_attempt(
    attempt_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Get an ongoing attempt."""
    db = get_database()

    attempt = await db.predefined_test_attempts.find_one({
        "id": attempt_id,
        "user_id": current_user["id"],
    })

    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attempt not found"
        )

    if attempt["is_submitted"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This attempt has already been submitted"
        )

    # Fetch full question details from questions collection
    question_ids = [q["question_id"] for q in attempt["questions"]]
    questions_cursor = db.questions.find({"id": {"$in": question_ids}})
    questions_data = await questions_cursor.to_list(length=None)
    questions_map = {q["id"]: q for q in questions_data}

    questions = []
    for q in attempt["questions"]:
        full_q = questions_map.get(q["question_id"], {})
        questions.append(QuestionForAttempt(
            question_id=q["question_id"],
            question=full_q.get("question", ""),
            options=full_q.get("options"),
            has_integer_answer=q.get("has_integer_answer", False),
            user_answer=q.get("user_answer")
        ).model_dump())

    return {
        "data": {
            "attempt_id": attempt["id"],
            "test_id": attempt["test_id"],
            "test_name": attempt["test_name"],
            "test_type": attempt["test_type"],
            "reference_name": attempt["reference_name"],
            "time_limit_minutes": attempt["time_limit_minutes"],
            "total_questions": attempt["total_questions"],
            "questions": questions,
            "started_at": attempt["started_at"],
        },
        "message": "Attempt retrieved successfully"
    }


@router.put("/attempts/{attempt_id}/save", response_model=APIResponse[None])
async def save_attempt_progress(
    attempt_id: str,
    request: SubmitAttemptRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """Save progress for an ongoing attempt (auto-save)."""
    db = get_database()

    attempt = await db.predefined_test_attempts.find_one({
        "id": attempt_id,
        "user_id": current_user["id"],
    })

    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attempt not found"
        )

    if attempt["is_submitted"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot save a submitted attempt"
        )

    # Update user answers
    user_answers_map = {a.question_id: a.user_answer for a in request.answers}

    updated_questions = []
    for q in attempt["questions"]:
        q["user_answer"] = user_answers_map.get(q["question_id"], q.get("user_answer"))
        updated_questions.append(q)

    await db.predefined_test_attempts.update_one(
        {"id": attempt_id},
        {"$set": {"questions": updated_questions}}
    )

    return {
        "data": None,
        "message": "Progress saved successfully"
    }


@router.post("/attempts/{attempt_id}/submit", response_model=APIResponse[SubmitAttemptResponse])
async def submit_attempt(
    attempt_id: str,
    request: SubmitAttemptRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """Submit a test attempt and calculate score."""
    db = get_database()

    attempt = await db.predefined_test_attempts.find_one({
        "id": attempt_id,
        "user_id": current_user["id"],
    })

    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attempt not found"
        )

    if attempt["is_submitted"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This attempt has already been submitted"
        )

    # Get scoring configuration
    marks_per_question = attempt.get("marks_per_question", 4.0)
    negative_marks = attempt.get("negative_marks", 1.0)

    # Create a map of user answers
    user_answers_map = {a.question_id: a.user_answer for a in request.answers}

    # Calculate results
    results = []
    correct_count = 0
    wrong_count = 0

    for q in attempt["questions"]:
        user_answer = user_answers_map.get(q["question_id"], q.get("user_answer"))
        correct_answer = q["correct_answer"]
        is_correct = user_answer is not None and user_answer == correct_answer

        if is_correct:
            correct_count += 1
        elif user_answer is not None and user_answer != "":
            wrong_count += 1

        results.append(AttemptQuestionResult(
            question_id=q["question_id"],
            user_answer=user_answer,
            correct_answer=correct_answer,
            is_correct=is_correct
        ).model_dump())

    total = attempt["total_questions"]
    unanswered = total - correct_count - wrong_count

    # Calculate score with negative marking
    score = (correct_count * marks_per_question) - (wrong_count * negative_marks)
    max_score = total * marks_per_question
    percentage = (score / max_score) * 100 if max_score > 0 else 0

    # Update attempt with final answers and score
    updated_questions = []
    for q in attempt["questions"]:
        q["user_answer"] = user_answers_map.get(q["question_id"], q.get("user_answer"))
        updated_questions.append(q)

    now = datetime.utcnow()
    await db.predefined_test_attempts.update_one(
        {"id": attempt_id},
        {
            "$set": {
                "questions": updated_questions,
                "score": score,
                "max_score": max_score,
                "percentage": round(percentage, 2),
                "correct_count": correct_count,
                "wrong_count": wrong_count,
                "unanswered": unanswered,
                "is_submitted": True,
                "submitted_at": now,
            }
        }
    )

    # Fetch the predefined test details for reference info
    test = await db.predefined_tests.find_one({"id": attempt["test_id"]})

    # Create unified attempt record
    unified_attempt_id = str(uuid4())
    unified_attempt_doc = {
        "id": unified_attempt_id,
        "user_id": current_user["id"],
        "test_id": attempt["test_id"],
        "predefined_attempt_id": attempt_id,  # Link to original attempt
        "test_source": "predefined",  # Distinguish from user-generated tests
        "test_name": attempt["test_name"],
        "test_type": attempt["test_type"],
        "reference_id": test.get("reference_id") if test else None,
        "reference_name": attempt["reference_name"],
        "set_test_id": test.get("set_test_id") if test else None,
        "set_test_name": test.get("set_test_name") if test else None,
        "total_questions": total,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "unanswered": unanswered,
        "score": score,
        "max_score": max_score,
        "percentage": round(percentage, 2),
        "marks_per_question": marks_per_question,
        "negative_marks": negative_marks,
        "negative_marking_applied": negative_marks > 0,
        "time_limit_minutes": attempt["time_limit_minutes"],
        "started_at": attempt["started_at"],
        "submitted_at": now,
        "questions": updated_questions,  # Store questions with user answers
    }

    await db.test_attempts.insert_one(unified_attempt_doc)

    return {
        "data": {
            "attempt_id": attempt_id,
            "test_id": attempt["test_id"],
            "total_questions": total,
            "correct_count": correct_count,
            "wrong_count": wrong_count,
            "unanswered": unanswered,
            "score": score,
            "max_score": max_score,
            "percentage": round(percentage, 2),
            "negative_marking_applied": negative_marks > 0,
            "results": results,
        },
        "message": "Test submitted successfully"
    }


@router.get("/history", response_model=APIResponse[List[UserAttemptHistoryResponse]])
async def get_attempt_history(
    test_type: Optional[str] = None,
    test_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    current_user: dict = Depends(get_current_active_user)
):
    """Get user's attempt history for predefined tests."""
    db = get_database()

    query = {
        "user_id": current_user["id"],
        "is_submitted": True,
    }
    if test_type:
        query["test_type"] = test_type
    if test_id:
        query["test_id"] = test_id

    cursor = db.predefined_test_attempts.find(
        query,
        {"questions": 0}
    ).sort("submitted_at", -1).skip(skip).limit(limit)

    attempts = await cursor.to_list(length=limit)

    return {
        "data": [
            {
                "attempt_id": a["id"],
                "test_id": a["test_id"],
                "test_name": a["test_name"],
                "test_type": a["test_type"],
                "reference_name": a["reference_name"],
                "total_questions": a["total_questions"],
                "score": a["score"],
                "max_score": a["max_score"],
                "percentage": a["percentage"],
                "started_at": a["started_at"],
                "submitted_at": a["submitted_at"],
            }
            for a in attempts
        ],
        "message": "Attempt history retrieved successfully"
    }


@router.get("/history/{attempt_id}/review", response_model=APIResponse[SubmitAttemptResponse])
async def review_attempt(
    attempt_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Review a submitted attempt with correct answers."""
    db = get_database()

    attempt = await db.predefined_test_attempts.find_one({
        "id": attempt_id,
        "user_id": current_user["id"],
        "is_submitted": True,
    })

    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submitted attempt not found"
        )

    results = [
        AttemptQuestionResult(
            question_id=q["question_id"],
            user_answer=q.get("user_answer"),
            correct_answer=q["correct_answer"],
            is_correct=q.get("user_answer") is not None and q.get("user_answer") == q["correct_answer"]
        ).model_dump()
        for q in attempt["questions"]
    ]

    return {
        "data": {
            "attempt_id": attempt["id"],
            "test_id": attempt["test_id"],
            "total_questions": attempt["total_questions"],
            "correct_count": attempt.get("correct_count", 0),
            "wrong_count": attempt.get("wrong_count", 0),
            "unanswered": attempt.get("unanswered", 0),
            "score": attempt["score"],
            "max_score": attempt["max_score"],
            "percentage": attempt["percentage"],
            "negative_marking_applied": attempt.get("negative_marks", 1.0) > 0,
            "results": results,
        },
        "message": "Attempt review retrieved successfully"
    }
