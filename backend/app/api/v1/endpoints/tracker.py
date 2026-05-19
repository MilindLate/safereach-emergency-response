"""tracker.py — Family tracker data endpoint (no login required — JWT-signed token)."""
from fastapi import APIRouter, HTTPException, Query
from jose import JWTError, jwt

from app.core.config import settings
from app.schemas.incident import FamilyTrackerData

router = APIRouter()


@router.get("/data", response_model=FamilyTrackerData, summary="Family tracker — live incident data")
async def get_tracker_data(token: str = Query(..., description="Signed tracker token from SMS")):
    """
    No authentication required — token is JWT-signed with incident_id.
    Shared via SMS with emergency contacts. Expires in 24 hours.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("role") != "tracker":
            raise HTTPException(status_code=403, detail="Invalid tracker token.")
        incident_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Expired or invalid tracker link.")

    # In production: fetch from DB + Redis for live positions
    # Stub response for now
    from datetime import datetime, timezone
    from uuid import UUID
    return FamilyTrackerData(
        incident_id=UUID(incident_id),
        victim_latitude=0.0,
        victim_longitude=0.0,
        incident_status="en_route",
        last_updated=datetime.now(timezone.utc),
    )
