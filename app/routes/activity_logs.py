import csv
import io
import json
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pymongo.errors import BulkWriteError

from app.database import get_database
from app.dependencies import get_current_active_user, require_admin
from app.models.activity_log import (
    ActivityBatchRequest,
    ActivityBatchResponse,
    ActivityCategory,
    ActivityDeviceResponse,
    ActivityLinkRequest,
    ActivityLinkResponse,
    ActivityLogListResponse,
    ActivityLogPurgeResponse,
    ActivityLogRangeSummary,
    ActivityUserSummaryList,
)
from app.models.response import APIResponse
from app.utils.security import decode_token

router = APIRouter(prefix="/activity-logs", tags=["activity-logs"])
admin_router = APIRouter(prefix="/admin/activity-logs", tags=["admin-activity-logs"])

# Logs must be accepted before login, so auth is optional here
optional_security = HTTPBearer(auto_error=False)

MAX_PROPS_BYTES = 8 * 1024

# Export/delete only reach logs at least this many days old; dates are IST calendar days
RETENTION_MIN_DAYS = 10
APP_TIMEZONE = ZoneInfo("Asia/Kolkata")

EXPORT_COLUMNS = [
    "client_ts", "received_at", "name", "category", "screen", "duration_ms",
    "user_id", "user_name", "whatsapp_number", "user_type", "pre_login", "linked_at",
    "device_id", "session_id", "seq", "app_variant", "app_version", "platform", "ip",
    "props",
]


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
) -> Optional[dict]:
    """Resolve the user from a bearer token if one is present and valid, else None."""
    if credentials is None:
        return None

    payload = decode_token(credentials.credentials)
    if not payload or not payload.get("sub"):
        return None

    db = get_database()
    if await db.blacklisted_tokens.find_one({"token": credentials.credentials}):
        return None

    return await db.users.find_one({"id": payload["sub"]})


def get_client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    return request.client.host if request.client else None


def limit_props(props: dict) -> dict:
    """Keep stored props small; oversized payloads are replaced by a truncated marker."""
    encoded = json.dumps(props, default=str)
    if len(encoded.encode("utf-8")) <= MAX_PROPS_BYTES:
        return props
    return {"_truncated": True, "_preview": encoded[:1000]}


@router.post("/batch", response_model=APIResponse[ActivityBatchResponse])
async def ingest_activity_batch(
    data: ActivityBatchRequest,
    request: Request,
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """Store a batch of activity events from the app. Works before and after login."""
    db = get_database()
    now = datetime.utcnow()
    ip = get_client_ip(request)
    device = data.device.model_dump()

    token_user_id = current_user["id"] if current_user else None
    token_user_type = current_user.get("user_type", "regular") if current_user else None

    docs = []
    for event in data.events:
        # Only trust the device's user_id when the request is authenticated as that user
        if event.user_id and event.user_id == token_user_id:
            user_id = token_user_id
            user_type = token_user_type
            claimed_user_id = None
        else:
            user_id = None
            user_type = None
            claimed_user_id = event.user_id

        docs.append({
            "event_id": event.event_id,
            "name": event.name,
            "category": event.category.value,
            "client_ts": event.ts,
            "received_at": now,
            "device_id": data.device_id,
            "session_id": event.session_id,
            "seq": event.seq,
            "screen": event.screen,
            "duration_ms": event.duration_ms,
            "user_id": user_id,
            "user_type": user_type,
            "claimed_user_id": claimed_user_id,
            "pre_login": event.pre_login,
            "linked_at": None,
            "props": limit_props(event.props),
            "app_variant": device.get("app_variant"),
            "app_version": device.get("app_version"),
            "platform": device.get("platform"),
            "ip": ip,
        })

    accepted = len(docs)
    duplicates = 0
    if docs:
        try:
            await db.activity_logs.insert_many(docs, ordered=False)
        except BulkWriteError as e:
            # Retried batches resend already-stored events; skip those (duplicate event_id)
            write_errors = e.details.get("writeErrors", [])
            duplicates = sum(1 for err in write_errors if err.get("code") == 11000)
            if duplicates != len(write_errors):
                raise
            accepted -= duplicates

    device_update = {
        "$set": {"info": device, "last_seen": now, "last_ip": ip},
        "$setOnInsert": {"first_seen": now},
    }
    if token_user_id:
        device_update["$set"]["last_user_id"] = token_user_id
        device_update["$addToSet"] = {"user_ids": token_user_id}
    await db.activity_devices.update_one({"device_id": data.device_id}, device_update, upsert=True)

    return {
        "data": {"accepted": accepted, "duplicates": duplicates},
        "message": "Activity logged",
    }


@router.post("/link", response_model=APIResponse[ActivityLinkResponse])
async def link_device_activity(
    data: ActivityLinkRequest,
    current_user: dict = Depends(get_current_active_user),
):
    """Attach this device's pre-login (and guest) activity to the user who just logged in."""
    if current_user.get("user_type") == "temp":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Guest sessions cannot claim activity",
        )

    db = get_database()
    now = datetime.utcnow()

    result = await db.activity_logs.update_many(
        {
            "device_id": data.device_id,
            "client_ts": {"$lte": now},
            "claimed_user_id": None,
            "$or": [{"user_id": None}, {"user_type": "temp"}],
        },
        {
            "$set": {
                "user_id": current_user["id"],
                "user_type": current_user.get("user_type", "regular"),
                "pre_login": True,
                "linked_at": now,
            }
        },
    )

    await db.activity_devices.update_one(
        {"device_id": data.device_id},
        {
            "$set": {"last_user_id": current_user["id"], "last_seen": now},
            "$addToSet": {"user_ids": current_user["id"]},
            "$setOnInsert": {"first_seen": now, "info": {}},
        },
        upsert=True,
    )

    return {
        "data": {"linked": result.modified_count},
        "message": "Activity linked to user",
    }


