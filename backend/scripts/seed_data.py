#!/usr/bin/env python3
"""
SafeReach — Development Seed Script
Populates: 1 dispatcher, 5 hospitals, 8 ambulances, 3 sample incidents.
Run: docker compose exec backend python scripts/seed_data.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal, init_db
from app.core.security import hash_password
from app.models.incident import (
    AmbulanceStatus, AmbulanceUnit, Dispatcher,
    Hospital, Incident, IncidentStatus, SeverityLevel,
)

# ── Seed data ─────────────────────────────────────────────────────────────────

HOSPITALS = [
    dict(name="AIIMS Nagpur",          lat=21.1458, lon=79.0882, trauma_level=1, beds_available=12, phone="+917122xxx001"),
    dict(name="Govt Medical College Nagpur", lat=21.1320, lon=79.0800, trauma_level=1, beds_available=8,  phone="+917122xxx002"),
    dict(name="Orange City Hospital",  lat=21.1550, lon=79.0950, trauma_level=2, beds_available=20, phone="+917122xxx003"),
    dict(name="Alexis Hospital",       lat=21.1210, lon=79.0710, trauma_level=2, beds_available=15, phone="+917122xxx004"),
    dict(name="Wockhardt Hospital",    lat=21.1660, lon=79.1010, trauma_level=2, beds_available=10, phone="+917122xxx005"),
]

AMBULANCES = [
    dict(unit_code="MH-31-AMB-001", lat=21.1300, lon=79.0750, status=AmbulanceStatus.FREE),
    dict(unit_code="MH-31-AMB-002", lat=21.1500, lon=79.1000, status=AmbulanceStatus.FREE),
    dict(unit_code="MH-31-AMB-003", lat=21.1100, lon=79.0600, status=AmbulanceStatus.FREE),
    dict(unit_code="MH-31-AMB-004", lat=21.1700, lon=79.1100, status=AmbulanceStatus.FREE),
    dict(unit_code="MH-31-AMB-005", lat=21.1400, lon=79.0900, status=AmbulanceStatus.FREE),
    dict(unit_code="MH-31-BLS-001", lat=21.1250, lon=79.0820, status=AmbulanceStatus.FREE),
    dict(unit_code="MH-31-BLS-002", lat=21.1600, lon=79.0950, status=AmbulanceStatus.FREE),
    dict(unit_code="MH-31-BLS-003", lat=21.1350, lon=79.0700, status=AmbulanceStatus.FREE),
]

SAMPLE_INCIDENTS = [
    dict(lat=21.1420, lon=79.0870, severity=SeverityLevel.CRITICAL, status=IncidentStatus.REPORTED,  address="NH-44, near Koradi junction, Nagpur"),
    dict(lat=21.1280, lon=79.0760, severity=SeverityLevel.MEDIUM,   status=IncidentStatus.DISPATCHED, address="Wardha Road, Dharampeth, Nagpur"),
    dict(lat=21.1550, lon=79.0990, severity=SeverityLevel.LOW,      status=IncidentStatus.CLOSED,    address="Ring Road, Manewada, Nagpur"),
]


async def seed():
    await init_db()

    async with AsyncSessionLocal() as db:
        # ── Dispatcher ────────────────────────────────────────────────────────
        existing = await db.execute(
            __import__("sqlalchemy").select(Dispatcher).where(Dispatcher.email == "dispatcher@safereach.dev")
        )
        if not existing.scalar_one_or_none():
            dispatcher = Dispatcher(
                email="dispatcher@safereach.dev",
                hashed_password=hash_password("SafeReach2026!"),
                full_name="Control Room Operator",
                is_active=True,
            )
            db.add(dispatcher)
            print("✓ Dispatcher created: dispatcher@safereach.dev / SafeReach2026!")
        else:
            print("· Dispatcher already exists, skipping.")

        # ── Hospitals ─────────────────────────────────────────────────────────
        for h in HOSPITALS:
            point = f"SRID=4326;POINT({h['lon']} {h['lat']})"
            hospital = Hospital(
                name=h["name"],
                location=point,
                phone=h["phone"],
                trauma_level=h["trauma_level"],
                beds_available=h["beds_available"],
                is_active=True,
            )
            db.add(hospital)
        print(f"✓ {len(HOSPITALS)} hospitals seeded.")

        await db.flush()

        # ── Ambulances ────────────────────────────────────────────────────────
        for a in AMBULANCES:
            point = f"SRID=4326;POINT({a['lon']} {a['lat']})"
            unit = AmbulanceUnit(
                unit_code=a["unit_code"],
                location=point,
                status=a["status"],
                driver_name=f"Driver ({a['unit_code']})",
                is_active=True,
            )
            db.add(unit)
        print(f"✓ {len(AMBULANCES)} ambulance units seeded.")

        # ── Sample incidents ──────────────────────────────────────────────────
        for inc_data in SAMPLE_INCIDENTS:
            point = f"SRID=4326;POINT({inc_data['lon']} {inc_data['lat']})"
            incident = Incident(
                location=point,
                severity=inc_data["severity"],
                status=inc_data["status"],
                address_approx=inc_data["address"],
                device_id="seed-device-00000000000001",
                victim_language="en",
                cnn_score={"critical": 0.87, "medium": 0.62, "low": 0.21}.get(inc_data["severity"].value, 0.5),
                cnn_confidence=0.91,
            )
            db.add(incident)
        print(f"✓ {len(SAMPLE_INCIDENTS)} sample incidents seeded.")

        await db.commit()
        print("\n🚀 SafeReach dev seed complete.")
        print("   Dashboard: http://localhost:3000")
        print("   API docs:  http://localhost:8000/api/docs")


if __name__ == "__main__":
    asyncio.run(seed())
