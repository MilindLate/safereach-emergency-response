"""
SafeReach — Dispatch Endpoints
POST /api/v1/dispatch/assign          — dispatcher assigns ambulance to incident
GET  /api/v1/dispatch/candidates/{id} — get nearby ambulances for an incident
PUT  /api/v1/dispatch/status/{id}     — update incident lifecycle status
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import publish_event
from app.core.security import require_dispatcher
from app.models.incident import AmbulanceStatus, AmbulanceUnit, Hospital, Incident, IncidentStatus
from app.schemas.incident import AmbulanceUnitStatus, DispatchAssignRequest, DispatchAssignResponse
from app.services.routing_service import routing_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/assign",
    response_model=DispatchAssignResponse,
    summary="Assign ambulance unit to an incident",
    description=(
        "One-click unit assignment from dispatcher dashboard. "
        "Marks incident as DISPATCHED, ambulance as ROUTING, "
        "pushes optimised route to crew app, schedules hospital pre-alert."
    ),
)
async def assign_ambulance(
    payload: DispatchAssignRequest,
    dispatcher: dict = Depends(require_dispatcher),
    db: AsyncSession = Depends(get_db),
) -> DispatchAssignResponse:

    # Load incident and ambulance
    incident = await db.get(Incident, payload.incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found.")
    if incident.status not in (IncidentStatus.REPORTED,):
        raise HTTPException(
            status_code=409,
            detail=f"Incident already in status '{incident.status.value}' — cannot reassign.",
        )

    ambulance = await db.get(AmbulanceUnit, payload.ambulance_unit_id)
    if not ambulance:
        raise HTTPException(status_code=404, detail="Ambulance unit not found.")
    if ambulance.status != AmbulanceStatus.FREE:
        raise HTTPException(status_code=409, detail=f"Unit {ambulance.unit_code} is not free.")

    # Compute route
    from geoalchemy2.shape import to_shape
    from app.schemas.incident import LocationPoint

    incident_shape = to_shape(incident.location)
    incident_loc = LocationPoint(latitude=incident_shape.y, longitude=incident_shape.x)

    ambulance_loc = None
    route_info = {"duration_seconds": 0, "polyline": ""}
    if ambulance.location is not None:
        amb_shape = to_shape(ambulance.location)
        ambulance_loc = LocationPoint(latitude=amb_shape.y, longitude=amb_shape.x)
        route_info = await routing_service.get_route(ambulance_loc, incident_loc)

    # Update database
    from datetime import datetime, timezone
    incident.assigned_ambulance_id = ambulance.id
    incident.status = IncidentStatus.DISPATCHED
    incident.dispatched_at = datetime.now(timezone.utc)
    ambulance.status = AmbulanceStatus.ROUTING
    await db.commit()

    eta_seconds = route_info["duration_seconds"]

    # Push to crew app via Redis → Socket.io
    await publish_event(
        channel=f"safereach:ambulance:{ambulance.id}",
        event={
            "type": "dispatch",
            "incident_id": str(incident.id),
            "route_polyline": route_info.get("polyline", ""),
            "eta_seconds": eta_seconds,
            "severity": incident.severity.value,
            "destination_lat": incident_shape.y,
            "destination_lng": incident_shape.x,
        },
    )

    # Update dispatcher dashboard
    await publish_event(
        channel="safereach:incidents",
        event={
            "type": "incident_updated",
            "incident_id": str(incident.id),
            "status": "dispatched",
            "ambulance_code": ambulance.unit_code,
            "eta_seconds": eta_seconds,
        },
    )

    # Schedule hospital pre-alert via Celery
    from app.tasks.notification_tasks import schedule_hospital_prealert
    if incident.receiving_hospital_id:
        eta_minutes = max(1, eta_seconds // 60)
        prealert_delay = max(0, eta_seconds - (settings.HOSPITAL_PREALERT_MINUTES_BEFORE * 60))
        schedule_hospital_prealert.apply_async(
            args=[str(incident.id)],
            countdown=prealert_delay,
        )

    logger.info(
        "Dispatcher %s assigned unit %s to incident %s (ETA %ds)",
        dispatcher.get("sub", "unknown")[:8],
        ambulance.unit_code,
        incident.id,
        eta_seconds,
    )

    return DispatchAssignResponse(
        incident_id=incident.id,
        ambulance_unit_id=ambulance.id,
        ambulance_unit_code=ambulance.unit_code,
        route_polyline=route_info.get("polyline"),
        eta_seconds=eta_seconds,
    )


@router.get(
    "/candidates/{incident_id}",
    response_model=list[AmbulanceUnitStatus],
    summary="Get nearest available ambulances for an incident",
)
async def get_candidates(
    incident_id: UUID,
    limit: int = 5,
    dispatcher: dict = Depends(require_dispatcher),
    db: AsyncSession = Depends(get_db),
) -> list[AmbulanceUnitStatus]:
    from geoalchemy2.functions import ST_Distance, ST_SetSRID, ST_MakePoint
    from geoalchemy2.shape import to_shape

    incident = await db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found.")

    inc_shape = to_shape(incident.location)
    point = ST_SetSRID(ST_MakePoint(inc_shape.x, inc_shape.y), 4326)

    result = await db.execute(
        select(AmbulanceUnit)
        .where(
            AmbulanceUnit.status == AmbulanceStatus.FREE,
            AmbulanceUnit.is_active == True,
            AmbulanceUnit.location.isnot(None),
        )
        .order_by(ST_Distance(AmbulanceUnit.location, point))
        .limit(limit)
    )
    units = result.scalars().all()

    out = []
    for unit in units:
        if unit.location is not None:
            s = to_shape(unit.location)
            out.append(
                AmbulanceUnitStatus(
                    id=unit.id,
                    unit_code=unit.unit_code,
                    status=unit.status.value,
                    latitude=s.y,
                    longitude=s.x,
                )
            )
    return out


@router.put(
    "/status/{incident_id}",
    summary="Update incident lifecycle status",
)
async def update_incident_status(
    incident_id: UUID,
    new_status: str,
    dispatcher: dict = Depends(require_dispatcher),
    db: AsyncSession = Depends(get_db),
):
    incident = await db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found.")

    try:
        incident.status = IncidentStatus(new_status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")

    from datetime import datetime, timezone
    if new_status == IncidentStatus.CLOSED.value:
        incident.closed_at = datetime.now(timezone.utc)
        if incident.assigned_ambulance_id:
            ambulance = await db.get(AmbulanceUnit, incident.assigned_ambulance_id)
            if ambulance:
                ambulance.status = AmbulanceStatus.FREE

    await db.commit()

    await publish_event(
        channel="safereach:incidents",
        event={
            "type": "incident_updated",
            "incident_id": str(incident.id),
            "status": new_status,
        },
    )
    return {"incident_id": str(incident_id), "status": new_status}


# Late import to avoid circular dependency
from app.core.config import settings  # noqa: E402
