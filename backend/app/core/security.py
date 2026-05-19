"""
SafeReach — JWT Security
Device tokens (long-lived) for mobile apps + short JWT for web dashboard.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import logging

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


# ─── Token creation ───────────────────────────────────────────────────────────

def create_access_token(subject: str, role: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": subject, "role": role, "exp": expire, "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_device_token(device_id: str) -> str:
    """Long-lived token for victim/crew mobile apps — no login required after setup."""
    return create_access_token(
        subject=device_id,
        role="device",
        expires_delta=timedelta(days=settings.JWT_DEVICE_TOKEN_EXPIRE_DAYS),
    )


def create_family_tracker_token(incident_id: str) -> str:
    """Short-lived signed token for no-login family tracking page."""
    return create_access_token(
        subject=incident_id,
        role="tracker",
        expires_delta=timedelta(hours=24),
    )


# ─── Token verification ───────────────────────────────────────────────────────

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ─── FastAPI dependencies ─────────────────────────────────────────────────────

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    return decode_token(credentials.credentials)


async def require_dispatcher(current: dict = Depends(get_current_user)) -> dict:
    if current.get("role") not in ("dispatcher", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dispatcher access required.")
    return current


async def require_device(current: dict = Depends(get_current_user)) -> dict:
    if current.get("role") not in ("device", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Device token required.")
    return current


# ─── Password utils (for dispatcher web accounts) ────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
