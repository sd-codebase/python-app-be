"""End-to-end test of the question-report endpoints against an in-memory Mongo.

Needs the dev-only packages mongomock-motor and httpx (not in requirements.txt):
    pip install mongomock-motor httpx
Run:  python -m tests.test_question_reports
Skips (exit 0) when they are not installed.
"""
import asyncio
import sys
from datetime import datetime

try:
    import httpx
    from mongomock_motor import AsyncMongoMockClient
except ImportError:
    print("skipped: pip install mongomock-motor httpx to run this test")
    sys.exit(0)

import app.main as main
import app.routes.question_reports as qr
from app.dependencies import get_current_active_user, require_admin

db = AsyncMongoMockClient()["test"]
qr.get_database = lambda: db
main.app.router.lifespan_context = None  # no real Mongo connection

STUDENT = {"id": "u1", "full_name": "Student One", "role": "user"}
STUDENT2 = {"id": "u2", "full_name": "Student Two", "role": "user"}
ADMIN = {"id": "a1", "full_name": "Admin", "role": "admin"}
current = {"user": STUDENT}

main.app.dependency_overrides[get_current_active_user] = lambda: current["user"]


def admin_only():
    if current["user"]["role"] != "admin":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin access required")
    return current["user"]


main.app.dependency_overrides[require_admin] = admin_only

ok = 0


def check(cond, label):
    global ok
    if not cond:
        raise AssertionError(label)
    ok += 1
    print("  ok -", label)


async def main_test():
    now = datetime.utcnow()
    for uid, aid in (("u1", "att1"), ("u2", "att2")):
        await db.test_attempts.insert_one({
            "id": aid, "user_id": uid, "test_id": "t1", "test_name": "Subject Test",
            "submitted_at": now,
            "questions": [
                {"question_id": "q1", "correct_answer": "2", "user_answer": "3", "has_integer_answer": False, "type": None},
                {"question_id": "q2", "correct_answer": "1", "user_answer": None, "has_integer_answer": False, "type": None},
            ],
        })

    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/question-reports", json={"attempt_id": "att1", "question_id": "q1", "reason": "wrong_answer", "comment": "  Answer should be 3  "})
        check(r.status_code == 201, f"student reports q1 (201) -> {r.status_code} {r.text[:120]}")
        body = r.json()["data"]
        check(body["user_answer"] == "3" and body["correct_answer"] == "2", "snapshot of user/correct answer stored")
        check(body["comment"] == "Answer should be 3", "comment trimmed")

        r = await c.post("/api/question-reports", json={"attempt_id": "att1", "question_id": "q1", "reason": "other"})
        check(r.status_code == 409, "duplicate open report rejected (409)")

        r = await c.post("/api/question-reports", json={"attempt_id": "att2", "question_id": "q1", "reason": "wrong_answer"})
        check(r.status_code == 404, "cannot report from someone else's attempt (404)")

        r = await c.post("/api/question-reports", json={"attempt_id": "att1", "question_id": "qX", "reason": "other"})
        check(r.status_code == 404, "question not in attempt (404)")

        r = await c.post("/api/question-reports", json={"attempt_id": "att1", "question_id": "q2", "reason": "bogus"})
        check(r.status_code == 422, "invalid reason rejected (422)")

        r = await c.post("/api/question-reports", json={"attempt_id": "att1", "question_id": "q2", "reason": "other", "comment": "x" * 301})
        check(r.status_code == 422, "comment over 300 chars rejected (422)")

        r = await c.get("/api/question-reports/mine", params={"attempt_id": "att1"})
        check(r.json()["data"] == [{"question_id": "q1", "status": "open"}], "mine: q1 open")

        r = await c.get("/api/admin/question-reports")
        check(r.status_code == 403, "student cannot list admin reports (403)")

        current["user"] = STUDENT2
        r = await c.post("/api/question-reports", json={"attempt_id": "att2", "question_id": "q1", "reason": "options_error"})
        check(r.status_code == 201, "second student reports q1")

        current["user"] = ADMIN
        r = await c.get("/api/admin/question-reports/counts")
        check(r.json()["data"] == {"open": 1, "resolved": 0, "dismissed": 0}, "counts: 1 open question")

        r = await c.get("/api/admin/question-reports", params={"status": "open"})
        data = r.json()["data"]
        check(len(data) == 1 and data[0]["question_id"] == "q1", "admin list grouped by question")
        check(data[0]["report_count"] == 2, "report_count 2")
        check(data[0]["reason_counts"] == {"wrong_answer": 1, "options_error": 1}, "reason counts")
        check({r_["user_name"] for r_ in data[0]["reports"]} == {None}, "user names absent when users collection empty")

        await db.users.insert_many([{"id": "u1", "full_name": "Student One"}, {"id": "u2", "full_name": "Student Two"}])
        r = await c.get("/api/admin/question-reports")
        check({r_["user_name"] for r_ in r.json()["data"][0]["reports"]} == {"Student One", "Student Two"}, "reporter names attached")

        r = await c.patch("/api/admin/question-reports/q1", json={"status": "resolved", "admin_note": "Fixed key"})
        check(r.status_code == 200 and r.json()["data"]["updated_count"] == 2, "resolve updates both reports")

        r = await c.get("/api/admin/question-reports/counts")
        check(r.json()["data"] == {"open": 0, "resolved": 1, "dismissed": 0}, "counts after resolve")

        r = await c.get("/api/admin/question-reports", params={"status": "resolved"})
        q = r.json()["data"][0]
        check(q["admin_note"] == "Fixed key" and q["resolved_by"] == "a1", "resolved note and admin stored")

        r = await c.patch("/api/admin/question-reports/q1", json={"status": "dismissed"})
        check(r.status_code == 404, "no open reports left to dismiss (404)")

        current["user"] = STUDENT
        r = await c.get("/api/question-reports/mine", params={"attempt_id": "att1"})
        check(r.json()["data"] == [{"question_id": "q1", "status": "resolved"}], "student sees resolved")
        r = await c.post("/api/question-reports", json={"attempt_id": "att1", "question_id": "q1", "reason": "wrong_answer"})
        check(r.status_code == 201, "student can report again after resolve")

        current["user"] = ADMIN
        r = await c.patch("/api/admin/question-reports/q1", json={"status": "open"})
        check(r.status_code == 200 and r.json()["data"]["updated_count"] == 2, "reopen resolved reports")
        r = await c.get("/api/admin/question-reports/counts")
        check(r.json()["data"]["open"] == 1, "one open question after reopen")

    print(f"\n{ok} checks passed")


asyncio.run(main_test())
