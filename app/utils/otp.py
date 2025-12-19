import random
import string
from datetime import datetime, timedelta

from app.config import settings


def generate_otp() -> str:
    """Generate a 6-digit OTP."""
    return "".join(random.choices(string.digits, k=6))


def get_otp_expiry() -> datetime:
    """Get OTP expiry timestamp."""
    return datetime.utcnow() + timedelta(minutes=settings.otp_expire_minutes)


def is_otp_valid(otp_expiry: datetime) -> bool:
    """Check if OTP is still valid (not expired)."""
    return datetime.utcnow() < otp_expiry
