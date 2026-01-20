from datetime import datetime, timedelta
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.security import HTTPAuthorizationCredentials

from app.database import get_database
from app.utils.rate_limiter import limiter
from app.models.response import APIResponse
from app.models.user import (
    SignupRequest,
    SignupResponse,
    VerifyOTPRequest,
    VerifyOTPResponse,
    SetPasswordRequest,
    LoginRequest,
    TokenResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
    UserResponse,
    UserRole,
)
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
)
from app.utils.otp import generate_otp, get_otp_expiry, is_otp_valid
from app.utils.email import send_otp_email, send_password_reset_email
from app.dependencies import get_current_active_user, security

router = APIRouter(prefix="/auth", tags=["auth"])


def get_plan_details(plan_name: str) -> dict:
    """Get plan details based on plan name."""
    plans = {
        "Pro": {
            "name": "Pro",
            "features": [
                "Unlimited test generation",
                "All premium question banks",
                "Advanced analytics and performance tracking",
                "Priority support",
                "Exclusive learning resources",
                "Custom test formats",
                "Progress insights"
            ],
            "test_generation_limit": None,  # Unlimited
            "question_bank_access": "all",
            "analytics_enabled": True,
            "priority_support": True
        },
        "Free": {
            "name": "Free",
            "features": [
                "Unlimited test generation",
                "All premium question banks",
                "Advanced analytics and performance tracking",
                "Priority support",
                "Exclusive learning resources",
                "Custom test formats",
                "Progress insights"
            ],
            "test_generation_limit": None,  # Unlimited
            "question_bank_access": "all",
            "analytics_enabled": True,
            "priority_support": True
        }
    }
    return plans.get(plan_name, plans["Free"])


