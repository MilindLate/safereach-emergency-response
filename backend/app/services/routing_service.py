"""
SafeReach — Routing Service
OSRM self-hosted routing + Google Maps traffic overlay.
Route refresh every 30 seconds via Celery beat task.
"""

import logging
from typing import Optional

import httpx

from app.core.config import settings
from app.schemas.incident import LocationPoint

logger = logging.getLogger(__name__)


class RoutingService:
    """
    Wraps OSRM for base routing and Google Maps Directions API for traffic overlay.
    Target: sub-200ms for OSRM queries (self-hosted), < 2s for full route with traffic.
    """

    def __init__(self):
        self._http = httpx.AsyncClient(timeout=5.0)

    async def get_route(
        self,
        origin: LocationPoint,
        destination: LocationPoint,
        use_traffic: bool = True,
    ) -> dict:
        """
        Returns a route dict with:
          - duration_seconds (int)
          - distance_meters (int)
          - polyline (str — Google encoded polyline)
          - steps (list of turn-by-turn instructions)
        """
        # Try Google Maps first (has real-time traffic)
        if use_traffic and settings.GOOGLE_MAPS_API_KEY:
            try:
                return await self._google_route(origin, destination)
            except Exception as exc:
                logger.warning("Google Maps routing failed, falling back to OSRM: %s", exc)

        # Fallback to self-hosted OSRM
        return await self._osrm_route(origin, destination)

    async def _osrm_route(self, origin: LocationPoint, destination: LocationPoint) -> dict:
        """Query self-hosted OSRM. Sub-200ms target."""
        coords = f"{origin.longitude},{origin.latitude};{destination.longitude},{destination.latitude}"
        url = (
            f"{settings.OSRM_BASE_URL}/route/v1/driving/{coords}"
            f"?overview=full&geometries=polyline&steps=true&annotations=false"
        )
        response = await self._http.get(url)
        response.raise_for_status()
        data = response.json()

        if data.get("code") != "Ok" or not data.get("routes"):
            raise ValueError(f"OSRM returned no route: {data.get('code')}")

        route = data["routes"][0]
        leg = route["legs"][0]

        steps = [
            {
                "instruction": step["maneuver"]["type"],
                "name": step.get("name", ""),
                "distance_m": step["distance"],
                "duration_s": step["duration"],
            }
            for step in leg["steps"]
        ]

        return {
            "duration_seconds": int(route["duration"]),
            "distance_meters": int(route["distance"]),
            "polyline": route["geometry"],
            "steps": steps,
            "source": "osrm",
        }

    async def _google_route(self, origin: LocationPoint, destination: LocationPoint) -> dict:
        """Google Maps Directions API with real-time traffic."""
        url = "https://maps.googleapis.com/maps/api/directions/json"
        params = {
            "origin": f"{origin.latitude},{origin.longitude}",
            "destination": f"{destination.latitude},{destination.longitude}",
            "mode": "driving",
            "departure_time": "now",
            "traffic_model": "best_guess",
            "key": settings.GOOGLE_MAPS_API_KEY,
        }
        response = await self._http.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if data["status"] != "OK" or not data["routes"]:
            raise ValueError(f"Google Maps returned status: {data['status']}")

        route = data["routes"][0]
        leg = route["legs"][0]

        # Prefer duration_in_traffic if available (traffic-aware)
        duration_s = leg.get("duration_in_traffic", leg["duration"])["value"]

        steps = [
            {
                "instruction": step["html_instructions"],
                "distance_m": step["distance"]["value"],
                "duration_s": step["duration"]["value"],
            }
            for step in leg["steps"]
        ]

        return {
            "duration_seconds": duration_s,
            "distance_meters": leg["distance"]["value"],
            "polyline": route["overview_polyline"]["points"],
            "steps": steps,
            "source": "google_maps",
        }

    async def flag_high_risk_segments(self, route_polyline: str) -> list:
        """
        Analyse route polyline for school zones and railway crossings.
        Returns list of flagged segment indices.
        In production: cross-reference with OSM school/railway layer.
        """
        # Stub — real implementation queries PostGIS spatial index
        return []

    async def close(self):
        await self._http.aclose()


routing_service = RoutingService()
