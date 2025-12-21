import random
import asyncio
from datetime import datetime
from uuid import uuid4
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks, Query

from app.database import get_database
from app.models.response import APIResponse
from app.models.test import (
    TestType,
    GenerationStatus,
    GenerateTestRequest,
    SubmitTestRequest,
    TestQuestion,
    TestGenerationResponse,
    TestMetadataResponse,
    TestDetailResponse,
    QuestionForTaking,
    SubmitTestResponse,
    QuestionResult,
)
from app.dependencies import get_current_active_user

router = APIRouter(prefix="/user-tests", tags=["user-generated-tests"])


# Helper functions to get questions
async def get_questions_for_topic(topic_id: str) -> List[dict]:
    """Get active questions for a topic using direct query."""
    db = get_database()
    # Match where is_active is not explicitly False (includes True, None, missing)
    cursor = db.questions.find({"topic_id": topic_id, "is_active": {"$ne": False}})
    return await cursor.to_list(length=None)


async def get_questions_for_chapter(chapter_id: str) -> List[dict]:
    """Get active questions for a chapter using direct chapter_id field."""
    db = get_database()
    cursor = db.questions.find({"chapter_id": chapter_id, "is_active": {"$ne": False}})
    return await cursor.to_list(length=None)


async def get_questions_for_subject(subject_id: str) -> List[dict]:
    """Get active questions for a subject using direct subject_id field."""
    db = get_database()
    cursor = db.questions.find({"subject_id": subject_id, "is_active": {"$ne": False}})
    return await cursor.to_list(length=None)


async def get_questions_for_course(course_id: str) -> List[dict]:
    """Get active questions for a course using direct course_id field."""
    db = get_database()
    cursor = db.questions.find({"course_id": course_id, "is_active": {"$ne": False}})
    return await cursor.to_list(length=None)


def select_questions_by_difficulty(questions: List[dict], difficulty: dict) -> List[dict]:
    """Select questions based on difficulty distribution.

    Args:
        questions: List of question documents
        difficulty: Dict with L1, L2, L3 counts (e.g., {"L1": 5, "L2": 3, "L3": 2})

    Returns:
        Selected questions matching the difficulty distribution
    """
    selected = []

    # Group questions by difficulty level (level field is integer: 1, 2, 3)
    # Map to L1, L2, L3 keys
    by_level = {"L1": [], "L2": [], "L3": []}
    for q in questions:
        level = q.get("level")
        if level == 1:
            by_level["L1"].append(q)
        elif level == 2:
            by_level["L2"].append(q)
        elif level == 3:
            by_level["L3"].append(q)
        else:
            # Default unknown levels to L1
            by_level["L1"].append(q)

    # Select required number from each level
    for level_key, count in difficulty.items():
        if count > 0 and level_key in by_level:
            available = by_level[level_key]
            if available:
                selected.extend(random.sample(available, min(count, len(available))))

    random.shuffle(selected)
    return selected


def select_questions_for_section(questions: List[dict], section: dict) -> List[dict]:
    """Select questions for a section based on its configuration."""
    difficulty = section.get("difficulty", {})
    is_numerical = section.get("is_numerical", False)

    # Filter by question type if needed
    if is_numerical:
        questions = [q for q in questions if q.get("has_integer_answer", False)]
    else:
        questions = [q for q in questions if not q.get("has_integer_answer", False)]

    if difficulty:
        return select_questions_by_difficulty(questions, difficulty)

    # Fallback to random selection based on question_count
    count = section.get("question_count", 10)
    return random.sample(questions, min(count, len(questions)))


async def get_reference_name(test_type: str, reference_id: str) -> str:
    """Get the name of the referenced entity."""
    db = get_database()

    if test_type == "topic":
        doc = await db.topics.find_one({"id": reference_id})
    elif test_type == "chapter":
        doc = await db.chapters.find_one({"id": reference_id})
    elif test_type == "subject":
        doc = await db.subjects.find_one({"id": reference_id})
    elif test_type == "course":
        doc = await db.courses.find_one({"id": reference_id})
    else:
        return "Unknown"

    return doc["name"] if doc else "Unknown"