@router.post("/signup", response_model=APIResponse[SignupResponse], status_code=201)
@limiter.limit("3/minute")
async def signup(request: Request, data: SignupRequest):
    """Register a new user and send OTP to email."""
    db = get_database()
    now = datetime.utcnow()

    # Check if email already exists
    existing_user = await db.users.find_one({"email": data.email})
    if existing_user:
        if existing_user.get("is_verified"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        else:
            # User exists but not verified, update OTP and resend
            otp = generate_otp()
            await db.users.update_one(
                {"email": data.email},
                {
                    "$set": {
                        "full_name": data.full_name,
                        "otp_code": otp,
                        "otp_expiry": get_otp_expiry(),
                        "updated_at": now,
                    }
                }
            )
            send_otp_email(data.email, otp, data.full_name)
            return {
                "data": {"user_id": existing_user["id"], "email": data.email},
                "message": "OTP sent to email"
            }

    # Create new user
    user_id = str(uuid4())
    otp = generate_otp()

    user_doc = {
        "id": user_id,
        "full_name": data.full_name,
        "email": data.email,
        "password_hash": None,
        "role": UserRole.USER,
        "plan": "Free",  # Default plan for all new users
        "is_active": False,
        "is_verified": False,
        "otp_code": otp,
        "otp_expiry": get_otp_expiry(),
        "created_at": now,
        "updated_at": now,
    }

    await db.users.insert_one(user_doc)
    send_otp_email(data.email, otp, data.full_name)

    return {
        "data": {"user_id": user_id, "email": data.email},
        "message": "OTP sent to email"
    }


@router.post("/verify-otp", response_model=APIResponse[VerifyOTPResponse])
async def verify_otp(request: VerifyOTPRequest):
    """Verify the OTP code."""
    db = get_database()

    user = await db.users.find_one({"email": request.email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
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

    if user["otp_code"] != request.otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP"
        )

    # Mark user as active (OTP verified)
    await db.users.update_one(
        {"email": request.email},
        {
            "$set": {
                "is_active": True,
                "otp_code": None,
                "otp_expiry": None,
                "updated_at": datetime.utcnow(),
            }
        }
    )

    return {
        "data": {"verified": True},
        "message": "OTP verified successfully"
    }


@router.post("/set-password", response_model=APIResponse[UserResponse])
async def set_password(request: SetPasswordRequest):
    """Set password after OTP verification."""
    db = get_database()

    user = await db.users.find_one({"email": request.email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please verify OTP first"
        )

    if user.get("is_verified"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password already set. Use change-password or forgot-password"
        )

    # Set password and mark as verified
    password_hash = hash_password(request.password)
    await db.users.update_one(
        {"email": request.email},
        {
            "$set": {
                "password_hash": password_hash,
                "is_verified": True,
                "updated_at": datetime.utcnow(),
            }
        }
    )

    updated_user = await db.users.find_one({"email": request.email})

    user_plan = updated_user.get("plan", "Free")
    plan_details = get_plan_details(user_plan)

    return {
        "data": {
            "id": updated_user["id"],
            "full_name": updated_user["full_name"],
            "email": updated_user["email"],
            "role": updated_user["role"],
            "plan": user_plan,
            "plan_details": plan_details,
            "is_active": updated_user["is_active"],
            "is_verified": updated_user["is_verified"],
            "created_at": updated_user["created_at"],
            "updated_at": updated_user["updated_at"],
        },
        "message": "Password set successfully"
    }


@router.post("/login", response_model=APIResponse[TokenResponse])
async def login(request: LoginRequest):
    """Login with email and password."""
    db = get_database()

    user = await db.users.find_one({"email": request.email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.get("is_verified") or not user.get("password_hash"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account not fully set up. Please complete registration"
        )

    if not verify_password(request.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )

    access_token = create_access_token(user["id"], user["role"])

    return {
        "data": {
            "access_token": access_token,
            "token_type": "bearer",
            "role": user["role"],
        },
        "message": "Login successful"
    }


@router.post("/forgot-password", response_model=APIResponse)
@limiter.limit("3/minute")
async def forgot_password(request: Request, data: ForgotPasswordRequest):
    """Request password reset OTP."""
    db = get_database()

    user = await db.users.find_one({"email": data.email})
    if not user:
        # Don't reveal if email exists or not for security
        return {
            "data": None,
            "message": "If the email exists, a reset code has been sent"
        }

    if not user.get("is_verified"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account not fully set up. Please complete registration first"
        )

    otp = generate_otp()
    await db.users.update_one(
        {"email": data.email},
        {
            "$set": {
                "otp_code": otp,
                "otp_expiry": get_otp_expiry(),
                "updated_at": datetime.utcnow(),
            }
        }
    )

    send_password_reset_email(data.email, otp, user["full_name"])

    return {
        "data": None,
        "message": "If the email exists, a reset code has been sent"
    }


@router.post("/reset-password", response_model=APIResponse)
async def reset_password(request: ResetPasswordRequest):
    """Reset password using OTP."""
    db = get_database()

    user = await db.users.find_one({"email": request.email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not user.get("otp_code") or not user.get("otp_expiry"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No password reset requested"
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

    password_hash = hash_password(request.new_password)
    await db.users.update_one(
        {"email": request.email},
        {
            "$set": {
                "password_hash": password_hash,
                "otp_code": None,
                "otp_expiry": None,
                "updated_at": datetime.utcnow(),
            }
        }
    )

    return {
        "data": None,
        "message": "Password reset successfully"
    }


@router.post("/change-password", response_model=APIResponse)
async def change_password(
    request: ChangePasswordRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """Change password for authenticated user."""
    db = get_database()

    if not verify_password(request.current_password, current_user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    password_hash = hash_password(request.new_password)
    await db.users.update_one(
        {"id": current_user["id"]},
        {
            "$set": {
                "password_hash": password_hash,
                "updated_at": datetime.utcnow(),
            }
        }
    )

    return {
        "data": None,
        "message": "Password changed successfully"
    }


@router.get("/me", response_model=APIResponse[UserResponse])
async def get_me(current_user: dict = Depends(get_current_active_user)):
    """Get current user profile."""
    db = get_database()

    user_plan = current_user.get("plan", "Free")
    plan_details = get_plan_details(user_plan)

    # Get examYear from app_metadata collection
    app_metadata = await db.app_metadata.find_one({})
    exam_year = app_metadata.get("examYear") if app_metadata else None

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
            "plan": user_plan,
            "plan_details": plan_details,
            "is_active": current_user["is_active"],
            "is_verified": current_user["is_verified"],
            "created_at": current_user["created_at"],
            "updated_at": current_user["updated_at"],
            "exam_year": exam_year,
            "plan_expiry": plan_expiry,
            "course_name": course_name,
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