@admin_router.get("", response_model=APIResponse[ActivityLogListResponse])
async def list_activity_logs(
    user_id: Optional[str] = None,
    phone: Optional[str] = Query(None, description="WhatsApp number; also matches pre-login attempts"),
    device_id: Optional[str] = None,
    session_id: Optional[str] = None,
    category: Optional[ActivityCategory] = None,
    exclude_category: Optional[List[ActivityCategory]] = Query(None, description="Categories to leave out"),
    name: Optional[str] = Query(None, description="Event name (exact) or prefix ending with *"),
    screen: Optional[str] = None,
    from_ts: Optional[datetime] = None,
    to_ts: Optional[datetime] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    admin_user: dict = Depends(require_admin),
):
    """Search activity logs. Admin only."""
    db = get_database()

    query: dict = {}
    if user_id:
        query["user_id"] = user_id
    if phone:
        phone_user = await db.users.find_one({"whatsapp_number": phone}, {"id": 1})
        or_clauses = [{"props.phone": phone}]
        if phone_user:
            or_clauses.append({"user_id": phone_user["id"]})
        query["$or"] = or_clauses
    if device_id:
        query["device_id"] = device_id
    if session_id:
        query["session_id"] = session_id
    if category:
        query["category"] = category.value
    elif exclude_category:
        query["category"] = {"$nin": [c.value for c in exclude_category]}
    if name:
        if name.endswith("*"):
            query["name"] = {"$regex": f"^{re.escape(name[:-1])}"}
        else:
            query["name"] = name
    if screen:
        query["screen"] = screen
    if from_ts or to_ts:
        query["client_ts"] = {}
        if from_ts:
            query["client_ts"]["$gte"] = from_ts
        if to_ts:
            query["client_ts"]["$lte"] = to_ts

    cursor = (
        db.activity_logs.find(query, {"_id": 0})
        .sort([("client_ts", -1), ("seq", -1)])
        .skip(skip)
        .limit(limit)
    )
    items = await cursor.to_list(length=limit)
    total = await db.activity_logs.count_documents(query)

    user_ids = list({item["user_id"] for item in items if item.get("user_id")})
    users_by_id = {}
    if user_ids:
        users = await db.users.find(
            {"id": {"$in": user_ids}},
            {"_id": 0, "id": 1, "full_name": 1, "whatsapp_number": 1, "user_type": 1},
        ).to_list(length=len(user_ids))
        users_by_id = {u["id"]: u for u in users}

    for item in items:
        item["user"] = users_by_id.get(item.get("user_id"))

    return {
        "data": {"items": items, "total": total},
        "message": "Activity logs retrieved successfully",
    }


