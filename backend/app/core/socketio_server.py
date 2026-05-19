"""
SafeReach — Socket.io Real-Time Server
Mounts on FastAPI via ASGI middleware.
Handles: incident rooms, ambulance location channels, dispatcher subscriptions.

Channels:
  safereach:incidents          — all dispatchers subscribe here
  safereach:ambulance:{unit_id} — per-unit dispatch commands
  safereach:ambulance:location:{unit_id} — live GPS stream
  incident:{incident_id}       — victim + family tracker updates
"""

import logging
from typing import Optional

import socketio
from jose import JWTError

from app.core.config import settings

logger = logging.getLogger(__name__)

# Redis adapter for horizontal scaling (multiple uvicorn workers)
mgr = socketio.AsyncRedisManager(settings.REDIS_URL, write_only=False)

sio = socketio.AsyncServer(
    async_mode="asgi",
    client_manager=mgr,
    cors_allowed_origins=settings.CORS_ORIGINS,
    logger=False,
    engineio_logger=False,
)


def get_sio_app(fastapi_app):
    """Wrap FastAPI app with Socket.io ASGI middleware."""
    return socketio.ASGIApp(sio, other_asgi_app=fastapi_app, socketio_path="/socket.io")


# ── Authentication middleware ─────────────────────────────────────────────────

@sio.event
async def connect(sid, environ, auth):
    """Validate JWT token on connection."""
    token = (auth or {}).get("token")
    if not token:
        logger.warning("Socket.io connection rejected — no token. sid=%s", sid[:8])
        return False  # reject

    try:
        from app.core.security import decode_token
        payload = decode_token(token)
        await sio.save_session(sid, {"user": payload})
        logger.info("Socket.io connected: sid=%s role=%s", sid[:8], payload.get("role"))
    except Exception:
        logger.warning("Socket.io connection rejected — invalid token. sid=%s", sid[:8])
        return False


@sio.event
async def disconnect(sid):
    logger.info("Socket.io disconnected: sid=%s", sid[:8])


# ── Room management ───────────────────────────────────────────────────────────

@sio.event
async def join_room(sid, room: str):
    """Client joins a specific channel/room."""
    session = await sio.get_session(sid)
    role = session.get("user", {}).get("role", "")

    # Enforce room access control
    allowed = _can_join_room(role, room)
    if not allowed:
        logger.warning("sid=%s role=%s denied access to room=%s", sid[:8], role, room)
        return

    await sio.enter_room(sid, room)
    logger.debug("sid=%s joined room=%s", sid[:8], room)
    await sio.emit("room_joined", {"room": room}, to=sid)


def _can_join_room(role: str, room: str) -> bool:
    """Role-based room access control."""
    if role in ("dispatcher", "admin"):
        return True  # full access
    if role == "device":
        # Devices can only join their own incident room or ambulance room
        return room.startswith("incident:") or room.startswith("safereach:ambulance:")
    if role == "tracker":
        # Family tracker: read-only incident room
        return room.startswith("incident:")
    return False


# ── Incident events (server → clients) ───────────────────────────────────────

async def emit_new_incident(incident_data: dict):
    """Broadcast new incident to all dispatchers."""
    await sio.emit("new_incident", incident_data, room="safereach:incidents")


async def emit_incident_updated(incident_id: str, update: dict):
    """Broadcast status/severity change to dispatchers + victim."""
    await sio.emit("incident_updated", update, room="safereach:incidents")
    await sio.emit("incident_updated", update, room=f"incident:{incident_id}")


async def emit_severity_updated(incident_id: str, severity: str, confidence: float):
    """CNN result available — update all subscribers."""
    data = {"type": "severity_updated", "incident_id": incident_id, "severity": severity, "cnn_confidence": confidence}
    await sio.emit("severity_updated", data, room="safereach:incidents")
    await sio.emit("severity_updated", data, room=f"incident:{incident_id}")


async def emit_ambulance_location(unit_id: str, lat: float, lng: float, speed_kmh: Optional[float]):
    """Push ambulance GPS update to dispatcher + victim tracking rooms."""
    data = {"unit_id": unit_id, "latitude": lat, "longitude": lng, "speed_kmh": speed_kmh}
    await sio.emit("ambulance_location", data, room="safereach:incidents")
    await sio.emit("ambulance_location", data, room=f"safereach:ambulance:location:{unit_id}")


async def emit_dispatch_to_crew(unit_id: str, dispatch_data: dict):
    """Push dispatch order to ambulance crew."""
    await sio.emit("dispatch", dispatch_data, room=f"safereach:ambulance:{unit_id}")


async def emit_eta_update(incident_id: str, eta_seconds: int):
    """Push ETA countdown to victim + family tracker."""
    data = {"incident_id": incident_id, "eta_seconds": eta_seconds}
    await sio.emit("eta_update", data, room=f"incident:{incident_id}")
