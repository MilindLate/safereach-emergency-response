"""
SafeReach — Pydantic Schemas
Request/response validation for all API endpoints.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ─── Base helpers ─────────────────────────────────────────────────────────────

class LocationPoint(BaseModel):
    latitude: float = Field(..., ge=-90, le=90, description="WGS-84 latitude")
    longitude: float = Field(..., ge=-180, le=180, description="WGS-84 longitude")
    accuracy_meters: Optional[float] = Field(None, ge=0, description="GPS accuracy radius")


# ─── SOS / Incident ───────────────────────────────────────────────────────────

class SOSTriggerRequest(BaseModel):
    """Payload sent from victim mobile app on SOS activation."""
    device_id: str = Field(..., min_length=16, max_length=256)
    location: LocationPoint
    language: str = Field("en", max_length=10)
    emergency_contacts: List[str] = Field(default_factory=list, max_length=5)
    # photo_s3_key is set server-side after S3 upload; not in this payload

    @field_validator("emergency_contacts")
    @classmethod
    def validate_phones(cls, v):
        for phone in v:
            if not phone.strip().lstrip("+").isdigit():
                raise ValueError(f"Invalid phone number: {phone}")
        return v


class SOSTriggerResponse(BaseModel):
    incident_id: UUID
    status: str
    nearest_hospital_name: Optional[str] = None
    eta_seconds: Optional[int] = None
    ambulance_unit_code: Optional[str] = None
    family_tracker_url: Optional[str] = None


class IncidentSummary(BaseModel):
    id: UUID
    severity: str
    status: str
    cnn_score: Optional[float] = None
    hotspot_risk: Optional[float] = None
    latitude: float
    longitude: float
    address_approx: Optional[str] = None
    created_at: datetime
    dispatched_at: Optional[datetime] = None
    ambulance_unit_code: Optional[str] = None
    hospital_name: Optional[str] = None


class IncidentDetail(IncidentSummary):
    photo_url: Optional[str] = None
    cnn_confidence: Optional[float] = None
    emergency_contacts_notified: int = 0


# ─── Dispatch ─────────────────────────────────────────────────────────────────

class DispatchAssignRequest(BaseModel):
    incident_id: UUID
    ambulance_unit_id: UUID


class DispatchAssignResponse(BaseModel):
    incident_id: UUID
    ambulance_unit_id: UUID
    ambulance_unit_code: str
    route_polyline: Optional[str] = None  # encoded polyline for map display
    eta_seconds: int


# ─── Ambulance ────────────────────────────────────────────────────────────────

class AmbulanceLocationUpdate(BaseModel):
    """Sent from crew app every 10–30 seconds."""
    unit_id: UUID
    location: LocationPoint
    speed_kmh: Optional[float] = None


class AmbulanceUnitStatus(BaseModel):
    id: UUID
    unit_code: str
    status: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    eta_seconds: Optional[int] = None
    distance_km: Optional[float] = None


# ─── Hospital ─────────────────────────────────────────────────────────────────

class HospitalInfo(BaseModel):
    id: UUID
    name: str
    latitude: float
    longitude: float
    phone: Optional[str] = None
    trauma_level: int
    beds_available: int
    distance_km: Optional[float] = None


# ─── AI Models ────────────────────────────────────────────────────────────────

class SeverityPrediction(BaseModel):
    severity: str          # low / medium / critical
    confidence: float      # 0.0 – 1.0
    class_scores: dict     # {"low": 0.1, "medium": 0.2, "critical": 0.7}
    inference_ms: float


class HotspotPrediction(BaseModel):
    risk_score: float      # 0.0 – 1.0
    risk_label: str        # low / moderate / high
    top_features: dict     # SHAP-inspired feature importance


# ─── Auth ─────────────────────────────────────────────────────────────────────

class DeviceRegisterRequest(BaseModel):
    device_id: str = Field(..., min_length=16, max_length=256)
    platform: str = Field(..., pattern="^(android|ios)$")
    emergency_contacts: List[str] = Field(default_factory=list, max_length=5)
    language: str = Field("en", max_length=10)


class DeviceRegisterResponse(BaseModel):
    device_token: str
    expires_in_days: int


class DispatcherLoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


# ─── Tracker ─────────────────────────────────────────────────────────────────

class FamilyTrackerData(BaseModel):
    incident_id: UUID
    victim_latitude: float
    victim_longitude: float
    ambulance_latitude: Optional[float] = None
    ambulance_longitude: Optional[float] = None
    ambulance_eta_seconds: Optional[int] = None
    receiving_hospital_name: Optional[str] = None
    incident_status: str
    last_updated: datetime
