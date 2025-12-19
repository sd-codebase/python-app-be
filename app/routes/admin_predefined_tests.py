import random
from datetime import datetime
from uuid import uuid4
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks

from app.database import get_database
from app.models.response import APIResponse
from app.models.predefined_test import (
    PredefinedTestStatus,
    CreatePredefinedTestRequest,
    UpdatePredefinedTestRequest,
    PredefinedTestQuestion,
    PredefinedTestAdminResponse,
    PredefinedTestDetailAdminResponse,
)
from app.dependencies import require_admin

router = APIRouter(prefix="/admin/predefined-tests", tags=["admin-predefined-tests"])


# Helper functions
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
    # Debug: count total questions with this course_id
    total_count = await db.questions.count_documents({"course_id": course_id})
    active_count = await db.questions.count_documents({"course_id": course_id, "is_active": {"$ne": False}})
    print(f"[DEBUG] get_questions_for_course({course_id}): total={total_count}, active={active_count}")

    cursor = db.questions.find({"course_id": course_id, "is_active": {"$ne": False}})
    questions = await cursor.to_list(length=None)
    print(f"[DEBUG] Fetched {len(questions)} questions for course {course_id}")
    return questions


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

    print(f"[DEBUG] select_questions_for_section: input={len(questions)}, is_numerical={is_numerical}, difficulty={difficulty}")

    # Filter by question type
    if is_numerical:
        filtered = [q for q in questions if q.get("has_integer_answer", False)]
    else:
        filtered = [q for q in questions if not q.get("has_integer_answer", False)]

    print(f"[DEBUG] After is_numerical filter: {len(filtered)} questions")

    if not filtered:
        return []

    # Select by difficulty if specified
    if difficulty and any(difficulty.values()):
        selected = select_questions_by_difficulty(filtered, difficulty)
        print(f"[DEBUG] After difficulty selection: {len(selected)} questions")
        return selected

    # Fallback to random selection based on question_count
    count = section.get("question_count", 10)
    selected = random.sample(filtered, min(count, len(filtered)))
    print(f"[DEBUG] Random selection: {len(selected)} questions (requested {count})")
    return selected


async def get_reference_name(test_type: str, reference_id: str) -> str:
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