async def generate_test_background(test_id: str, set_test: dict, reference_id: str, user_id: str):
    """Background task to generate test questions based on set test format."""
    db = get_database()

    try:
        # Update status to in_progress
        await db.generated_tests.update_one(
            {"id": test_id},
            {"$set": {"generation_status": GenerationStatus.IN_PROGRESS.value}}
        )

        test_type = set_test["test_type"]
        reference_name = await get_reference_name(test_type, reference_id)

        if reference_name == "Unknown":
            raise Exception(f"{test_type.capitalize()} with ID {reference_id} not found")

        test_questions = []

        if test_type == "topic":
            # Simple topic test
            all_questions = await get_questions_for_topic(reference_id)
            if not all_questions:
                raise Exception("No questions available for this topic")

            difficulty = set_test.get("difficulty", {})
            question_count = set_test.get("question_count", 10)

            # Select by difficulty distribution if specified
            if difficulty and any(difficulty.values()):
                selected = select_questions_by_difficulty(all_questions, difficulty)
            else:
                selected = random.sample(all_questions, min(question_count, len(all_questions)))

            for q in selected:
                test_questions.append(TestQuestion(
                    question_id=q["id"],
                    has_integer_answer=q.get("has_integer_answer", False),
                    answer=q["answer"],
                    user_answer=None
                ).model_dump())

        elif test_type == "chapter":
            # Chapter test
            all_questions = await get_questions_for_chapter(reference_id)
            if not all_questions:
                raise Exception("No questions available for this chapter")

            difficulty = set_test.get("difficulty", {})
            question_count = set_test.get("question_count", 20)

            # Select by difficulty distribution if specified
            if difficulty and any(difficulty.values()):
                selected = select_questions_by_difficulty(all_questions, difficulty)
            else:
                selected = random.sample(all_questions, min(question_count, len(all_questions)))

            for q in selected:
                test_questions.append(TestQuestion(
                    question_id=q["id"],
                    has_integer_answer=q.get("has_integer_answer", False),
                    answer=q["answer"],
                    user_answer=None
                ).model_dump())

        elif test_type == "subject":
            # Subject test with sections
            sections = set_test.get("sections", [])
            all_questions = await get_questions_for_subject(reference_id)

            if not all_questions:
                raise Exception("No questions available for this subject")

            for section in sections:
                section_questions = select_questions_for_section(all_questions, section)

                for q in section_questions:
                    test_questions.append(TestQuestion(
                        question_id=q["id"],
                        has_integer_answer=q.get("has_integer_answer", False),
                        answer=q["answer"],
                        user_answer=None
                    ).model_dump())

        elif test_type == "course":
            # First fetch ALL questions for the course
            course_questions = await get_questions_for_course(reference_id)
            if not course_questions:
                raise Exception("No questions available for this course")

            # Get actual subjects for this course to map by name
            subjects_cursor = db.subjects.find({"course_id": reference_id})
            course_subjects = await subjects_cursor.to_list(length=None)
            subject_name_to_id = {s["name"].lower(): s["id"] for s in course_subjects}

            subject_sections = set_test.get("subject_sections", [])

            for subject_section in subject_sections:
                template_subject_id = subject_section.get("subject_id")
                subject_name = subject_section.get("subject_name", "")

                # Determine which questions to use for this subject_section
                section_pool = []

                if template_subject_id == "any" or not template_subject_id:
                    # Use all course questions
                    section_pool = course_questions
                else:
                    # First try direct subject_id match
                    section_pool = [q for q in course_questions if q.get("subject_id") == template_subject_id]

                    # If no match, try matching by subject name
                    if not section_pool and subject_name:
                        actual_subject_id = subject_name_to_id.get(subject_name.lower())
                        if actual_subject_id:
                            section_pool = [q for q in course_questions if q.get("subject_id") == actual_subject_id]

                    # If still no match, fall back to all course questions
                    if not section_pool:
                        section_pool = course_questions

                if not section_pool:
                    continue

                sections = subject_section.get("sections", [])
                for section in sections:
                    section_questions = select_questions_for_section(section_pool, section)

                    for q in section_questions:
                        test_questions.append(TestQuestion(
                            question_id=q["id"],
                            has_integer_answer=q.get("has_integer_answer", False),
                            answer=q["answer"],
                            user_answer=None
                        ).model_dump())

            if not test_questions:
                raise Exception("No questions could be selected for this course test")

        # Auto-generate final name with reference_name
        test_type_labels = {
            "topic": "Topic Test",
            "chapter": "Chapter Quiz",
            "subject": "Subject Test",
            "course": "Full Test",
        }
        final_name = f"{test_type_labels.get(test_type, 'Test')} - {reference_name}"

        # Update test with generated questions
        await db.generated_tests.update_one(
            {"id": test_id},
            {
                "$set": {
                    "name": final_name,
                    "reference_name": reference_name,
                    "questions": test_questions,
                    "total_questions": len(test_questions),
                    "generation_status": GenerationStatus.COMPLETED.value,
                    "generated_at": datetime.utcnow(),
                }
            }
        )

    except Exception as e:
        # Update status to failed with error message
        await db.generated_tests.update_one(
            {"id": test_id},
            {
                "$set": {
                    "generation_status": GenerationStatus.FAILED.value,
                    "error_message": str(e),
                }
            }
        )


