"""Question reports: students flag a problem with a question while reviewing an attempt;
admins review the reports grouped by question and mark them resolved or dismissed.

Fixing the question content itself is done in the existing data tools, not here.
"""
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.database import get_database
from app.dependencies import get_current_active_user, require_admin
from app.models.question_report import (
    AdminReportCounts,
    AdminReportedQuestion,
    AdminUpdateReportsRequest,
    AdminUpdateReportsResponse,
    CreateQuestionReportRequest,
    MyReportedQuestion,
    QuestionReportResponse,
    ReportStatus,
)
from app.models.response import APIResponse
from app.utils.rate_limiter import limiter

router = APIRouter(prefix="/question-reports", tags=["question-reports"])
admin_router = APIRouter(prefix="/admin/question-reports", tags=["admin-question-reports"])


def _report_response(doc: dict) -> dict:
    return QuestionReportResponse(**doc).model_dump()


@router.post("", response_model=APIResponse[QuestionReportResponse], status_code=201)
@limiter.limit("20/minute")
async def create_report(
    request: Request,
    data: CreateQuestionReportRequest,
    current_user: dict = Depends(get_current_active_user),
):
    """Report a problem with a question from one of the user's own attempts.

    One open report per user per question; reporting again while it is open returns 409.
    """
    db = get_database()

    attempt = await db.test_attempts.find_one(
        {"id": data.attempt_id, "user_id": current_user["id"]},
        {"_id": 0, "id": 1, "test_id": 1, "test_name": 1, "questions": 1},
    )
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")

    question = next(
        (q for q in attempt.get("questions", []) if q.get("question_id") == data.question_id),
        None,
    )
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found in this attempt")

    existing = await db.question_reports.find_one(
        {"question_id": data.question_id, "user_id": current_user["id"], "status": ReportStatus.OPEN.value}
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You have already reported this question")

    now = datetime.utcnow()
    comment = (data.comment or "").strip() or None
    doc = {
        "id": str(uuid4()),
        "question_id": data.question_id,
        "attempt_id": attempt["id"],
        "test_id": attempt["test_id"],
        "test_name": attempt.get("test_name"),
        "user_id": current_user["id"],
        "reason": data.reason.value,
        "comment": comment,
        # Snapshot of what the user saw, so admins can judge the report later
        "user_answer": question.get("user_answer"),
        "correct_answer": question.get("correct_answer"),
        "has_integer_answer": bool(question.get("has_integer_answer")),
        "type": question.get("type"),
        "status": ReportStatus.OPEN.value,
        "admin_note": None,
        "resolved_by": None,
        "resolved_at": None,
        "created_at": now,
        "updated_at": now,
    }
    await db.question_reports.insert_one(doc)

    return {"data": _report_response(doc), "message": "Question reported"}


@router.get("/mine", response_model=APIResponse[List[MyReportedQuestion]])
async def my_reports(
    attempt_id: str = Query(..., min_length=1, max_length=100),
    current_user: dict = Depends(get_current_active_user),
):
    """Questions of this attempt that the user has reported (latest report status per question)."""
    db = get_database()
    attempt = await db.test_attempts.find_one(
        {"id": attempt_id, "user_id": current_user["id"]},
        {"_id": 0, "questions.question_id": 1},
    )
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")

    question_ids = [q["question_id"] for q in attempt.get("questions", [])]
    cursor = db.question_reports.find(
        {"user_id": current_user["id"], "question_id": {"$in": question_ids}},
        {"_id": 0, "question_id": 1, "status": 1, "created_at": 1},
    ).sort("created_at", 1)

    latest = {}
    async for r in cursor:
        latest[r["question_id"]] = r["status"]  # later reports overwrite earlier ones

    return {
        "data": [{"question_id": qid, "status": s} for qid, s in latest.items()],
        "message": "Reported questions",
    }


@admin_router.get("/counts", response_model=APIResponse[AdminReportCounts])
async def admin_report_counts(admin_user: dict = Depends(require_admin)):
    """Number of reported questions per status (for the admin badge and filter tabs)."""
    db = get_database()
    counts = {s.value: 0 for s in ReportStatus}
    pipeline = [
        {"$group": {"_id": {"q": "$question_id", "s": "$status"}}},
        {"$group": {"_id": "$_id.s", "n": {"$sum": 1}}},
    ]
    async for row in db.question_reports.aggregate(pipeline):
        if row["_id"] in counts:
            counts[row["_id"]] = row["n"]
    return {"data": counts, "message": "Report counts"}


@admin_router.get("", response_model=APIResponse[List[AdminReportedQuestion]])
async def admin_list_reports(
    report_status: ReportStatus = Query(ReportStatus.OPEN, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    admin_user: dict = Depends(require_admin),
):
    """Reported questions with the given status, grouped by question, most-reported first."""
    db = get_database()
    pipeline = [
        {"$match": {"status": report_status.value}},
        {"$sort": {"created_at": -1}},
        {
            "$group": {
                "_id": "$question_id",
                "report_count": {"$sum": 1},
                "reasons": {"$push": "$reason"},
                "correct_answer": {"$first": "$correct_answer"},
                "has_integer_answer": {"$first": "$has_integer_answer"},
                "type": {"$first": "$type"},
                "first_reported_at": {"$min": "$created_at"},
                "last_reported_at": {"$max": "$created_at"},
                "admin_note": {"$first": "$admin_note"},
                "resolved_by": {"$first": "$resolved_by"},
                "resolved_at": {"$first": "$resolved_at"},
                "reports": {
                    "$push": {
                        "id": "$id",
                        "user_id": "$user_id",
                        "reason": "$reason",
                        "comment": "$comment",
                        "user_answer": "$user_answer",
                        "test_name": "$test_name",
                        "created_at": "$created_at",
                    }
                },
            }
        },
        {"$sort": {"report_count": -1, "last_reported_at": -1}},
        {"$skip": skip},
        {"$limit": limit},
    ]
    groups = [g async for g in db.question_reports.aggregate(pipeline)]

    # Attach reporter names
    user_ids = list({r["user_id"] for g in groups for r in g["reports"]})
    names = {}
    if user_ids:
        async for u in db.users.find({"id": {"$in": user_ids}}, {"_id": 0, "id": 1, "full_name": 1}):
            names[u["id"]] = u.get("full_name")

    data = []
    for g in groups:
        reason_counts: dict = {}
        for reason in g["reasons"]:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        data.append(
            AdminReportedQuestion(
                question_id=g["_id"],
                status=report_status,
                report_count=g["report_count"],
                reason_counts=reason_counts,
                correct_answer=g.get("correct_answer"),
                has_integer_answer=bool(g.get("has_integer_answer")),
                type=g.get("type"),
                first_reported_at=g["first_reported_at"],
                last_reported_at=g["last_reported_at"],
                admin_note=g.get("admin_note"),
                resolved_by=g.get("resolved_by"),
                resolved_at=g.get("resolved_at"),
                reports=[{**r, "user_name": names.get(r["user_id"])} for r in g["reports"]],
            ).model_dump()
        )

    return {"data": data, "message": "Reported questions"}


@admin_router.patch("/{question_id}", response_model=APIResponse[AdminUpdateReportsResponse])
async def admin_update_reports(
    question_id: str,
    data: AdminUpdateReportsRequest,
    admin_user: dict = Depends(require_admin),
):
    """Set the status of a question's reports.

    resolved / dismissed: applies to all of the question's open reports.
    open: reopens all of the question's resolved and dismissed reports.
    """
    db = get_database()
    if data.status == ReportStatus.OPEN:
        match = {"question_id": question_id, "status": {"$ne": ReportStatus.OPEN.value}}
    else:
        match = {"question_id": question_id, "status": ReportStatus.OPEN.value}

    now = datetime.utcnow()
    closing = data.status != ReportStatus.OPEN
    result = await db.question_reports.update_many(
        match,
        {
            "$set": {
                "status": data.status.value,
                "admin_note": (data.admin_note or "").strip() or None,
                "resolved_by": admin_user["id"] if closing else None,
                "resolved_at": now if closing else None,
                "updated_at": now,
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No reports to update for this question")

    return {
        "data": {"question_id": question_id, "status": data.status, "updated_count": result.modified_count},
        "message": "Reports updated",
    }
