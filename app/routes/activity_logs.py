import json
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
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
)
from app.models.response import APIResponse
from app.utils.security import decode_token

router = APIRouter(prefix="/activity-logs", tags=["activity-logs"])
admin_router = APIRouter(prefix="/admin/activity-logs", tags=["admin-activity-logs"])

# Logs must be accepted before login, so auth is optional here
optional_security = HTTPBearer(auto_error=False)

MAX_PROPS_BYTES = 8 * 1024


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
    if name:
        if name.endswith("*"):
            query["name"] = {"$regex": f"^{name[:-1]}"}
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