@admin_router.get("/users", response_model=APIResponse[ActivityUserSummaryList])
async def list_activity_users(
    search: Optional[str] = Query(None, description="Name or WhatsApp number"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    admin_user: dict = Depends(require_admin),
):
    """Per-user activity summary, most recently active first. Admin only."""
    db = get_database()

    match: dict = {"user_id": {"$ne": None}}
    if search:
        pattern = {"$regex": re.escape(search), "$options": "i"}
        matching_users = await db.users.find(
            {"$or": [{"full_name": pattern}, {"whatsapp_number": pattern}]}, {"_id": 0, "id": 1}
        ).to_list(length=1000)
        match["user_id"] = {"$in": [u["id"] for u in matching_users]}

    pipeline = [
        {"$match": match},
        {"$sort": {"client_ts": 1, "seq": 1}},
        {"$group": {
            "_id": "$user_id",
            "events": {"$sum": 1},
            "sessions": {"$addToSet": "$session_id"},
            "devices": {"$addToSet": "$device_id"},
            "first_ts": {"$min": "$client_ts"},
            "last_ts": {"$max": "$client_ts"},
            "last_event": {"$last": "$name"},
            "last_screen": {"$last": "$screen"},
            "user_type": {"$last": "$user_type"},
            "app_variant": {"$last": "$app_variant"},
            "app_version": {"$last": "$app_version"},
            "pre_login_events": {"$sum": {"$cond": ["$pre_login", 1, 0]}},
            "errors": {"$sum": {"$cond": [{"$eq": ["$category", "error"]}, 1, 0]}},
            "tests_submitted": {"$sum": {"$cond": [
                {"$in": ["$name", ["test_submitted", "test_auto_submitted"]]}, 1, 0
            ]}},
        }},
        {"$sort": {"last_ts": -1}},
        {"$facet": {
            "items": [{"$skip": skip}, {"$limit": limit}],
            "total": [{"$count": "count"}],
        }},
    ]
    result = await db.activity_logs.aggregate(pipeline, allowDiskUse=True).to_list(length=1)
    facet = result[0] if result else {"items": [], "total": []}

    user_ids = [item["_id"] for item in facet["items"]]
    users = await db.users.find(
        {"id": {"$in": user_ids}},
        {"_id": 0, "id": 1, "full_name": 1, "whatsapp_number": 1, "user_type": 1},
    ).to_list(length=len(user_ids)) if user_ids else []
    users_by_id = {u["id"]: u for u in users}

    items = []
    for item in facet["items"]:
        user = users_by_id.get(item["_id"]) or {}
        items.append({
            "user_id": item["_id"],
            "full_name": user.get("full_name"),
            "whatsapp_number": user.get("whatsapp_number"),
            "user_type": user.get("user_type") or item.get("user_type"),
            "events": item["events"],
            "sessions": len(item["sessions"]),
            "devices": len(item["devices"]),
            "first_ts": item["first_ts"],
            "last_ts": item["last_ts"],
            "last_event": item.get("last_event"),
            "last_screen": item.get("last_screen"),
            "app_variant": item.get("app_variant"),
            "app_version": item.get("app_version"),
            "pre_login_events": item["pre_login_events"],
            "errors": item["errors"],
            "tests_submitted": item["tests_submitted"],
        })

    return {
        "data": {"items": items, "total": facet["total"][0]["count"] if facet["total"] else 0},
        "message": "Activity users retrieved successfully",
    }


@admin_router.get("/devices/{device_id}", response_model=APIResponse[ActivityDeviceResponse])
async def get_activity_device(
    device_id: str,
    admin_user: dict = Depends(require_admin),
):
    """Get device details and the users who have used it. Admin only."""
    db = get_database()
    device = await db.activity_devices.find_one({"device_id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    return {
        "data": device,
        "message": "Device retrieved successfully",
    }


def resolve_purge_cutoff(end_date: date) -> datetime:
    """Validate the end date (at least RETENTION_MIN_DAYS old) and return the exclusive UTC cutoff.

    The end date is inclusive: everything up to 23:59:59 IST on that day is covered.
    """
    today = datetime.now(APP_TIMEZONE).date()
    latest_allowed = today - timedelta(days=RETENTION_MIN_DAYS)
    if end_date > latest_allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"End date must be on or before {latest_allowed.isoformat()} "
                   f"(logs from the last {RETENTION_MIN_DAYS} days can't be exported or deleted)",
        )
    next_day_start = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=APP_TIMEZONE)
    # Stored timestamps are naive UTC
    return next_day_start.astimezone(timezone.utc).replace(tzinfo=None)