@router.post("/generate", response_model=APIResponse[TestGenerationResponse], status_code=202)
async def generate_test(
    request: GenerateTestRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Generate a new test based on set test format.
    Returns immediately with pending status. Poll /tests/{test_id}/status to check progress.
    """
    db = get_database()

    # Fetch the set test format
    set_test = await db.set_tests.find_one({"id": request.set_test_id})
    if not set_test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Set test format not found"
        )

    test_id = str(uuid4())
    now = datetime.utcnow()

    # Auto-generate name based on test type
    test_type_labels = {
        "topic": "Topic Test",
        "chapter": "Chapter Quiz",
        "subject": "Subject Test",
        "course": "Full Test",
    }
    auto_name = test_type_labels.get(set_test["test_type"], "Test")

    # Create pending test record
    test_doc = {
        "id": test_id,
        "user_id": current_user["id"],
        "name": auto_name,  # Auto-generated, will be updated with reference_name
        "set_test_id": request.set_test_id,
        "set_test_name": set_test["name"],
        "test_type": set_test["test_type"],
        "reference_id": request.reference_id,
        "reference_name": "",  # Will be populated by background task
        "time_limit_minutes": set_test["time_limit_minutes"],
        "total_questions": 0,  # Will be populated by background task
        "questions": [],  # Will be populated by background task
        "generation_status": GenerationStatus.PENDING.value,
        "error_message": None,
        "score": None,
        "is_submitted": False,
        "submitted_at": None,
        "created_at": now,
        "generated_at": None,
    }

    await db.generated_tests.insert_one(test_doc)

    # Add background task for test generation
    background_tasks.add_task(
        generate_test_background,
        test_id,
        set_test,
        request.reference_id,
        current_user["id"]
    )

    return {
        "data": {
            "id": test_id,
            "name": auto_name,
            "set_test_id": request.set_test_id,
            "set_test_name": set_test["name"],
            "test_type": set_test["test_type"],
            "reference_id": request.reference_id,
            "reference_name": "",
            "generation_status": GenerationStatus.PENDING.value,
            "error_message": None,
            "created_at": now,
        },
        "message": "Test generation started. Poll /user-tests/{test_id}/status to check progress."
    }


@router.get("/{test_id}/status", response_model=APIResponse[TestGenerationResponse])
async def get_test_status(
    test_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Poll this endpoint to check test generation status."""
    db = get_database()

    test = await db.generated_tests.find_one({
        "id": test_id,
        "user_id": current_user["id"]
    })

    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test not found"
        )

    return {
        "data": {
            "id": test["id"],
            "name": test.get("name", ""),
            "set_test_id": test["set_test_id"],
            "set_test_name": test["set_test_name"],
            "test_type": test["test_type"],
            "reference_id": test["reference_id"],
            "reference_name": test["reference_name"],
            "generation_status": test["generation_status"],
            "error_message": test.get("error_message"),
            "created_at": test["created_at"],
        },
        "message": f"Test generation status: {test['generation_status']}"
    }


