"""
SafeReach — Celery AI Tasks
- analyse_crash_photo: runs CNN on uploaded photo, updates DB severity
- refresh_hotspot_grid: regenerates full city-wide hotspot predictions every 6 hours
"""

import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.ai_tasks.analyse_crash_photo",
    bind=True,
    max_retries=2,
    default_retry_delay=5,
)
def analyse_crash_photo(self, incident_id: str, photo_s3_key: str) -> dict:
    """
    Triggered after crash photo upload.
    Runs EfficientNet-B2 CNN inference, updates incident severity in DB,
    and pushes updated severity to dispatcher dashboard via Socket.io.
    """
    try:
        from app.services.ai_service import ai_service
        from app.core.database import AsyncSessionLocal
        from app.models.incident import Incident, SeverityLevel
        from app.core.redis import publish_event
        from sqlalchemy import select
        from uuid import UUID

        async def _run():
            prediction = await ai_service.predict_severity(photo_s3_key)
            if not prediction:
                return {"status": "no_prediction"}

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Incident).where(Incident.id == UUID(incident_id))
                )
                incident = result.scalar_one_or_none()
                if incident:
                    incident.severity = SeverityLevel(prediction.severity)
                    incident.cnn_score = prediction.class_scores.get(prediction.severity, 0.0)
                    incident.cnn_confidence = prediction.confidence
                    await db.commit()
                    logger.info(
                        "CNN: incident %s → %s (conf=%.2f, %.1fms)",
                        incident_id[:8],
                        prediction.severity,
                        prediction.confidence,
                        prediction.inference_ms,
                    )

                    # Push severity update to dashboard
                    await publish_event(
                        channel="safereach:incidents",
                        event={
                            "type": "severity_updated",
                            "incident_id": incident_id,
                            "severity": prediction.severity,
                            "cnn_confidence": prediction.confidence,
                        },
                    )

            return {
                "severity": prediction.severity,
                "confidence": prediction.confidence,
                "inference_ms": prediction.inference_ms,
            }

        return asyncio.run(_run())

    except Exception as exc:
        logger.exception("analyse_crash_photo task failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(name="app.tasks.ai_tasks.refresh_hotspot_grid")
def refresh_hotspot_grid() -> dict:
    """
    Regenerates the accident hotspot prediction grid for the entire service area.
    Runs every 6 hours, stores results in Redis for fast dashboard retrieval.
    """
    logger.info("Hotspot grid refresh started.")
    # In production: iterate over 500m grid cells, run XGBoost, store in Redis GeoHash
    # Stub: returns success
    return {"status": "refreshed", "cells_updated": 0}