@admin_router.get("/range-summary", response_model=APIResponse[ActivityLogRangeSummary])
async def activity_logs_range_summary(
    end_date: date = Query(..., description="Inclusive end date (IST), at least 10 days ago"),
    admin_user: dict = Depends(require_admin),
):
    """How many logs an export/delete up to end_date would cover. Admin only."""
    cutoff = resolve_purge_cutoff(end_date)
    db = get_database()
    query = {"client_ts": {"$lt": cutoff}}

    count = await db.activity_logs.count_documents(query)
    oldest = await db.activity_logs.find_one(query, {"client_ts": 1}, sort=[("client_ts", 1)])

    return {
        "data": {
            "end_date": end_date,
            "count": count,
            "oldest_ts": oldest["client_ts"] if oldest else None,
        },
        "message": "Range summary retrieved successfully",
    }


@admin_router.get("/export")
async def export_activity_logs(
    end_date: date = Query(..., description="Inclusive end date (IST), at least 10 days ago"),
    admin_user: dict = Depends(require_admin),
):
    """Download all logs up to end_date as CSV, oldest first. Admin only."""
    cutoff = resolve_purge_cutoff(end_date)
    db = get_database()

    async def rows():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(EXPORT_COLUMNS)

        cursor = db.activity_logs.find({"client_ts": {"$lt": cutoff}}, {"_id": 0}).sort(
            [("client_ts", 1), ("seq", 1)]
        ).batch_size(1000)

        batch: List[dict] = []
        async for log in cursor:
            batch.append(log)
            if len(batch) == 1000:
                await write_batch(writer, batch)
                batch = []
                yield buffer.getvalue()
                buffer.seek(0)
                buffer.truncate(0)
        if batch:
            await write_batch(writer, batch)
        yield buffer.getvalue()

    async def write_batch(writer, batch: List[dict]):
        user_ids = list({log["user_id"] for log in batch if log.get("user_id")})
        users = await db.users.find(
            {"id": {"$in": user_ids}},
            {"_id": 0, "id": 1, "full_name": 1, "whatsapp_number": 1},
        ).to_list(length=len(user_ids)) if user_ids else []
        users_by_id = {u["id"]: u for u in users}

        for log in batch:
            user = users_by_id.get(log.get("user_id")) or {}
            writer.writerow([
                log.get("client_ts").isoformat() + "Z" if log.get("client_ts") else "",
                log.get("received_at").isoformat() + "Z" if log.get("received_at") else "",
                log.get("name"),
                log.get("category"),
                log.get("screen") or "",
                log.get("duration_ms") if log.get("duration_ms") is not None else "",
                log.get("user_id") or "",
                user.get("full_name") or "",
                user.get("whatsapp_number") or "",
                log.get("user_type") or "",
                log.get("pre_login", False),
                log.get("linked_at").isoformat() + "Z" if log.get("linked_at") else "",
                log.get("device_id"),
                log.get("session_id"),
                log.get("seq"),
                log.get("app_variant") or "",
                log.get("app_version") or "",
                log.get("platform") or "",
                log.get("ip") or "",
                json.dumps(log.get("props") or {}, default=str, ensure_ascii=False),
            ])

    filename = f"activity-logs-until-{end_date.isoformat()}.csv"
    return StreamingResponse(
        rows(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@admin_router.delete("", response_model=APIResponse[ActivityLogPurgeResponse])
async def delete_activity_logs(
    end_date: date = Query(..., description="Inclusive end date (IST), at least 10 days ago"),
    admin_user: dict = Depends(require_admin),
):
    """Permanently delete all logs up to end_date. Admin only."""
    cutoff = resolve_purge_cutoff(end_date)
    db = get_database()

    result = await db.activity_logs.delete_many({"client_ts": {"$lt": cutoff}})

    return {
        "data": {"end_date": end_date, "deleted": result.deleted_count},
        "message": f"Deleted {result.deleted_count} activity logs",
    }
