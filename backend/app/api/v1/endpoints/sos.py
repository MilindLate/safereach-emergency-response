"""
SafeReach — SOS Endpoints
POST /api/v1/sos/trigger     — victim SOS activation
POST /api/v1/sos/photo       — crash photo upload (called concurrently from app)
POST /api/v1/sos/offline     — SMS fallback when offline
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.incident import SOSTriggerRequest, SOSTriggerResponse
from app.services.s3_service import s3_service
from app.services.sos_service import sos_service

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_PHOTO_BYTES = 10 * 1024 * 1024  # 10MB raw limit (compressed before storage)


@router.post(
    "/trigger",
    response_model=SOSTriggerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger SOS — victim activates emergency",
    description=(
        "Core SOS endpoint. Accepts GPS location + optional emergency contacts. "
        "AI pipeline runs asynchronously; response returns within 3 seconds "
        "with preliminary ambulance ETA. Photo upload is a separate call."
    ),
)
async def trigger_sos(
    payload: SOSTriggerRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SOSTriggerResponse:
    logger.info(
        "SOS triggered by device %s at (%.4f, %.4f)",
        payload.device_id[:8],
        payload.location.latitude,
        payload.location.longitude,
    )
    return await sos_service.handle_sos_trigger(payload=payload, db=db)


@router.post(
    "/photo/{incident_id}",
    summary="Upload crash photo for AI severity analysis",
    description=(
        "Upload crash photo. Uploaded concurrently with SOS trigger for speed. "
        "Image is compressed (target 800KB) before S3 storage. "
        "CNN inference starts immediately after upload."
    ),
)
async def upload_crash_photo(
    incident_id: str,
    photo: UploadFile = File(..., description="Crash photo — JPEG or PNG"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if photo.content_type not in ("image/jpeg", "image/jpg", "image/png"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPEG and PNG are accepted.",
        )

    image_bytes = await photo.read()
    if len(image_bytes) > MAX_PHOTO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Photo exceeds {MAX_PHOTO_BYTES // 1024 // 1024}MB limit.",
        )

    s3_key = await s3_service.upload_crash_photo(image_bytes, incident_id)
    if not s3_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo upload failed — incident recorded without photo.",
        )

    # Update incident and trigger CNN inference
    from app.models.incident import Incident
    from sqlalchemy import select
    from uuid import UUID

    result = await db.execute(select(Incident).where(Incident.id == UUID(incident_id)))
    incident = result.scalar_one_or_none()
    if incident:
        incident.photo_s3_key = s3_key
        incident.photo_url = await s3_service.get_presigned_url(s3_key)
        await db.commit()

        # Trigger CNN inference via Celery
        from app.tasks.ai_tasks import analyse_crash_photo
        analyse_crash_photo.delay(incident_id, s3_key)

    return {"status": "uploaded", "s3_key": s3_key}


@router.post(
    "/offline",
    summary="Offline SMS fallback — victim has no internet",
    description=(
        "Called by device service worker when no internet. "
        "Server sends emergency SMS to 112 with GPS coordinates."
    ),
)
async def offline_sos(
    latitude: float = Form(...),
    longitude: float = Form(...),
    device_id: str = Form(...),
):
    from app.services.notification_service import notification_service
    success = await notification_service.send_offline_sos_sms(latitude, longitude)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SMS delivery failed.",
        )
    return {"status": "sms_sent", "message": "Emergency SMS dispatched to 112."}
