from datetime import datetime, timedelta
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.security import HTTPAuthorizationCredentials

from app.database import get_database
from app.utils.rate_limiter import limiter
from app.models.response import APIResponse
from app.models.user import (
    SendWhatsAppOTPRequest,
    VerifyWhatsAppOTPRequest,
    VerifyWhatsAppOTPResponse,
    CompleteRegistrationRequest,
    UpdateWhatsAppRequest,
    VerifyUpdateWhatsAppRequest,
    UpdateNameRequest,
    TokenResponse,
    UserResponse,
    UserRole,
)
from app.utils.security import create_access_token
from app.utils.otp import generate_otp, get_otp_expiry, is_otp_valid
from app.utils.whatsapp import send_whatsapp_otp
from app.dependencies import get_current_active_user, security
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/send-whatsapp-otp", response_model=APIResponse)
@limiter.limit("3/minute")
async def send_otp(request: Request, data: SendWhatsAppOTPRequest):
    """Send OTP to WhatsApp number. Creates unverified user if not exists."""
    db = get_database()
    now = datetime.utcnow()
    phone = data.phone
    full_phone = f"91{phone}"

    # Find user by whatsapp_number
    existing_user = await db.users.find_one({"whatsapp_number": phone})

    otp = generate_otp()

    if existing_user:
        # Update OTP on existing user
        await db.users.update_one(
            {"whatsapp_number": phone},
            {
                "$set": {
                    "otp_code": otp,
                    "otp_expiry": get_otp_expiry(),
                    "updated_at": now,
                }
            }
        )
    else:
        # Create new unverified user
        user_id = str(uuid4())
        user_doc = {
            "id": user_id,
            "full_name": "User",
            "email": f"wa_{phone}@whatsapp.local",
            "password_hash": None,
            "role": UserRole.USER,
            "user_type": "regular",
            "plan": "Free",
            "is_active": False,
            "is_verified": False,
            "whatsapp_number": phone,
            "country_code": "91",
            "otp_code": otp,
            "otp_expiry": get_otp_expiry(),
            "created_at": now,
            "updated_at": now,
        }
        await db.users.insert_one(user_doc)

    # Skip sending OTP for demo account
    is_demo = settings.demo_whatsapp_number and phone == settings.demo_whatsapp_number
    if not is_demo:
        sent = await send_whatsapp_otp(full_phone, otp)
        if not sent:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send OTP. Please try again."
            )

    return {
        "data": None,
        "message": "OTP sent to WhatsApp"
    }


@router.post("/verify-whatsapp-otp", response_model=APIResponse[VerifyWhatsAppOTPResponse])
async def verify_whatsapp_otp(request: VerifyWhatsAppOTPRequest):
    """Verify WhatsApp OTP. Returns token for existing users, is_new_user flag for new users."""
    db = get_database()

    user = await db.users.find_one({"whatsapp_number": request.phone})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Please request OTP first."
        )

    is_demo = (
        settings.demo_whatsapp_number
        and request.phone == settings.demo_whatsapp_number
    )

    if is_demo:
        # Demo account: verify against hardcoded OTP only
        if request.otp != settings.demo_otp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP"
            )
    else:
        if not user.get("otp_code") or not user.get("otp_expiry"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No OTP requested"
            )

        if not is_otp_valid(user["otp_expiry"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP has expired"
            )

        if user["otp_code"] != request.otp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP"
            )

    # Clear OTP
    await db.users.update_one(
        {"whatsapp_number": request.phone},
        {
            "$set": {
                "otp_code": None,
                "otp_expiry": None,
                "updated_at": datetime.utcnow(),
            }
        }
    )

    # Check if this is a verified (existing) user
    if user.get("is_verified"):
        # Existing user — return token
        if not user.get("is_active"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated"
            )

        access_token = create_access_token(user["id"], user["role"])
        return {
            "data": {
                "is_new_user": False,
                "access_token": access_token,
                "token_type": "bearer",
                "role": user["role"],
            },
            "message": "Login successful"
        }
    else:
        # New user — mark active but not verified yet (needs name)
        await db.users.update_one(
            {"whatsapp_number": request.phone},
            {"$set": {"is_active": True, "updated_at": datetime.utcnow()}}
        )
        return {
            "data": {
                "is_new_user": True,
            },
            "message": "OTP verified. Please complete registration."
        }


@router.post("/complete-registration", response_model=APIResponse[TokenResponse])
async def complete_registration(request: CompleteRegistrationRequest):
    """Complete registration for new users by setting their name."""
    db = get_database()

    user = await db.users.find_one({"whatsapp_number": request.phone})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if user.get("is_verified"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already registered"
        )

    if not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please verify OTP first"
        )

    # Set name and mark verified
    await db.users.update_one(
        {"whatsapp_number": request.phone},
        {
            "$set": {
                "full_name": request.full_name,
                "is_verified": True,
                "updated_at": datetime.utcnow(),
            }
        }
    )

    access_token = create_access_token(user["id"], user["role"])

    return {
        "data": {
            "access_token": access_token,
            "token_type": "bearer",
            "role": user["role"],
        },
        "message": "Registration complete"
    }


@router.post("/update-whatsapp", response_model=APIResponse)
async def update_whatsapp(
    data: UpdateWhatsAppRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """Send OTP to a new WhatsApp number for updating."""
    db = get_database()
    phone = data.phone

    # Check if number already taken by another user
    existing = await db.users.find_one({"whatsapp_number": phone})
    if existing and existing["id"] != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This WhatsApp number is already associated with another account"
        )

    otp = generate_otp()
    full_phone = f"91{phone}"

    await db.users.update_one(
        {"id": current_user["id"]},
        {
            "$set": {
                "pending_whatsapp_number": phone,
                "otp_code": otp,
                "otp_expiry": get_otp_expiry(),
                "updated_at": datetime.utcnow(),
            }
        }
    )

    sent = await send_whatsapp_otp(full_phone, otp)
    if not sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP. Please try again."
        )

    return {
        "data": None,
        "message": "OTP sent to new WhatsApp number"
    }


