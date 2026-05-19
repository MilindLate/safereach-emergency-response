"""
SafeReach — Analytics Endpoints
GET /api/v1/incidents/stats/summary  — dashboard KPI stats
GET /api/v1/incidents/hotspots       — hotspot grid for heatmap panel
"""

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_dispatcher
from app.models.incident import Incident, IncidentStatus, AmbulanceUnit, AmbulanceStatus

router = APIRouter()


@router.get("/stats/summary", summary="Dashboard KPI summary")
async def get_stats_summary(
    dispatcher: dict = Depends(require_dispatcher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Real-time KPI counts for the dispatcher stats bar."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Active incidents (not closed)
    active_q = await db.execute(
        select(func.count()).where(
            Incident.status.notin_([IncidentStatus.CLOSED])
        )
    )
    active_count = active_q.scalar_one()

    # Critical incidents
    critical_q = await db.execute(
        select(func.count()).where(
            and_(
                Incident.severity == "critical",
                Incident.status.notin_([IncidentStatus.CLOSED]),
            )
        )
    )
    critical_count = critical_q.scalar_one()

    # Free ambulances
    free_q = await db.execute(
        select(func.count()).where(
            and_(AmbulanceUnit.status == AmbulanceStatus.FREE, AmbulanceUnit.is_active == True)
        )
    )
    free_ambulances = free_q.scalar_one()

    # Average dispatch time (reported → dispatched, today)
    dispatch_q = await db.execute(
        select(
            func.avg(
                func.extract("epoch", Incident.dispatched_at - Incident.created_at) / 60
            )
        ).where(
            and_(
                Incident.dispatched_at.isnot(None),
                Incident.created_at >= today_start,
            )
        )
    )
    avg_dispatch = dispatch_q.scalar_one()

    # Average total response time (created → on_scene, today)
    response_q = await db.execute(
        select(
            func.avg(
                func.extract("epoch", Incident.on_scene_at - Incident.created_at) / 60
            )
        ).where(
            and_(
                Incident.on_scene_at.isnot(None),
                Incident.created_at >= today_start,
            )
        )
    )
    avg_response = response_q.scalar_one()

    # Resolved today
    resolved_q = await db.execute(
        select(func.count()).where(
            and_(
                Incident.status == IncidentStatus.CLOSED,
                Incident.closed_at >= today_start,
            )
        )
    )
    resolved_today = resolved_q.scalar_one()

    return {
        "active_incidents":  active_count,
        "critical_count":    critical_count,
        "free_ambulances":   free_ambulances,
        "avg_dispatch_min":  round(avg_dispatch, 1) if avg_dispatch else "—",
        "avg_response_min":  round(avg_response, 1) if avg_response else "—",
        "resolved_today":    resolved_today,
    }


@router.get("/hotspots", summary="Accident hotspot grid for heatmap")
async def get_hotspots(
    limit: int = 50,
    dispatcher: dict = Depends(require_dispatcher),
) -> list:
    """
    Returns top-N hotspot locations with XGBoost risk scores.
    In production: fetched from Redis cache (refreshed every 6h by Celery beat).
    Stub: returns representative Indian highway hotspots.
    """
    from app.core.redis import cache_get
    cached = await cache_get("hotspot:grid:top50")
    if cached:
        return cached[:limit]

    # Stub data — replaced by real Celery-generated predictions in production
    hotspots = [
        {"lat": 28.61, "lng": 77.23, "risk": 0.82, "road": "NH-48",   "label": "Dhaula Kuan, Delhi"},
        {"lat": 19.07, "lng": 72.87, "risk": 0.74, "road": "NH-8",    "label": "Bhiwandi, Maharashtra"},
        {"lat": 12.97, "lng": 77.59, "risk": 0.68, "road": "ORR",     "label": "Silk Board Jn, Bengaluru"},
        {"lat": 22.57, "lng": 88.36, "risk": 0.63, "road": "NH-6",    "label": "Ultadanga, Kolkata"},
        {"lat": 17.38, "lng": 78.47, "risk": 0.55, "road": "ORR",     "label": "LB Nagar, Hyderabad"},
        {"lat": 13.08, "lng": 80.27, "risk": 0.49, "road": "GST Rd",  "label": "Tambaram, Chennai"},
        {"lat": 26.85, "lng": 75.79, "risk": 0.44, "road": "NH-48",   "label": "Ajmer Rd, Jaipur"},
        {"lat": 23.02, "lng": 72.58, "risk": 0.38, "road": "SH-17",   "label": "Sarkhej, Ahmedabad"},
        {"lat": 21.25, "lng": 81.65, "risk": 0.33, "road": "NH-30",   "label": "Raipur Bypass"},
        {"lat": 26.85, "lng": 80.94, "risk": 0.29, "road": "NH-27",   "label": "Lucknow Ring Road"},
    ]
    return hotspots[:limit]