async def generate_predefined_test_background(test_id: str, set_test: dict, reference_id: str):
    """Background task to generate predefined test questions."""
    db = get_database()

    try:
        await db.predefined_tests.update_one(
            {"id": test_id},
            {"$set": {"status": PredefinedTestStatus.IN_PROGRESS.value}}
        )

        test_type = set_test["test_type"]
        reference_name = await get_reference_name(test_type, reference_id)

        if reference_name == "Unknown":
            raise Exception(f"{test_type.capitalize()} with ID {reference_id} not found")

        test_questions = []

        if test_type == "topic":
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
                test_questions.append(PredefinedTestQuestion(
                    question_id=q["id"],
                    has_integer_answer=q.get("has_integer_answer", False),
                    answer=q["answer"]
                ).model_dump())

        elif test_type == "chapter":
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
                test_questions.append(PredefinedTestQuestion(
                    question_id=q["id"],
                    has_integer_answer=q.get("has_integer_answer", False),
                    answer=q["answer"]
                ).model_dump())

        elif test_type == "subject":
            sections = set_test.get("sections", [])
            all_questions = await get_questions_for_subject(reference_id)
            if not all_questions:
                raise Exception("No questions available for this subject")
            for section in sections:
                section_questions = select_questions_for_section(all_questions, section)
                for q in section_questions:
                    test_questions.append(PredefinedTestQuestion(
                        question_id=q["id"],
                        has_integer_answer=q.get("has_integer_answer", False),
                        answer=q["answer"]
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
                        test_questions.append(PredefinedTestQuestion(
                            question_id=q["id"],
                            has_integer_answer=q.get("has_integer_answer", False),
                            answer=q["answer"]
                        ).model_dump())

            if not test_questions:
                raise Exception("No questions could be selected for this course test")

        # Update with generated questions and publish
        await db.predefined_tests.update_one(
            {"id": test_id},
            {
                "$set": {
                    "reference_name": reference_name,
                    "questions": test_questions,
                    "total_questions": len(test_questions),
                    "status": PredefinedTestStatus.PUBLISHED.value,
                    "published_at": datetime.utcnow(),
                }
            }
        )

    except Exception as e:
        await db.predefined_tests.update_one(
            {"id": test_id},
            {
                "$set": {
                    "status": PredefinedTestStatus.FAILED.value,
                    "error_message": str(e),
                }
            }
        )


@router.post("", response_model=APIResponse[PredefinedTestAdminResponse], status_code=202)
async def create_predefined_test(
    request: CreatePredefinedTestRequest,
    background_tasks: BackgroundTasks,
    admin_user: dict = Depends(require_admin)
):
    """Create a new predefined test. Admin only."""
    db = get_database()

    set_test = await db.set_tests.find_one({"id": request.set_test_id})
    if not set_test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Set test format not found"
        )

    test_id = str(uuid4())
    now = datetime.utcnow()

    # Use custom name if provided, otherwise use set_test_name
    test_name = request.name if request.name else set_test["name"]

    test_doc = {
        "id": test_id,
        "set_test_id": request.set_test_id,
        "set_test_name": set_test["name"],
        "name": test_name,
        "test_type": set_test["test_type"],
        "reference_id": request.reference_id,
        "reference_name": "",
        "time_limit_minutes": set_test["time_limit_minutes"],
        "marks_per_question": set_test.get("marks_per_question", 4.0),
        "negative_marks": set_test.get("negative_marks", 1.0),
        "total_questions": 0,
        "questions": [],
        "status": PredefinedTestStatus.PENDING.value,
        "error_message": None,
        "created_by": admin_user["id"],
        "created_at": now,
        "published_at": None,
    }

    await db.predefined_tests.insert_one(test_doc)

    background_tasks.add_task(
        generate_predefined_test_background,
        test_id,
        set_test,
        request.reference_id
    )

    return {
        "data": {
            "id": test_id,
            "name": test_name,
            "set_test_id": request.set_test_id,
            "set_test_name": set_test["name"],
            "test_type": set_test["test_type"],
            "reference_id": request.reference_id,
            "reference_name": "",
            "time_limit_minutes": set_test["time_limit_minutes"],
            "total_questions": 0,
            "status": PredefinedTestStatus.PENDING.value,
            "error_message": None,
            "created_by": admin_user["id"],
            "created_at": now,
            "published_at": None,
        },
        "message": "Predefined test creation started. Poll status to check progress."
    }


@router.get("", response_model=APIResponse[List[PredefinedTestAdminResponse]])
async def get_predefined_tests(
    test_type: Optional[str] = None,
    status_filter: Optional[PredefinedTestStatus] = None,
    reference_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    admin_user: dict = Depends(require_admin)
):
    """Get all predefined tests. Admin only."""
    db = get_database()

    query = {}
    if test_type:
        query["test_type"] = test_type
    if status_filter:
        query["status"] = status_filter.value
    if reference_id:
        query["reference_id"] = reference_id

    cursor = db.predefined_tests.find(
        query,
        {"questions": 0}
    ).sort("created_at", -1).skip(skip).limit(limit)

    tests = await cursor.to_list(length=limit)

    return {
        "data": [
            {
                "id": t["id"],
                "name": t.get("name", t["set_test_name"]),
                "set_test_id": t["set_test_id"],
                "set_test_name": t["set_test_name"],
                "test_type": t["test_type"],
                "reference_id": t["reference_id"],
                "reference_name": t["reference_name"],
                "time_limit_minutes": t["time_limit_minutes"],
                "total_questions": t["total_questions"],
                "status": t["status"],
                "error_message": t.get("error_message"),
                "created_by": t["created_by"],
                "created_at": t["created_at"],
                "published_at": t.get("published_at"),
            }
            for t in tests
        ],
        "message": "Predefined tests retrieved successfully"
    }


@router.get("/{test_id}", response_model=APIResponse[PredefinedTestDetailAdminResponse])
async def get_predefined_test(
    test_id: str,
    admin_user: dict = Depends(require_admin)
):
    """Get a predefined test with questions. Admin only."""
    db = get_database()

    test = await db.predefined_tests.find_one({"id": test_id})

    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Predefined test not found"
        )

    return {
        "data": {
            "id": test["id"],
            "name": test.get("name", test["set_test_name"]),
            "set_test_id": test["set_test_id"],
            "set_test_name": test["set_test_name"],
            "test_type": test["test_type"],
            "reference_id": test["reference_id"],
            "reference_name": test["reference_name"],
            "time_limit_minutes": test["time_limit_minutes"],
            "total_questions": test["total_questions"],
            "status": test["status"],
            "error_message": test.get("error_message"),
            "questions": test.get("questions", []),
            "created_by": test["created_by"],
            "created_at": test["created_at"],
            "published_at": test.get("published_at"),
        },
        "message": "Predefined test retrieved successfully"
    }


