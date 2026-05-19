"""hospitals.py — Hospital search endpoint."""
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_Distance, ST_SetSRID, ST_MakePoint
from geoalchemy2.shape import to_shape

from app.core.database import get_db
from app.models.incident import Hospital
from app.schemas.incident import HospitalInfo

router = APIRouter()


@router.get("/nearby", response_model=List[HospitalInfo], summary="Nearest hospitals for victim app")
async def nearby_hospitals(
    latitude: float = Query(...),
    longitude: float = Query(...),
    limit: int = Query(5, le=20),
    db: AsyncSession = Depends(get_db),
) -> List[HospitalInfo]:
    point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
    result = await db.execute(
        select(Hospital)
        .where(Hospital.is_active == True)
        .order_by(ST_Distance(Hospital.location, point))
        .limit(limit)
    )
    hospitals = result.scalars().all()

    out = []
    for h in hospitals:
        shape = to_shape(h.location)
        out.append(HospitalInfo(
            id=h.id, name=h.name,
            latitude=shape.y, longitude=shape.x,
            phone=h.phone, trauma_level=h.trauma_level,
            beds_available=h.beds_available,
        ))
    return out
