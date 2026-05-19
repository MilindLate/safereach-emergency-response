"""incidents.py — Incident list and detail endpoints for dispatcher dashboard."""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.shape import to_shape

from app.core.database import get_db
from app.core.security import require_dispatcher
from app.models.incident import Incident, IncidentStatus
from app.schemas.incident import IncidentDetail, IncidentSummary
from app.services.s3_service import s3_service

router = APIRouter()


@router.get("/", response_model=List[IncidentSummary], summary="List all incidents (dispatcher)")
async def list_incidents(
    status_filter: str = Query(None, alias="status"),
    limit: int = Query(50, le=200),
    offset: int = 0,
    dispatcher: dict = Depends(require_dispatcher),
    db: AsyncSession = Depends(get_db),
) -> List[IncidentSummary]:
    q = select(Incident).order_by(desc(Incident.created_at)).limit(limit).offset(offset)
    if status_filter:
        q = q.where(Incident.status == IncidentStatus(status_filter))

    result = await db.execute(q)
    incidents = result.scalars().all()

    out = []
    for inc in incidents:
        shape = to_shape(inc.location)
        out.append(IncidentSummary(
            id=inc.id, severity=inc.severity.value, status=inc.status.value,
            cnn_score=inc.cnn_score, hotspot_risk=inc.hotspot_risk,
            latitude=shape.y, longitude=shape.x,
            address_approx=inc.address_approx,
            created_at=inc.created_at, dispatched_at=inc.dispatched_at,
            ambulance_unit_code=inc.ambulance.unit_code if inc.ambulance else None,
            hospital_name=inc.hospital.name if inc.hospital else None,
        ))
    return out


@router.get("/{incident_id}", response_model=IncidentDetail, summary="Get incident detail")
async def get_incident(
    incident_id: UUID,
    dispatcher: dict = Depends(require_dispatcher),
    db: AsyncSession = Depends(get_db),
) -> IncidentDetail:
    incident = await db.get(Incident, incident_id)
    if not incident:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Incident not found.")

    shape = to_shape(incident.location)
    photo_url = await s3_service.get_presigned_url(incident.photo_s3_key) if incident.photo_s3_key else None

    return IncidentDetail(
        id=incident.id, severity=incident.severity.value, status=incident.status.value,
        cnn_score=incident.cnn_score, cnn_confidence=incident.cnn_confidence,
        hotspot_risk=incident.hotspot_risk, latitude=shape.y, longitude=shape.x,
        address_approx=incident.address_approx, photo_url=photo_url,
        created_at=incident.created_at, dispatched_at=incident.dispatched_at,
        ambulance_unit_code=incident.ambulance.unit_code if incident.ambulance else None,
        hospital_name=incident.hospital.name if incident.hospital else None,
        emergency_contacts_notified=sum(
            1 for c in incident.emergency_contacts if c.notified_at is not None
        ),
    )