@router.get("/{test_id}/status", response_model=APIResponse[PredefinedTestAdminResponse])
async def get_predefined_test_status(
    test_id: str,
    admin_user: dict = Depends(require_admin)
):
    """Poll predefined test generation status. Admin only."""
    db = get_database()

    test = await db.predefined_tests.find_one({"id": test_id}, {"questions": 0})

    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Predefined test not found"
        )

    return {
        "data": {
            "id": test["id"],
            "name": test.get("name", test["set_test_name"]),
            "set_test_id": test["set_test_id"],
            "set_test_name": test["set_test_name"],
            "test_type": test["test_type"],
            "reference_id": test["reference_id"],
            "reference_name": test["reference_name"],
            "time_limit_minutes": test["time_limit_minutes"],
            "total_questions": test["total_questions"],
            "status": test["status"],
            "error_message": test.get("error_message"),
            "created_by": test["created_by"],
            "created_at": test["created_at"],
            "published_at": test.get("published_at"),
        },
        "message": f"Status: {test['status']}"
    }


@router.put("/{test_id}/archive", response_model=APIResponse[PredefinedTestAdminResponse])
async def archive_predefined_test(
    test_id: str,
    admin_user: dict = Depends(require_admin)
):
    """Archive a predefined test. Admin only."""
    db = get_database()

    test = await db.predefined_tests.find_one({"id": test_id})

    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Predefined test not found"
        )

    await db.predefined_tests.update_one(
        {"id": test_id},
        {"$set": {"status": PredefinedTestStatus.ARCHIVED.value}}
    )

    test["status"] = PredefinedTestStatus.ARCHIVED.value

    return {
        "data": {
            "id": test["id"],
            "name": test.get("name", test["set_test_name"]),
            "set_test_id": test["set_test_id"],
            "set_test_name": test["set_test_name"],
            "test_type": test["test_type"],
            "reference_id": test["reference_id"],
            "reference_name": test["reference_name"],
            "time_limit_minutes": test["time_limit_minutes"],
            "total_questions": test["total_questions"],
            "status": test["status"],
            "error_message": test.get("error_message"),
            "created_by": test["created_by"],
            "created_at": test["created_at"],
            "published_at": test.get("published_at"),
        },
        "message": "Predefined test archived successfully"
    }


@router.put("/{test_id}/publish", response_model=APIResponse[PredefinedTestAdminResponse])
async def publish_predefined_test(
    test_id: str,
    admin_user: dict = Depends(require_admin)
):
    """Republish an archived predefined test. Admin only."""
    db = get_database()

    test = await db.predefined_tests.find_one({"id": test_id})

    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Predefined test not found"
        )

    if test["status"] not in [PredefinedTestStatus.ARCHIVED.value, PredefinedTestStatus.FAILED.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only archived or failed tests can be republished"
        )

    if not test.get("questions"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot publish test without questions"
        )

    now = datetime.utcnow()
    await db.predefined_tests.update_one(
        {"id": test_id},
        {
            "$set": {
                "status": PredefinedTestStatus.PUBLISHED.value,
                "published_at": now,
            }
        }
    )

    test["status"] = PredefinedTestStatus.PUBLISHED.value
    test["published_at"] = now

    return {
        "data": {
            "id": test["id"],
            "name": test.get("name", test["set_test_name"]),
            "set_test_id": test["set_test_id"],
            "set_test_name": test["set_test_name"],
            "test_type": test["test_type"],
            "reference_id": test["reference_id"],
            "reference_name": test["reference_name"],
            "time_limit_minutes": test["time_limit_minutes"],
            "total_questions": test["total_questions"],
            "status": test["status"],
            "error_message": test.get("error_message"),
            "created_by": test["created_by"],
            "created_at": test["created_at"],
            "published_at": test["published_at"],
        },
        "message": "Predefined test published successfully"
    }


@router.delete("/{test_id}", response_model=APIResponse[None])
async def delete_predefined_test(
    test_id: str,
    admin_user: dict = Depends(require_admin)
):
    """Delete a predefined test. Admin only."""
    db = get_database()

    test = await db.predefined_tests.find_one({"id": test_id})

    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Predefined test not found"
        )

    # Delete the test
    await db.predefined_tests.delete_one({"id": test_id})

    # Also delete all user attempts for this test
    await db.predefined_test_attempts.delete_many({"test_id": test_id})

    return {
        "data": None,
        "message": "Predefined test and all related attempts deleted successfully"
    }
