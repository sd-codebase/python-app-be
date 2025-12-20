import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4
from fastapi import APIRouter, HTTPException

from app.config import settings
from app.database import get_database
from app.models.response import APIResponse

router = APIRouter(prefix="/migrate", tags=["migration"])

DATA_DIR = Path(__file__).parent.parent.parent / "migration-data" / settings.app_for


def parse_json_field(value: Any) -> Any:
    """Parse JSON string field to dict/list if needed."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def parse_datetime(value: Any) -> datetime:
    """Parse datetime from various formats."""
    if value is None:
        return datetime.utcnow()
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # Handle ISO format with timezone
        value = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime.utcnow()
    return datetime.utcnow()


def load_json_file(file_path: Path) -> list[dict]:
    """Load JSON file and return list of records."""
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return []
    try:
        with open(file_path, "r") as f:
            content = f.read().strip()
            if not content:
                print(f"Empty file: {file_path}")
                return []
            data = json.loads(content)
        return data if isinstance(data, list) else [data]
    except json.JSONDecodeError as e:
        print(f"JSON decode error in {file_path}: {e}")
        return []
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []


def load_json_files_from_dir(dir_path: Path) -> list[dict]:
    """Load all JSON files from a directory."""
    records = []
    if not dir_path.exists():
        print(f"Directory not found: {dir_path}")
        return records
    for file_path in sorted(dir_path.glob("*.json")):
        print(f"Loading: {file_path}")
        records.extend(load_json_file(file_path))
    return records


@router.post("/", response_model=APIResponse)
async def run_migration():
    """
    Run migration from Supabase JSON exports to MongoDB.

    Expects data in:
    - data/courses/courses.json
    - data/subjects/subjects.json
    - data/chapters/chapters.json
    - data/topics/topics.json
    - data/questions/*.json (multiple files supported)

    Only available in development environment.
    """
    # Prevent migration in non-development environments
    if settings.environment.lower() != "development":
        raise HTTPException(
            status_code=403,
            detail=f"Migration is not allowed in {settings.environment} environment. Only available in development."
        )

    db = get_database()

    # ID mappings: old_supabase_id -> new_mongodb_id
    id_mappings = {
        "courses": {},
        "subjects": {},
        "chapters": {},
        "topics": {},
    }

    # Parent ID lookups for denormalization (new_id -> parent_new_id)
    parent_lookups = {
        "subject_to_course": {},   # subject_id -> course_id
        "chapter_to_subject": {},  # chapter_id -> subject_id
        "topic_to_chapter": {},    # topic_id -> chapter_id
    }

    summary = {
        "courses": {"inserted": 0, "skipped": 0},
        "subjects": {"inserted": 0, "skipped": 0},
        "chapters": {"inserted": 0, "skipped": 0},
        "topics": {"inserted": 0, "skipped": 0},
        "questions": {"inserted": 0, "skipped": 0},
    }

    # 1. Migrate Courses
    courses_file = DATA_DIR / "courses" / "courses.json"
    courses_data = load_json_file(courses_file)

    for course in courses_data:
        old_id = course.get("id")
        new_id = old_id or str(uuid4())  # Preserve original ID

        doc = {
            "id": new_id,
            "name": course.get("name"),
            "description": course.get("description"),
            "is_active": course.get("is_active", True),
            "created_at": parse_datetime(course.get("created_at")),
            "updated_at": parse_datetime(course.get("updated_at")),
        }

        try:
            await db.courses.insert_one(doc)
            if old_id:
                id_mappings["courses"][old_id] = new_id
            summary["courses"]["inserted"] += 1
        except Exception:
            summary["courses"]["skipped"] += 1

    # 2. Migrate Subjects
    subjects_file = DATA_DIR / "subjects" / "subjects.json"
    subjects_data = load_json_file(subjects_file)

    for subject in subjects_data:
        old_id = subject.get("id")
        new_id = old_id or str(uuid4())  # Preserve original ID

        # Remap course_id
        old_course_id = subject.get("course_id")
        new_course_id = id_mappings["courses"].get(old_course_id, old_course_id) if old_course_id else None

        doc = {
            "id": new_id,
            "name": subject.get("name"),
            "description": subject.get("description"),
            "course_id": new_course_id,
            "is_active": subject.get("is_active", True),
            "created_at": parse_datetime(subject.get("created_at")),
            "updated_at": parse_datetime(subject.get("updated_at")),
        }

        try:
            await db.subjects.insert_one(doc)
            if old_id:
                id_mappings["subjects"][old_id] = new_id
            # Build lookup for denormalization
            if new_course_id:
                parent_lookups["subject_to_course"][new_id] = new_course_id
            summary["subjects"]["inserted"] += 1
        except Exception:
            summary["subjects"]["skipped"] += 1

    # 3. Migrate Chapters
    chapters_file = DATA_DIR / "chapters" / "chapters.json"
    chapters_data = load_json_file(chapters_file)

    for chapter in chapters_data:
        old_id = chapter.get("id")
        new_id = old_id or str(uuid4())  # Preserve original ID

        # Remap subject_id
        old_subject_id = chapter.get("subject_id")
        new_subject_id = id_mappings["subjects"].get(old_subject_id, old_subject_id) if old_subject_id else None

        doc = {
            "id": new_id,
            "name": chapter.get("name"),
            "description": chapter.get("description"),
            "order_num": chapter.get("order_num", 0),
            "subject_id": new_subject_id,
            "is_active": chapter.get("is_active", True),
            "created_at": parse_datetime(chapter.get("created_at")),
            "updated_at": parse_datetime(chapter.get("updated_at")),
        }

        try:
            await db.chapters.insert_one(doc)
            if old_id:
                id_mappings["chapters"][old_id] = new_id
            # Build lookup for denormalization
            if new_subject_id:
                parent_lookups["chapter_to_subject"][new_id] = new_subject_id
            summary["chapters"]["inserted"] += 1
        except Exception:
            summary["chapters"]["skipped"] += 1

    # 4. Migrate Topics
    topics_file = DATA_DIR / "topics" / "topics.json"
    topics_data = load_json_file(topics_file)

    for topic in topics_data:
        old_id = topic.get("id")
        new_id = old_id or str(uuid4())  # Preserve original ID

        # Remap chapter_id
        old_chapter_id = topic.get("chapter_id")
        new_chapter_id = id_mappings["chapters"].get(old_chapter_id, old_chapter_id) if old_chapter_id else None

        doc = {
            "id": new_id,
            "name": topic.get("name"),
            "description": topic.get("description"),
            "order_num": topic.get("order_num", 0),
            "chapter_id": new_chapter_id,
            "is_active": topic.get("is_active", True),
            "resources_directory": topic.get("resources_directory"),
            "created_at": parse_datetime(topic.get("created_at")),
            "updated_at": parse_datetime(topic.get("updated_at")),
        }

        try:
            await db.topics.insert_one(doc)
            if old_id:
                id_mappings["topics"][old_id] = new_id
            # Build lookup for denormalization
            if new_chapter_id:
                parent_lookups["topic_to_chapter"][new_id] = new_chapter_id
            summary["topics"]["inserted"] += 1
        except Exception:
            summary["topics"]["skipped"] += 1

    # 5. Migrate Questions (multiple files)
    questions_dir = DATA_DIR / "questions"
    questions_data = load_json_files_from_dir(questions_dir)

    for question in questions_data:
        old_id = question.get("id")
        new_id = old_id or str(uuid4())  # Preserve original ID

        # Remap topic_id
        old_topic_id = question.get("topic_id")
        new_topic_id = id_mappings["topics"].get(old_topic_id, old_topic_id) if old_topic_id else None

        # Denormalize parent IDs using in-memory lookups
        chapter_id = None
        subject_id = None
        course_id = None

        if new_topic_id:
            chapter_id = parent_lookups["topic_to_chapter"].get(new_topic_id)
            if chapter_id:
                subject_id = parent_lookups["chapter_to_subject"].get(chapter_id)
                if subject_id:
                    course_id = parent_lookups["subject_to_course"].get(subject_id)

        doc = {
            "id": new_id,
            "question": question.get("question"),
            "options": parse_json_field(question.get("options")),
            "has_integer_answer": question.get("has_integer_answer"),
            "answer": question.get("answer"),
            "solutions": parse_json_field(question.get("solutions")),
            "level": question.get("level"),
            "is_marked_for_review": question.get("is_marked_for_review", False),
            "review_in_app": question.get("review_in_app", False),
            "sr_no": question.get("sr_no"),
            "pyo": question.get("pyo"),
            "extra": parse_json_field(question.get("extra")),
            "topic_id": new_topic_id,
            "chapter_id": chapter_id,
            "subject_id": subject_id,
            "course_id": course_id,
            "is_active": question.get("is_active", True),
            "verified_in_app": question.get("verified_in_app", False),
            "created_at": parse_datetime(question.get("created_at")),
            "updated_at": parse_datetime(question.get("updated_at")),
        }

        try:
            await db.questions.insert_one(doc)
            summary["questions"]["inserted"] += 1
        except Exception:
            summary["questions"]["skipped"] += 1

    return {
        "data": {
            "data_directory": str(DATA_DIR),
            "summary": summary,
            "id_mappings_count": {
                "courses": len(id_mappings["courses"]),
                "subjects": len(id_mappings["subjects"]),
                "chapters": len(id_mappings["chapters"]),
                "topics": len(id_mappings["topics"]),
            }
        },
        "message": "Migration completed successfully"
    }


@router.delete("/clear", response_model=APIResponse)
async def clear_all_data():
    """
    Clear all data from all collections. Use with caution!

    Only available in development environment.
    """
    # Prevent data clearing in non-development environments
    if settings.environment.lower() != "development":
        raise HTTPException(
            status_code=403,
            detail=f"Clearing data is not allowed in {settings.environment} environment. Only available in development."
        )

    db = get_database()

    deleted = {
        "courses": 0,
        "subjects": 0,
        "chapters": 0,
        "topics": 0,
        "questions": 0,
    }

    deleted["questions"] = (await db.questions.delete_many({})).deleted_count
    deleted["topics"] = (await db.topics.delete_many({})).deleted_count
    deleted["chapters"] = (await db.chapters.delete_many({})).deleted_count
    deleted["subjects"] = (await db.subjects.delete_many({})).deleted_count
    deleted["courses"] = (await db.courses.delete_many({})).deleted_count

    return {"data": deleted, "message": "All data cleared successfully"}
