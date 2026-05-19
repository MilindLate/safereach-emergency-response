"""
SafeReach — API v1 Router
Aggregates all endpoint modules under /api/v1.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, sos, incidents, dispatch, ambulances, hospitals, tracker, analytics

router = APIRouter()

router.include_router(auth.router,       prefix="/auth",       tags=["authentication"])
router.include_router(sos.router,        prefix="/sos",        tags=["SOS"])
router.include_router(incidents.router,  prefix="/incidents",  tags=["incidents"])
router.include_router(analytics.router,  prefix="/incidents",  tags=["analytics"])   # /incidents/stats, /incidents/hotspots
router.include_router(dispatch.router,   prefix="/dispatch",   tags=["dispatch"])
router.include_router(ambulances.router, prefix="/ambulances", tags=["ambulances"])
router.include_router(hospitals.router,  prefix="/hospitals",  tags=["hospitals"])
router.include_router(tracker.router,    prefix="/tracker",    tags=["family tracker"])