@router.get("/by-reference/{test_type}/{reference_id}", response_model=APIResponse[List[TestMetadataResponse]])
async def get_tests_by_reference(
    test_type: str,
    reference_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Get all user-generated tests for a specific topic/chapter/subject/course."""
    db = get_database()

    query = {
        "user_id": current_user["id"],
        "test_type": test_type,
        "reference_id": reference_id,
    }

    cursor = db.generated_tests.find(query).sort("created_at", -1)
    tests = await cursor.to_list(length=None)

    return {
        "data": [
            {
                "id": t["id"],
                "name": t.get("name", ""),
                "set_test_id": t["set_test_id"],
                "set_test_name": t["set_test_name"],
                "test_type": t["test_type"],
                "reference_id": t["reference_id"],
                "reference_name": t["reference_name"],
                "total_questions": t["total_questions"],
                "generation_status": t["generation_status"],
                "is_submitted": t["is_submitted"],
                "score": t.get("score"),
                "questions": [
                    {
                        "question_id": q["question_id"],
                        "has_integer_answer": q.get("has_integer_answer", False)
                    }
                    for q in t.get("questions", [])
                ],
                "created_at": t["created_at"],
            }
            for t in tests
        ],
        "message": "Tests for reference retrieved successfully"
    }


@router.get("", response_model=APIResponse[List[TestMetadataResponse]])
async def get_user_tests(
    generation_status: Optional[GenerationStatus] = None,
    is_submitted: Optional[bool] = None,
    skip: int = 0,
    limit: int = 20,
    current_user: dict = Depends(get_current_active_user)
):
    """Get all tests for the current user."""
    db = get_database()

    query = {"user_id": current_user["id"]}
    if generation_status:
        query["generation_status"] = generation_status.value
    if is_submitted is not None:
        query["is_submitted"] = is_submitted

    cursor = db.generated_tests.find(query).sort("created_at", -1).skip(skip).limit(limit)

    tests = await cursor.to_list(length=limit)

    return {
        "data": [
            {
                "id": t["id"],
                "name": t.get("name", ""),
                "set_test_id": t["set_test_id"],
                "set_test_name": t["set_test_name"],
                "test_type": t["test_type"],
                "reference_id": t["reference_id"],
                "reference_name": t["reference_name"],
                "total_questions": t["total_questions"],
                "generation_status": t["generation_status"],
                "is_submitted": t["is_submitted"],
                "score": t.get("score"),
                "questions": [
                    {
                        "question_id": q["question_id"],
                        "has_integer_answer": q.get("has_integer_answer", False)
                    }
                    for q in t.get("questions", [])
                ],
                "created_at": t["created_at"],
            }
            for t in tests
        ],
        "message": "Tests retrieved successfully"
    }


@router.get("/{test_id}", response_model=APIResponse[TestMetadataResponse])
async def get_test(
    test_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Get test metadata by ID (lightweight response without question details)."""
    db = get_database()

    # First check if test exists at all
    test_exists = await db.generated_tests.find_one({"id": test_id})

    if not test_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test with ID '{test_id}' does not exist"
        )

    # Then check if it belongs to current user
    test = await db.generated_tests.find_one({
        "id": test_id,
        "user_id": current_user["id"]
    })

    if not test:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this test"
        )

    # Prepare minimal question data (just IDs and has_integer_answer)
    minimal_questions = [
        {
            "question_id": q["question_id"],
            "has_integer_answer": q.get("has_integer_answer", False)
        }
        for q in test["questions"]
    ]

    # Return metadata with minimal question data
    return {
        "data": {
            "id": test["id"],
            "name": test.get("name", ""),
            "set_test_id": test["set_test_id"],
            "set_test_name": test["set_test_name"],
            "test_type": test["test_type"],
            "reference_id": test["reference_id"],
            "reference_name": test["reference_name"],
            "total_questions": test["total_questions"],
            "generation_status": test["generation_status"],
            "is_submitted": test["is_submitted"],
            "score": test.get("score"),
            "questions": minimal_questions,
            "created_at": test["created_at"],
        },
        "message": "Test metadata retrieved successfully"
    }


