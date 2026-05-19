"""SafeReach — Notification Celery Tasks"""
import asyncio
import logging
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.notification_tasks.schedule_hospital_prealert")
def schedule_hospital_prealert(incident_id: str) -> dict:
    """Triggered N minutes before ambulance arrival to alert hospital trauma bay."""
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.models.incident import Incident
        from app.services.notification_service import notification_service
        from sqlalchemy import select
        from uuid import UUID

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Incident).where(Incident.id == UUID(incident_id)))
            incident = result.scalar_one_or_none()
            if incident and incident.hospital:
                await notification_service.send_hospital_prealert(
                    hospital=incident.hospital,
                    incident=incident,
                    eta_minutes=10,
                )
    asyncio.run(_run())
    return {"status": "prealert_sent", "incident_id": incident_id}
