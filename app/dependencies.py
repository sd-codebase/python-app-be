from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.database import get_database
from app.utils.security import decode_token
from app.models.user import UserRole

security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    db = get_database()

    # Check if token is blacklisted
    blacklisted = await db.blacklisted_tokens.find_one({"token": token})
    if blacklisted:
        raise credentials_exception

    user = await db.users.find_one({"id": user_id})

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(current_user: dict = Depends(get_current_user)):
    """Get current active and verified user."""
    if not current_user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active"
        )

    if not current_user.get("is_verified"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not verified"
        )

    return current_user


async def require_admin(current_user: dict = Depends(get_current_active_user)):
    """Require admin role."""
    if current_user.get("role") != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return current_user