@router.get("/{test_id}/take", response_model=APIResponse[TestDetailResponse])
async def take_test(
    test_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Get full test details with questions for taking the test."""
    db = get_database()

    # First check if test exists at all
    test_exists = await db.generated_tests.find_one({"id": test_id})

    if not test_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test with ID '{test_id}' does not exist"
        )

    # Then check if it belongs to current user
    test = await db.generated_tests.find_one({
        "id": test_id,
        "user_id": current_user["id"]
    })

    if not test:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this test"
        )

    # Check if test generation is complete
    if test["generation_status"] != GenerationStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Test generation is {test['generation_status']}. Cannot take test yet."
        )

    # Fetch full question details from questions collection
    question_ids = [q["question_id"] for q in test["questions"]]
    questions_cursor = db.questions.find({"id": {"$in": question_ids}})
    questions_data = await questions_cursor.to_list(length=None)
    questions_map = {q["id"]: q for q in questions_data}

    # Build user answers map
    user_answers_map = {q["question_id"]: q.get("user_answer") for q in test["questions"]}

    # Prepare questions with full details (without correct answers)
    questions = []
    for q in test["questions"]:
        full_q = questions_map.get(q["question_id"], {})
        questions.append(QuestionForTaking(
            question_id=q["question_id"],
            question=full_q.get("question", ""),
            options=full_q.get("options"),
            has_integer_answer=q.get("has_integer_answer", False),
            user_answer=user_answers_map.get(q["question_id"])
        ).model_dump())

    return {
        "data": {
            "id": test["id"],
            "name": test.get("name", ""),
            "set_test_id": test["set_test_id"],
            "set_test_name": test["set_test_name"],
            "test_type": test["test_type"],
            "reference_id": test["reference_id"],
            "reference_name": test["reference_name"],
            "total_questions": test["total_questions"],
            "time_limit_minutes": test["time_limit_minutes"],
            "generation_status": test["generation_status"],
            "is_submitted": test["is_submitted"],
            "score": test.get("score"),
            "questions": questions,
            "created_at": test["created_at"],
        },
        "message": "Test retrieved successfully"
    }


@router.post("/{test_id}/submit", response_model=APIResponse[SubmitTestResponse])
async def submit_test(
    test_id: str,
    request: SubmitTestRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """Submit a test and calculate score."""
    db = get_database()

    # First check if test exists at all
    test_exists = await db.generated_tests.find_one({"id": test_id})

    if not test_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test with ID '{test_id}' does not exist"
        )

    # Then check if it belongs to current user
    test = await db.generated_tests.find_one({
        "id": test_id,
        "user_id": current_user["id"]
    })

    if not test:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to submit this test"
        )

    if test["generation_status"] != GenerationStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Test generation not completed"
        )

    if test["is_submitted"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Test has already been submitted"
        )

    # Get set test for scoring configuration
    set_test = await db.set_tests.find_one({"id": test["set_test_id"]})

    # Default scoring values
    marks_per_question = 4.0
    negative_marks = 1.0

    if set_test:
        marks_per_question = set_test.get("marks_per_question", 4.0)
        negative_marks = set_test.get("negative_marks", 1.0)

    # Create a map of user answers
    user_answers_map = {a.question_id: a.user_answer for a in request.answers}

    # Calculate results
    results = []
    correct_count = 0
    wrong_count = 0

    for q in test["questions"]:
        user_answer = user_answers_map.get(q["question_id"])
        is_correct = user_answer is not None and user_answer == q["answer"]

        if is_correct:
            correct_count += 1
        elif user_answer is not None and user_answer != "":
            wrong_count += 1

        results.append(QuestionResult(
            question_id=q["question_id"],
            user_answer=user_answer,
            correct_answer=q["answer"],
            is_correct=is_correct
        ).model_dump())

    total = test["total_questions"]
    unanswered = total - correct_count - wrong_count

    # Calculate score with negative marking
    score = (correct_count * marks_per_question) - (wrong_count * negative_marks)
    max_score = total * marks_per_question
    percentage = (score / max_score) * 100 if max_score > 0 else 0

    # Update test with user answers and score
    updated_questions = []
    for q in test["questions"]:
        q["user_answer"] = user_answers_map.get(q["question_id"])
        updated_questions.append(q)

    await db.generated_tests.update_one(
        {"id": test_id},
        {
            "$set": {
                "questions": updated_questions,
                "score": score,
                "is_submitted": True,
                "submitted_at": datetime.utcnow(),
            }
        }
    )

    return {
        "data": {
            "test_id": test_id,
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


@router.delete("/{test_id}", response_model=APIResponse[None])
async def delete_test(
    test_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Delete a test."""
    db = get_database()

    # First check if test exists at all
    test_exists = await db.generated_tests.find_one({"id": test_id})

    if not test_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test with ID '{test_id}' does not exist"
        )

    # Then check if it belongs to current user
    test = await db.generated_tests.find_one({
        "id": test_id,
        "user_id": current_user["id"]
    })

    if not test:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this test"
        )

    await db.generated_tests.delete_one({"id": test_id})

    return {
        "data": None,
        "message": "Test deleted successfully"
    }
