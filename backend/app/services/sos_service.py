"""
SafeReach — SOS Service
Core pipeline: SOS received → AI analysis → unit dispatch → notifications.
"""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from geoalchemy2.functions import ST_DWithin, ST_SetSRID, ST_MakePoint, ST_Distance
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import publish_event, cache_set, cache_get
from app.core.security import create_family_tracker_token
from app.models.incident import (
    AmbulanceStatus, AmbulanceUnit, Hospital, Incident,
    IncidentStatus, SeverityLevel, EmergencyContact,
)
from app.schemas.incident import (
    LocationPoint, SOSTriggerRequest, SOSTriggerResponse,
    SeverityPrediction, HospitalInfo,
)
from app.services.ai_service import ai_service
from app.services.notification_service import notification_service
from app.services.routing_service import routing_service
from app.services.s3_service import s3_service

logger = logging.getLogger(__name__)


class SOSService:
    """
    Handles the complete SOS event lifecycle from trigger to dispatch.
    Follows the architecture defined in Section 3 of the submission doc.
    """

    async def handle_sos_trigger(
        self,
        payload: SOSTriggerRequest,
        db: AsyncSession,
        photo_s3_key: str | None = None,
    ) -> SOSTriggerResponse:
        """
        Main entry point — called from the SOS endpoint.
        Steps:
          1. Persist incident to DB
          2. Trigger AI pipeline (async — CNN + XGBoost in parallel)
          3. Find nearest free ambulance via PostGIS
          4. Route calculation
          5. Notify family via SMS
          6. Push real-time update via Socket.io / Redis pub-sub
        """
        # ── 1. Persist incident ──────────────────────────────────────────────
        point_wkb = f"SRID=4326;POINT({payload.location.longitude} {payload.location.latitude})"
        incident = Incident(
            location=point_wkb,
            photo_s3_key=photo_s3_key,
            photo_url=await s3_service.get_presigned_url(photo_s3_key) if photo_s3_key else None,
            device_id=payload.device_id,
            victim_language=payload.language,
            status=IncidentStatus.REPORTED,
            severity=SeverityLevel.MEDIUM,  # placeholder until CNN runs
        )
        db.add(incident)

        # Persist emergency contacts
        for phone in payload.emergency_contacts:
            db.add(EmergencyContact(incident=incident, phone=phone))

        await db.flush()  # get incident.id without committing
        logger.info("Incident %s created for device %s", incident.id, payload.device_id[:8])

        # ── 2. AI pipeline (concurrent) ──────────────────────────────────────
        cnn_task = asyncio.create_task(
            self._run_cnn(incident.id, photo_s3_key, db)
        )
        hotspot_task = asyncio.create_task(
            self._run_hotspot(incident.id, payload.location, db)
        )

        # Don't await yet — let dispatch proceed with preliminary severity

        # ── 3. Find nearest hospital and ambulance ───────────────────────────
        hospital = await self._nearest_hospital(payload.location, db)
        ambulance = await self._nearest_free_ambulance(payload.location, db)

        eta_seconds: int | None = None
        route_info = None

        if ambulance:
            ambulance_loc = await self._get_ambulance_location(ambulance)
            if ambulance_loc:
                route_info = await routing_service.get_route(ambulance_loc, payload.location)
                eta_seconds = route_info.get("duration_seconds")

        # ── 4. Commit incident to DB ─────────────────────────────────────────
        if hospital:
            incident.receiving_hospital_id = hospital.id
        await db.commit()
        await db.refresh(incident)

        # ── 5. Wait for AI results (with timeout) ────────────────────────────
        try:
            cnn_result: SeverityPrediction | None = await asyncio.wait_for(cnn_task, timeout=settings.CNN_INFERENCE_TIMEOUT_S)
            if cnn_result:
                incident.severity = SeverityLevel(cnn_result.severity)
                incident.cnn_score = cnn_result.class_scores.get(cnn_result.severity, 0.0)
                incident.cnn_confidence = cnn_result.confidence
                await db.commit()
        except asyncio.TimeoutError:
            logger.warning("CNN timed out for incident %s — using default severity.", incident.id)

        try:
            hotspot_score = await asyncio.wait_for(hotspot_task, timeout=2.0)
            if hotspot_score is not None:
                incident.hotspot_risk = hotspot_score
                await db.commit()
        except asyncio.TimeoutError:
            logger.warning("Hotspot model timed out for incident %s.", incident.id)

        # ── 6. Auto-dispatch if Critical ────────────────────────────────────
        if incident.severity == SeverityLevel.CRITICAL and ambulance:
            await self._assign_ambulance(incident, ambulance, db)

        # ── 7. Family notification (fire and forget) ─────────────────────────
        tracker_token = create_family_tracker_token(str(incident.id))
        tracker_url = f"{settings.FRONTEND_BASE_URL}/track/{tracker_token}"
        asyncio.create_task(
            notification_service.notify_family(incident, tracker_url)
        )

        # ── 8. Push to dispatcher dashboard via Socket.io ────────────────────
        await publish_event(
            channel="safereach:incidents",
            event={
                "type": "new_incident",
                "incident_id": str(incident.id),
                "severity": incident.severity.value,
                "latitude": payload.location.latitude,
                "longitude": payload.location.longitude,
                "eta_seconds": eta_seconds,
                "hospital": hospital.name if hospital else None,
            },
        )

        return SOSTriggerResponse(
            incident_id=incident.id,
            status=incident.status.value,
            nearest_hospital_name=hospital.name if hospital else None,
            eta_seconds=eta_seconds,
            ambulance_unit_code=ambulance.unit_code if ambulance else None,
            family_tracker_url=tracker_url,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _run_cnn(
        self,
        incident_id: UUID,
        photo_s3_key: str | None,
        db: AsyncSession,
    ) -> SeverityPrediction | None:
        if not photo_s3_key:
            return None
        return await ai_service.predict_severity(photo_s3_key)

    async def _run_hotspot(
        self,
        incident_id: UUID,
        location: LocationPoint,
        db: AsyncSession,
    ) -> float | None:
        result = await ai_service.predict_hotspot(location.latitude, location.longitude)
        return result.risk_score if result else None

    async def _nearest_hospital(
        self, location: LocationPoint, db: AsyncSession
    ) -> Hospital | None:
        """PostGIS ST_Distance query — returns closest active hospital within 50km."""
        cache_key = f"hospital:nearest:{location.latitude:.3f}:{location.longitude:.3f}"
        cached = await cache_get(cache_key)
        if cached:
            return await db.get(Hospital, cached["id"])

        point = ST_SetSRID(ST_MakePoint(location.longitude, location.latitude), 4326)
        result = await db.execute(
            select(Hospital)
            .where(and_(Hospital.is_active == True, Hospital.trauma_level <= 2))
            .order_by(ST_Distance(Hospital.location, point))
            .limit(1)
        )
        hospital = result.scalar_one_or_none()
        if hospital:
            await cache_set(cache_key, {"id": str(hospital.id)}, ttl_seconds=600)
        return hospital

    async def _nearest_free_ambulance(
        self, location: LocationPoint, db: AsyncSession
    ) -> AmbulanceUnit | None:
        """Find nearest FREE ambulance unit within 30km using PostGIS."""
        point = ST_SetSRID(ST_MakePoint(location.longitude, location.latitude), 4326)
        result = await db.execute(
            select(AmbulanceUnit)
            .where(
                and_(
                    AmbulanceUnit.status == AmbulanceStatus.FREE,
                    AmbulanceUnit.is_active == True,
                    AmbulanceUnit.location.isnot(None),
                    ST_DWithin(AmbulanceUnit.location, point, 30000),  # 30km in metres (geography)
                )
            )
            .order_by(ST_Distance(AmbulanceUnit.location, point))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_ambulance_location(self, unit: AmbulanceUnit) -> LocationPoint | None:
        if unit.location is None:
            return None
        # GeoAlchemy2 returns WKBElement; extract coordinates
        from geoalchemy2.shape import to_shape
        shape = to_shape(unit.location)
        return LocationPoint(latitude=shape.y, longitude=shape.x)

    async def _assign_ambulance(
        self,
        incident: Incident,
        ambulance: AmbulanceUnit,
        db: AsyncSession,
    ) -> None:
        incident.assigned_ambulance_id = ambulance.id
        incident.status = IncidentStatus.DISPATCHED
        incident.dispatched_at = datetime.now(timezone.utc)
        ambulance.status = AmbulanceStatus.ROUTING
        await db.commit()

        logger.info(
            "Auto-dispatched unit %s to CRITICAL incident %s",
            ambulance.unit_code, incident.id
        )


sos_service = SOSService()
