from fastapi import APIRouter, Query
from app.database import get_database

router = APIRouter(prefix="/global-notifications", tags=["global-notifications"])


@router.get("", response_model=list[str])
async def get_global_notifications(apiVersion: str = Query(...)):
    db = get_database()
    doc = await db.global_notifications.find_one(
        {"api_version": apiVersion, "is_active": True}
    )
    return doc["messages"] if doc else []
