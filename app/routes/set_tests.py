from datetime import datetime
from uuid import uuid4
from typing import List, Union
from fastapi import APIRouter, HTTPException, Depends, status, Body

from app.database import get_database
from app.models.response import APIResponse
from app.models.set_test import (
    SetTestType,
    TopicTestCreate,
    TopicTestUpdate,
    ChapterTestCreate,
    ChapterTestUpdate,
    SubjectTestCreate,
    SubjectTestUpdate,
    CourseTestCreate,
    CourseTestUpdate,
    SetTestResponse,
    SetTestListResponse,
)
from app.dependencies import get_current_active_user

router = APIRouter(prefix="/set-tests", tags=["set-tests"])


def build_response(doc: dict) -> dict:
    """Build a response dict from a database document."""
    return {
        "id": doc["id"],
        "name": doc["name"],
        "time_limit_minutes": doc["time_limit_minutes"],
        "is_active": doc["is_active"],
        "test_type": doc["test_type"],
        "created_at": doc["created_at"],
        "updated_at": doc["updated_at"],
        "topic_id": doc.get("topic_id"),
        "chapter_id": doc.get("chapter_id"),
        "subject_id": doc.get("subject_id"),
        "course_id": doc.get("course_id"),
        "question_count": doc.get("question_count"),
        "marks_per_question": doc.get("marks_per_question"),
        "negative_marks": doc.get("negative_marks"),
        "difficulty": doc.get("difficulty"),
        "sections": doc.get("sections"),
        "subject_sections": doc.get("subject_sections"),
    }


@router.get("", response_model=APIResponse[List[SetTestListResponse]])
async def get_set_tests(
    test_type: SetTestType = None,
    is_active: bool = None,
    skip: int = 0,
    limit: int = 20,
    current_user: dict = Depends(get_current_active_user)
):
    """Get all set tests with optional filtering."""
    db = get_database()

    query = {}
    if test_type:
        query["test_type"] = test_type.value
    if is_active is not None:
        query["is_active"] = is_active

    cursor = db.set_tests.find(query).sort("created_at", -1).skip(skip).limit(limit)
    tests = await cursor.to_list(length=limit)

    return {
        "data": [
            {
                "id": t["id"],
                "name": t["name"],
                "time_limit_minutes": t["time_limit_minutes"],
                "is_active": t["is_active"],
                "test_type": t["test_type"],
                "created_at": t["created_at"],
                "updated_at": t["updated_at"],
            }
            for t in tests
        ],
        "message": "Set tests retrieved successfully"
    }


