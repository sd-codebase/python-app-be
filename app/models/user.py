from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from enum import Enum


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


class UserType(str, Enum):
    REGULAR = "regular"
    TEMP = "temp"


class UserBase(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr


class UserCreate(UserBase):
    pass


class User(UserBase):
    id: str
    role: UserRole = UserRole.USER
    user_type: str = "regular"
    is_active: bool = False
    is_verified: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserInDB(User):
    password_hash: Optional[str] = None
    otp_code: Optional[str] = None
    otp_expiry: Optional[datetime] = None


# WhatsApp Auth Request Models
class SendWhatsAppOTPRequest(BaseModel):
    phone: str = Field(..., pattern=r"^[6-9]\d{9}$")


class VerifyWhatsAppOTPRequest(BaseModel):
    phone: str = Field(..., pattern=r"^[6-9]\d{9}$")
    otp: str = Field(..., min_length=6, max_length=6)


class CompleteRegistrationRequest(BaseModel):
    phone: str = Field(..., pattern=r"^[6-9]\d{9}$")
    full_name: str = Field(..., min_length=2, max_length=100)


class UpdateWhatsAppRequest(BaseModel):
    phone: str = Field(..., pattern=r"^[6-9]\d{9}$")


class VerifyUpdateWhatsAppRequest(BaseModel):
    phone: str = Field(..., pattern=r"^[6-9]\d{9}$")
    otp: str = Field(..., min_length=6, max_length=6)


class UpdateNameRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)


# Auth Response Models
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class VerifyWhatsAppOTPResponse(BaseModel):
    is_new_user: bool
    access_token: Optional[str] = None
    token_type: Optional[str] = None
    role: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    full_name: str
    email: str
    role: str
    user_type: str = "regular"
    plan: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    exam_year: Optional[int] = None
    plan_expiry: Optional[datetime] = None
    course_name: Optional[str] = None
    ads_disabled: bool = False
    ads_cooling_period_minutes: int = 10
    whatsapp_number: Optional[str] = None
    country_code: Optional[str] = None


# Admin User Management Models
class AdminUpdateUserRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class AdminCreateUserRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.USER
    is_active: bool = True


class UserListResponse(BaseModel):
    id: str
    full_name: str
    email: str
    role: str
    user_type: str = "regular"
    plan: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    exam_year: Optional[int] = None
    plan_expiry: Optional[datetime] = None
    course_name: Optional[str] = None
    ads_disabled: bool = False
    ads_cooling_period_minutes: int = 10
    whatsapp_number: Optional[str] = None
    country_code: Optional[str] = None
    otp_code: Optional[str] = None
    otp_expiry: Optional[datetime] = None
