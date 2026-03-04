from datetime import datetime
from uuid import uuid4
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status, Query

from app.database import get_database
from app.models.response import APIResponse
from app.models.user import (
    UserRole,
    UserResponse,
    UserListResponse,
    AdminUpdateUserRequest,
    AdminCreateUserRequest,
)
from app.utils.security import hash_password
from app.dependencies import require_admin

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


def build_user_response(user: dict, include_otp: bool = False) -> dict:
    """Build a user response dict from a database document with all fields except password."""
    user_plan = user.get("plan", "Free")
    response = {
        "id": user["id"],
        "full_name": user["full_name"],
        "email": user["email"],
        "role": user["role"],
        "user_type": user.get("user_type", "regular"),
        "plan": user_plan,
        "is_active": user["is_active"],
        "is_verified": user["is_verified"],
        "created_at": user["created_at"],
        "updated_at": user["updated_at"],
        "exam_year": user.get("exam_year"),
        "plan_expiry": user.get("plan_expiry"),
        "course_name": user.get("course_name"),
        "whatsapp_number": user.get("whatsapp_number"),
        "country_code": user.get("country_code"),
    }
    if include_otp:
        response["otp_code"] = user.get("otp_code")
        response["otp_expiry"] = user.get("otp_expiry")
    return response


@router.get("", response_model=APIResponse[List[UserListResponse]])
async def get_users(
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    is_verified: Optional[bool] = None,
    search: Optional[str] = Query(None, description="Search by name or email"),
    skip: int = 0,
    limit: int = 20,
    admin_user: dict = Depends(require_admin)
):
    """Get all users with optional filtering. Admin only."""
    db = get_database()

    query = {}
    if role:
        query["role"] = role.value
    if is_active is not None:
        query["is_active"] = is_active
    if is_verified is not None:
        query["is_verified"] = is_verified
    if search:
        query["$or"] = [
            {"full_name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
        ]

    cursor = db.users.find(
        query,
        {"password_hash": 0}
    ).sort("created_at", -1).skip(skip).limit(limit)

    users = await cursor.to_list(length=limit)
    total = await db.users.count_documents(query)

    return {
        "data": [build_user_response(u, include_otp=True) for u in users],
        "message": f"Retrieved {len(users)} users (total: {total})"
    }


@router.get("/{user_id}", response_model=APIResponse[UserResponse])
async def get_user(
    user_id: str,
    admin_user: dict = Depends(require_admin)
):
    """Get a single user by ID. Admin only."""
    db = get_database()

    user = await db.users.find_one(
        {"id": user_id},
        {"password_hash": 0, "otp_code": 0, "otp_expiry": 0}
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return {
        "data": build_user_response(user),
        "message": "User retrieved successfully"
    }


@router.post("", response_model=APIResponse[UserResponse], status_code=201)
async def create_user(
    request: AdminCreateUserRequest,
    admin_user: dict = Depends(require_admin)
):
    """Create a new user directly (bypasses OTP verification). Admin only."""
    db = get_database()

    # Check if email already exists
    existing_user = await db.users.find_one({"email": request.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    user_id = str(uuid4())
    now = datetime.utcnow()

    user_doc = {
        "id": user_id,
        "full_name": request.full_name,
        "email": request.email,
        "password_hash": hash_password(request.password),
        "role": request.role.value,
        "plan": "Free",  # Default plan for all new users
        "is_active": request.is_active,
        "is_verified": True,
        "otp_code": None,
        "otp_expiry": None,
        "created_at": now,
        "updated_at": now,
    }

    await db.users.insert_one(user_doc)

    return {
        "data": build_user_response(user_doc),
        "message": "User created successfully"
    }


@router.put("/{user_id}", response_model=APIResponse[UserResponse])
async def update_user(
    user_id: str,
    request: AdminUpdateUserRequest,
    admin_user: dict = Depends(require_admin)
):
    """Update a user's details. Admin only."""
    db = get_database()

    existing = await db.users.find_one({"id": user_id})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Prevent admin from demoting themselves
    if user_id == admin_user["id"] and request.role and request.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own admin role"
        )

    # Prevent admin from deactivating themselves
    if user_id == admin_user["id"] and request.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )

    update_data = request.model_dump(exclude_unset=True)
    if "role" in update_data and update_data["role"]:
        update_data["role"] = update_data["role"].value
    update_data["updated_at"] = datetime.utcnow()

    await db.users.update_one(
        {"id": user_id},
        {"$set": update_data}
    )

    updated = await db.users.find_one(
        {"id": user_id},
        {"password_hash": 0, "otp_code": 0, "otp_expiry": 0}
    )

    return {
        "data": build_user_response(updated),
        "message": "User updated successfully"
    }


@router.delete("/{user_id}", response_model=APIResponse[None])
async def delete_user(
    user_id: str,
    admin_user: dict = Depends(require_admin)
):
    """Delete a user and all associated data. Admin only. Only temporary or inactive users can be deleted."""
    db = get_database()

    # Prevent admin from deleting themselves
    if user_id == admin_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    existing = await db.users.find_one({"id": user_id})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Only allow deletion of temporary or inactive users
    is_temp = existing.get("user_type") == "temp"
    is_inactive = not existing.get("is_active", True)

    if not is_temp and not is_inactive:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only temporary or inactive users can be deleted"
        )

    # Delete user's generated tests
    await db.generated_tests.delete_many({"user_id": user_id})

    # Delete user's test attempts
    await db.test_attempts.delete_many({"user_id": user_id})

    # Delete user record
    await db.users.delete_one({"id": user_id})

    # Invalidate all tokens for this user
    await db.blacklisted_tokens.delete_many({"user_id": user_id})

    return {
        "data": None,
        "message": "User and all associated data deleted successfully"
    }


@router.post("/{user_id}/reset-password", response_model=APIResponse[None])
async def admin_reset_password(
    user_id: str,
    new_password: str = Query(..., min_length=8, description="New password for the user"),
    admin_user: dict = Depends(require_admin)
):
    """Reset a user's password. Admin only."""
    db = get_database()

    existing = await db.users.find_one({"id": user_id})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    password_hash = hash_password(new_password)
    await db.users.update_one(
        {"id": user_id},
        {
            "$set": {
                "password_hash": password_hash,
                "updated_at": datetime.utcnow(),
            }
        }
    )

    return {
        "data": None,
        "message": "Password reset successfully"
    }


@router.post("/{user_id}/toggle-active", response_model=APIResponse[UserResponse])
async def toggle_user_active(
    user_id: str,
    admin_user: dict = Depends(require_admin)
):
    """Toggle a user's active status. Admin only."""
    db = get_database()

    # Prevent admin from toggling themselves
    if user_id == admin_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot toggle your own active status"
        )

    existing = await db.users.find_one({"id": user_id})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    new_status = not existing["is_active"]
    await db.users.update_one(
        {"id": user_id},
        {
            "$set": {
                "is_active": new_status,
                "updated_at": datetime.utcnow(),
            }
        }
    )

    updated = await db.users.find_one(
        {"id": user_id},
        {"password_hash": 0, "otp_code": 0, "otp_expiry": 0}
    )

    status_text = "activated" if new_status else "deactivated"
    return {
        "data": build_user_response(updated),
        "message": f"User {status_text} successfully"
    }