@router.get("/{set_test_id}", response_model=APIResponse[SetTestResponse])
async def get_set_test(
    set_test_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Get a single set test by ID."""
    db = get_database()

    test = await db.set_tests.find_one({"id": set_test_id})

    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Set test not found"
        )

    return {
        "data": build_response(test),
        "message": "Set test retrieved successfully"
    }


@router.post("/topic", response_model=APIResponse[SetTestResponse], status_code=201)
async def create_topic_test(
    request: TopicTestCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """Create a new topic test configuration template."""
    db = get_database()

    test_id = str(uuid4())
    now = datetime.utcnow()

    doc = {
        "id": test_id,
        "name": request.name,
        "time_limit_minutes": request.time_limit_minutes,
        "is_active": request.is_active,
        "test_type": request.test_type.value,
        "topic_id": request.topic_id,
        "question_count": request.question_count,
        "marks_per_question": request.marks_per_question,
        "negative_marks": request.negative_marks,
        "difficulty": request.difficulty.model_dump(),
        "created_at": now,
        "updated_at": now,
    }

    await db.set_tests.insert_one(doc)

    return {
        "data": build_response(doc),
        "message": "Topic test created successfully"
    }


@router.post("/chapter", response_model=APIResponse[SetTestResponse], status_code=201)
async def create_chapter_test(
    request: ChapterTestCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """Create a new chapter test configuration template."""
    db = get_database()

    test_id = str(uuid4())
    now = datetime.utcnow()

    doc = {
        "id": test_id,
        "name": request.name,
        "time_limit_minutes": request.time_limit_minutes,
        "is_active": request.is_active,
        "test_type": request.test_type.value,
        "chapter_id": request.chapter_id,
        "question_count": request.question_count,
        "marks_per_question": request.marks_per_question,
        "negative_marks": request.negative_marks,
        "difficulty": request.difficulty.model_dump(),
        "created_at": now,
        "updated_at": now,
    }

    await db.set_tests.insert_one(doc)

    return {
        "data": build_response(doc),
        "message": "Chapter test created successfully"
    }


@router.post("/subject", response_model=APIResponse[SetTestResponse], status_code=201)
async def create_subject_test(
    request: SubjectTestCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """Create a new subject test configuration template."""
    db = get_database()

    test_id = str(uuid4())
    now = datetime.utcnow()

    doc = {
        "id": test_id,
        "name": request.name,
        "time_limit_minutes": request.time_limit_minutes,
        "is_active": request.is_active,
        "test_type": request.test_type.value,
        "subject_id": request.subject_id,
        "sections": [s.model_dump() for s in request.sections],
        "created_at": now,
        "updated_at": now,
    }

    await db.set_tests.insert_one(doc)

    return {
        "data": build_response(doc),
        "message": "Subject test created successfully"
    }


@router.post("/course", response_model=APIResponse[SetTestResponse], status_code=201)
async def create_course_test(
    request: CourseTestCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """Create a new course test configuration template."""
    db = get_database()

    test_id = str(uuid4())
    now = datetime.utcnow()

    doc = {
        "id": test_id,
        "name": request.name,
        "time_limit_minutes": request.time_limit_minutes,
        "is_active": request.is_active,
        "test_type": request.test_type.value,
        "course_id": request.course_id,
        "subject_sections": [ss.model_dump() for ss in request.subject_sections],
        "created_at": now,
        "updated_at": now,
    }

    await db.set_tests.insert_one(doc)

    return {
        "data": build_response(doc),
        "message": "Course test created successfully"
    }


@router.put("/topic/{set_test_id}", response_model=APIResponse[SetTestResponse])
async def update_topic_test(
    set_test_id: str,
    request: TopicTestUpdate,
    current_user: dict = Depends(get_current_active_user)
):
    """Update a topic test configuration template."""
    db = get_database()

    existing = await db.set_tests.find_one({"id": set_test_id, "test_type": "topic"})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic test not found"
        )

    update_data = request.model_dump(exclude_unset=True)
    if "difficulty" in update_data and update_data["difficulty"]:
        update_data["difficulty"] = update_data["difficulty"]
    update_data["updated_at"] = datetime.utcnow()

    await db.set_tests.update_one(
        {"id": set_test_id},
        {"$set": update_data}
    )

    updated = await db.set_tests.find_one({"id": set_test_id})

    return {
        "data": build_response(updated),
        "message": "Topic test updated successfully"
    }


@router.put("/chapter/{set_test_id}", response_model=APIResponse[SetTestResponse])
async def update_chapter_test(
    set_test_id: str,
    request: ChapterTestUpdate,
    current_user: dict = Depends(get_current_active_user)
):
    """Update a chapter test configuration template."""
    db = get_database()

    existing = await db.set_tests.find_one({"id": set_test_id, "test_type": "chapter"})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chapter test not found"
        )

    update_data = request.model_dump(exclude_unset=True)
    if "difficulty" in update_data and update_data["difficulty"]:
        update_data["difficulty"] = update_data["difficulty"]
    update_data["updated_at"] = datetime.utcnow()

    await db.set_tests.update_one(
        {"id": set_test_id},
        {"$set": update_data}
    )

    updated = await db.set_tests.find_one({"id": set_test_id})

    return {
        "data": build_response(updated),
        "message": "Chapter test updated successfully"
    }


@router.put("/subject/{set_test_id}", response_model=APIResponse[SetTestResponse])
async def update_subject_test(
    set_test_id: str,
    request: SubjectTestUpdate,
    current_user: dict = Depends(get_current_active_user)
):
    """Update a subject test configuration template."""
    db = get_database()

    existing = await db.set_tests.find_one({"id": set_test_id, "test_type": "subject"})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject test not found"
        )

    update_data = request.model_dump(exclude_unset=True)
    if "sections" in update_data and update_data["sections"]:
        update_data["sections"] = [s if isinstance(s, dict) else s for s in update_data["sections"]]
    update_data["updated_at"] = datetime.utcnow()

    await db.set_tests.update_one(
        {"id": set_test_id},
        {"$set": update_data}
    )

    updated = await db.set_tests.find_one({"id": set_test_id})

    return {
        "data": build_response(updated),
        "message": "Subject test updated successfully"
    }


@router.put("/course/{set_test_id}", response_model=APIResponse[SetTestResponse])
async def update_course_test(
    set_test_id: str,
    request: CourseTestUpdate,
    current_user: dict = Depends(get_current_active_user)
):
    """Update a course test configuration template."""
    db = get_database()

    existing = await db.set_tests.find_one({"id": set_test_id, "test_type": "course"})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course test not found"
        )

    update_data = request.model_dump(exclude_unset=True)
    if "subject_sections" in update_data and update_data["subject_sections"]:
        update_data["subject_sections"] = [ss if isinstance(ss, dict) else ss for ss in update_data["subject_sections"]]
    update_data["updated_at"] = datetime.utcnow()

    await db.set_tests.update_one(
        {"id": set_test_id},
        {"$set": update_data}
    )

    updated = await db.set_tests.find_one({"id": set_test_id})

    return {
        "data": build_response(updated),
        "message": "Course test updated successfully"
    }


@router.delete("/{set_test_id}", response_model=APIResponse[None])
async def delete_set_test(
    set_test_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Delete a set test configuration."""
    db = get_database()

    existing = await db.set_tests.find_one({"id": set_test_id})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Set test not found"
        )

    await db.set_tests.delete_one({"id": set_test_id})

    return {
        "data": None,
        "message": "Set test deleted successfully"
    }
