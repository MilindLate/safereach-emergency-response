"""
SafeReach — Supporting Endpoints
incidents.py, ambulances.py, hospitals.py, auth.py, tracker.py — combined for brevity.
Each section maps to a separate file in the actual repository.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# auth.py
# ═══════════════════════════════════════════════════════════════════════════════
from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    create_access_token, create_device_token,
    hash_password, verify_password,
)
from app.schemas.incident import (
    DeviceRegisterRequest, DeviceRegisterResponse,
    DispatcherLoginRequest, TokenResponse,
)
from app.core.config import settings

router = APIRouter()


@router.post("/device/register", response_model=DeviceRegisterResponse, summary="Register victim/crew device")
async def register_device(payload: DeviceRegisterRequest) -> DeviceRegisterResponse:
    """
    One-time device registration — returns long-lived device token.
    No user account needed (friction-free for emergencies).
    """
    token = create_device_token(payload.device_id)
    return DeviceRegisterResponse(
        device_token=token,
        expires_in_days=settings.JWT_DEVICE_TOKEN_EXPIRE_DAYS,
    )


@router.post("/dispatcher/login", response_model=TokenResponse, summary="Dispatcher web dashboard login")
async def dispatcher_login(
    payload: DispatcherLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    from app.models.incident import Dispatcher
    from sqlalchemy import select

    result = await db.execute(
        select(Dispatcher).where(Dispatcher.email == payload.email, Dispatcher.is_active == True)
    )
    dispatcher = result.scalar_one_or_none()
    if not dispatcher or not verify_password(payload.password, dispatcher.hashed_password):
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )
    token = create_access_token(str(dispatcher.id), role="dispatcher")
    return TokenResponse(
        access_token=token,
        expires_in_minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    )
