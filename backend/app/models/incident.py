"""
SafeReach — ORM Models
PostgreSQL 15 + PostGIS geometry columns via GeoAlchemy2.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ─── Enums ────────────────────────────────────────────────────────────────────

class SeverityLevel(PyEnum):
    LOW = "low"
    MEDIUM = "medium"
    CRITICAL = "critical"


class IncidentStatus(PyEnum):
    REPORTED = "reported"
    DISPATCHED = "dispatched"
    EN_ROUTE = "en_route"
    ON_SCENE = "on_scene"
    HOSPITAL_HANDOFF = "hospital_handoff"
    CLOSED = "closed"


class AmbulanceStatus(PyEnum):
    FREE = "free"
    ROUTING = "routing"
    ON_SCENE = "on_scene"


# ─── Incident ─────────────────────────────────────────────────────────────────

class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Geography
    location: Mapped[object] = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    address_approx: Mapped[str | None] = mapped_column(String(512))

    # Media
    photo_url: Mapped[str | None] = mapped_column(Text)
    photo_s3_key: Mapped[str | None] = mapped_column(String(512))

    # AI outputs
    severity: Mapped[SeverityLevel] = mapped_column(
        Enum(SeverityLevel), default=SeverityLevel.MEDIUM
    )
    cnn_score: Mapped[float | None] = mapped_column(Float)       # 0.0 – 1.0
    cnn_confidence: Mapped[float | None] = mapped_column(Float)  # model confidence
    hotspot_risk: Mapped[float | None] = mapped_column(Float)    # XGBoost risk score

    # Workflow
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus), default=IncidentStatus.REPORTED, index=True
    )
    assigned_ambulance_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ambulance_units.id"), nullable=True
    )
    receiving_hospital_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=True
    )

    # Device info
    device_id: Mapped[str | None] = mapped_column(String(256))
    victim_language: Mapped[str] = mapped_column(String(10), default="en")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    on_scene_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    emergency_contacts: Mapped[list["EmergencyContact"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )
    ambulance: Mapped["AmbulanceUnit | None"] = relationship(foreign_keys=[assigned_ambulance_id])
    hospital: Mapped["Hospital | None"] = relationship(foreign_keys=[receiving_hospital_id])


# ─── Ambulance Unit ───────────────────────────────────────────────────────────

class AmbulanceUnit(Base):
    __tablename__ = "ambulance_units"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    unit_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    location: Mapped[object] = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    status: Mapped[AmbulanceStatus] = mapped_column(
        Enum(AmbulanceStatus), default=AmbulanceStatus.FREE, index=True
    )

    hospital_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=True
    )
    driver_name: Mapped[str | None] = mapped_column(String(256))
    driver_phone: Mapped[str | None] = mapped_column(String(20))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    base_hospital: Mapped["Hospital | None"] = relationship(foreign_keys=[hospital_id])


# ─── Hospital ─────────────────────────────────────────────────────────────────

class Hospital(Base):
    __tablename__ = "hospitals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    location: Mapped[object] = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    address: Mapped[str | None] = mapped_column(String(512))
    phone: Mapped[str | None] = mapped_column(String(20))

    trauma_level: Mapped[int] = mapped_column(Integer, default=2)  # 1=highest, 3=basic
    beds_available: Mapped[int] = mapped_column(Integer, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


# ─── Emergency Contact ────────────────────────────────────────────────────────

class EmergencyContact(Base):
    __tablename__ = "emergency_contacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False, index=True
    )
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(256))
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sms_sid: Mapped[str | None] = mapped_column(String(64))  # Twilio message SID

    incident: Mapped["Incident"] = relationship(back_populates="emergency_contacts")


# ─── Dispatcher (web dashboard users) ────────────────────────────────────────

class Dispatcher(Base):
    __tablename__ = "dispatchers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(256))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