@router.post("/verify-update-whatsapp", response_model=APIResponse)
async def verify_update_whatsapp(
    data: VerifyUpdateWhatsAppRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """Verify OTP and update WhatsApp number."""
    db = get_database()

    user = await db.users.find_one({"id": current_user["id"]})

    if not user.get("pending_whatsapp_number"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No WhatsApp number update requested"
        )

    if user["pending_whatsapp_number"] != data.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number does not match pending update"
        )

    if not user.get("otp_code") or not user.get("otp_expiry"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No OTP requested"
        )

    if not is_otp_valid(user["otp_expiry"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired"
        )

    if user["otp_code"] != data.otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP"
        )

    await db.users.update_one(
        {"id": current_user["id"]},
        {
            "$set": {
                "whatsapp_number": data.phone,
                "country_code": "91",
                "pending_whatsapp_number": None,
                "otp_code": None,
                "otp_expiry": None,
                "updated_at": datetime.utcnow(),
            }
        }
    )

    return {
        "data": None,
        "message": "WhatsApp number updated successfully"
    }


@router.post("/update-name", response_model=APIResponse)
async def update_name(
    data: UpdateNameRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """Update user's full name."""
    db = get_database()

    await db.users.update_one(
        {"id": current_user["id"]},
        {
            "$set": {
                "full_name": data.full_name,
                "updated_at": datetime.utcnow(),
            }
        }
    )

    return {
        "data": None,
        "message": "Name updated successfully"
    }


@router.get("/me", response_model=APIResponse[UserResponse])
async def get_me(current_user: dict = Depends(get_current_active_user)):
    """Get current user profile."""
    db = get_database()

    # Get examYear from app_metadata collection
    app_metadata = await db.app_metadata.find_one({})
    exam_year = app_metadata.get("examYear") if app_metadata else None
    ads_disabled = app_metadata.get("ads_disabled", False) if app_metadata else False
    ads_cooling_period_minutes = app_metadata.get("ads_cooling_period_minutes", 10) if app_metadata else 10

    # Get course name from courses collection
    course = await db.courses.find_one({})
    course_name = course.get("name") if course else None

    # Calculate planExpiry as created_at + 91 days
    created_at = current_user.get("created_at")
    plan_expiry = created_at + timedelta(days=91) if created_at else None

    return {
        "data": {
            "id": current_user["id"],
            "full_name": current_user["full_name"],
            "email": current_user["email"],
            "role": current_user["role"],
            "user_type": current_user.get("user_type", "regular"),
            "plan": current_user.get("plan", "Free"),
            "is_active": current_user["is_active"],
            "is_verified": current_user["is_verified"],
            "created_at": current_user["created_at"],
            "updated_at": current_user["updated_at"],
            "exam_year": exam_year,
            "plan_expiry": plan_expiry,
            "course_name": course_name,
            "ads_disabled": ads_disabled,
            "ads_cooling_period_minutes": ads_cooling_period_minutes,
            "whatsapp_number": current_user.get("whatsapp_number"),
            "country_code": current_user.get("country_code"),
        },
        "message": "User profile retrieved successfully"
    }


@router.post("/logout", response_model=APIResponse)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: dict = Depends(get_current_active_user)
):
    """Logout and invalidate the current token."""
    db = get_database()

    # Add token to blacklist
    await db.blacklisted_tokens.insert_one({
        "token": credentials.credentials,
        "user_id": current_user["id"],
        "blacklisted_at": datetime.utcnow(),
    })

    return {
        "data": None,
        "message": "Logged out successfully"
    }


@router.post("/anonymous", response_model=APIResponse[TokenResponse])
@limiter.limit("10/minute")
async def anonymous_access(request: Request):
    """Create anonymous/temp user and return access token."""
    db = get_database()
    now = datetime.utcnow()
    user_id = str(uuid4())

    user_doc = {
        "id": user_id,
        "full_name": "User",
        "email": f"temp_{user_id}@anonymous.local",
        "password_hash": None,
        "role": UserRole.USER,
        "user_type": "temp",
        "plan": "Free",
        "is_active": True,
        "is_verified": True,
        "whatsapp_number": None,
        "country_code": None,
        "otp_code": None,
        "otp_expiry": None,
        "created_at": now,
        "updated_at": now,
    }

    await db.users.insert_one(user_doc)

    # 24-hour token (1440 minutes)
    access_token = create_access_token(user_id, UserRole.USER, expires_minutes=1440)

    return {
        "data": {
            "access_token": access_token,
            "token_type": "bearer",
            "role": UserRole.USER,
        },
        "message": "Anonymous access granted"
    }


@router.delete("/delete-my-account", response_model=APIResponse)
async def delete_my_account(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: dict = Depends(get_current_active_user)
):
    """Deactivate the current user's account. User will no longer be able to login."""
    db = get_database()
    user_id = current_user["id"]

    # Deactivate the user account
    await db.users.update_one(
        {"id": user_id},
        {
            "$set": {
                "is_active": False,
                "updated_at": datetime.utcnow(),
            }
        }
    )

    # Blacklist the current token to log them out immediately
    await db.blacklisted_tokens.insert_one({
        "token": credentials.credentials,
        "user_id": user_id,
        "blacklisted_at": datetime.utcnow(),
    })

    return {
        "data": None,
        "message": "Account deactivated successfully"
    }
