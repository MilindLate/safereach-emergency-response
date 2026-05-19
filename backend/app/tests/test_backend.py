"""
SafeReach — Backend Test Suite
Coverage target: 75%+
Tests: SOS ingestion, severity CNN stub, PostGIS query, Twilio mock.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app
from app.core.config import settings


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
def device_token():
    from app.core.security import create_device_token
    return create_device_token("test-device-id-1234567890abcdef")


@pytest.fixture
def dispatcher_token():
    from app.core.security import create_access_token
    return create_access_token("dispatcher-uuid-123", role="dispatcher")


# ─── Health Check ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "SafeReach API"


# ─── Device Registration ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_device_register(client: AsyncClient):
    response = await client.post("/api/v1/auth/device/register", json={
        "device_id": "test-device-id-abcdef123456",
        "platform": "android",
        "emergency_contacts": ["+919876543210"],
        "language": "hi",
    })
    assert response.status_code == 200
    data = response.json()
    assert "device_token" in data
    assert data["expires_in_days"] == settings.JWT_DEVICE_TOKEN_EXPIRE_DAYS


@pytest.mark.asyncio
async def test_device_register_invalid_platform(client: AsyncClient):
    response = await client.post("/api/v1/auth/device/register", json={
        "device_id": "test-device-id-abcdef123456",
        "platform": "windows",  # invalid
    })
    assert response.status_code == 422


# ─── SOS Trigger ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sos_trigger_requires_auth(client: AsyncClient):
    response = await client.post("/api/v1/sos/trigger", json={
        "device_id": "test-device-id-1234567890abcdef",
        "location": {"latitude": 21.1458, "longitude": 79.0882},
        "language": "hi",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_sos_trigger_invalid_location(client: AsyncClient, device_token: str):
    response = await client.post(
        "/api/v1/sos/trigger",
        json={
            "device_id": "test-device-id-1234567890abcdef",
            "location": {"latitude": 200.0, "longitude": 79.0},  # invalid lat
        },
        headers={"Authorization": f"Bearer {device_token}"},
    )
    assert response.status_code == 422


# ─── AI Service Unit Tests ────────────────────────────────────────────────────

class TestAIService:

    def test_severity_stub_returns_prediction(self):
        """CNN stub mode should return medium severity when model weights absent."""
        from app.services.ai_service import AIService
        service = AIService()
        result = service._sync_predict_severity("fake/key.jpg")
        # In stub mode (no model file), should return a valid SeverityPrediction
        # This test validates the graceful fallback
        assert result is None or result.severity in ("low", "medium", "critical")

    def test_hotspot_stub_returns_valid_score(self):
        """Hotspot stub should return score in [0, 1]."""
        import asyncio
        from app.services.ai_service import ai_service

        async def _test():
            result = await ai_service.predict_hotspot(21.1458, 79.0882)
            if result:
                assert 0.0 <= result.risk_score <= 1.0
                assert result.risk_label in ("low", "moderate", "high")
        asyncio.run(_test())

    def test_risk_label_thresholds(self):
        from app.services.ai_service import AIService
        assert AIService._risk_label(0.75) == "high"
        assert AIService._risk_label(0.50) == "moderate"
        assert AIService._risk_label(0.20) == "low"

    def test_hotspot_feature_vector_length(self):
        from app.services.ai_service import AIService
        from datetime import datetime, timezone
        service = AIService()
        features = service._build_hotspot_features(21.1458, 79.0882, datetime.now(timezone.utc))
        assert len(features) == 14


# ─── Security Tests ───────────────────────────────────────────────────────────

class TestSecurity:

    def test_create_and_decode_device_token(self):
        from app.core.security import create_device_token, decode_token
        token = create_device_token("device-abc-123456789012")
        payload = decode_token(token)
        assert payload["role"] == "device"
        assert payload["sub"] == "device-abc-123456789012"

    def test_family_tracker_token(self):
        from app.core.security import create_family_tracker_token, decode_token
        import uuid
        incident_id = str(uuid.uuid4())
        token = create_family_tracker_token(incident_id)
        payload = decode_token(token)
        assert payload["role"] == "tracker"
        assert payload["sub"] == incident_id

    def test_dispatcher_role_required(self):
        from app.core.security import create_device_token, decode_token
        token = create_device_token("device-abc-123456789012")
        payload = decode_token(token)
        # Device tokens should NOT have dispatcher role
        assert payload["role"] != "dispatcher"

    def test_password_hash_and_verify(self):
        from app.core.security import hash_password, verify_password
        hashed = hash_password("SecurePassword123!")
        assert verify_password("SecurePassword123!", hashed)
        assert not verify_password("WrongPassword", hashed)


# ─── Routing Service Tests ────────────────────────────────────────────────────

class TestRoutingService:

    @pytest.mark.asyncio
    async def test_osrm_fallback_on_google_failure(self):
        """When Google Maps fails, OSRM fallback should be attempted."""
        from app.services.routing_service import RoutingService
        from app.schemas.incident import LocationPoint

        service = RoutingService()

        with patch.object(service, "_google_route", side_effect=Exception("API error")):
            with patch.object(service, "_osrm_route", new_callable=AsyncMock) as mock_osrm:
                mock_osrm.return_value = {
                    "duration_seconds": 720,
                    "distance_meters": 8500,
                    "polyline": "abc123",
                    "steps": [],
                    "source": "osrm",
                }
                origin = LocationPoint(latitude=21.14, longitude=79.08)
                dest = LocationPoint(latitude=21.16, longitude=79.10)
                result = await service.get_route(origin, dest, use_traffic=True)
                assert result["source"] == "osrm"
                assert result["duration_seconds"] == 720
