"""ambulances.py — Ambulance location updates from crew app."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import publish_event
from app.core.security import require_device
from app.models.incident import AmbulanceUnit
from app.schemas.incident import AmbulanceLocationUpdate

router = APIRouter()


@router.put("/location", summary="Update ambulance GPS location (30s interval from crew app)")
async def update_ambulance_location(
    payload: AmbulanceLocationUpdate,
    current: dict = Depends(require_device),
    db: AsyncSession = Depends(get_db),
):
    unit = await db.get(AmbulanceUnit, payload.unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Ambulance unit not found.")

    point_wkb = f"SRID=4326;POINT({payload.location.longitude} {payload.location.latitude})"
    unit.location = point_wkb
    await db.commit()

    # Push live location to Socket.io rooms
    await publish_event(
        channel=f"safereach:ambulance:location:{unit.id}",
        event={
            "type": "location_update",
            "unit_id": str(unit.id),
            "unit_code": unit.unit_code,
            "latitude": payload.location.latitude,
            "longitude": payload.location.longitude,
            "speed_kmh": payload.speed_kmh,
        },
    )
    return {"status": "ok"}


@router.put("/status", summary="Update ambulance operational status")
async def update_ambulance_status(
    unit_id: UUID,
    status: str,
    current: dict = Depends(require_device),
    db: AsyncSession = Depends(get_db),
):
    """Called by crew app when marking unit free/on_scene."""
    unit = await db.get(AmbulanceUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Ambulance unit not found.")
    try:
        unit.status = AmbulanceStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    await db.commit()
    await publish_event(
        channel="safereach:ambulances",
        event={"type": "status_update", "unit_id": str(unit_id), "status": status},
    )
    return {"status": "ok", "unit_code": unit.unit_code, "new_status": status}


@router.get("/", summary="List all active ambulance units")
async def list_ambulances(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from geoalchemy2.shape import to_shape
    result = await db.execute(select(AmbulanceUnit).where(AmbulanceUnit.is_active == True))
    units = result.scalars().all()
    out = []
    for unit in units:
        lat, lng = None, None
        if unit.location is not None:
            try:
                s = to_shape(unit.location); lat, lng = s.y, s.x
            except Exception:
                pass
        out.append({"id": str(unit.id), "unit_code": unit.unit_code,
                    "status": unit.status.value, "latitude": lat, "longitude": lng})
    return out
