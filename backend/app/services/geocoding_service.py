"""
SafeReach — Geocoding Service
Reverse geocodes GPS coordinates to human-readable address strings.
Used to display "NH-48 near Gurugram Toll" instead of raw lat/lng.
Primary: Google Maps Geocoding API
Fallback: Nominatim (OpenStreetMap) — free, no key required
"""

import logging
from typing import Optional

import httpx

from app.core.config import settings
from app.core.redis import cache_get, cache_set

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
GOOGLE_GEO_URL = "https://maps.googleapis.com/maps/api/geocode/json"
GEOCODE_CACHE_TTL = 86400  # 24 hours — addresses don't change


class GeocodingService:

    def __init__(self):
        self._http = httpx.AsyncClient(
            timeout=4.0,
            headers={"User-Agent": "SafeReach-Emergency-App/1.0 contact@safereach.in"},
        )

    async def reverse_geocode(self, latitude: float, longitude: float) -> Optional[str]:
        """
        Convert GPS coordinates to a readable Indian address string.
        Returns format like: "NH-48, Sector 18, Gurugram, Haryana"
        Cached in Redis for 24h by coordinate grid (50m resolution).
        """
        # Round to 4dp (~11m precision) for cache key
        cache_key = f"geocode:{latitude:.4f}:{longitude:.4f}"
        cached = await cache_get(cache_key)
        if cached:
            return cached.get("address")

        # Try Google Maps first (better Indian address quality)
        if settings.GOOGLE_MAPS_API_KEY:
            try:
                address = await self._google_geocode(latitude, longitude)
                if address:
                    await cache_set(cache_key, {"address": address}, ttl_seconds=GEOCODE_CACHE_TTL)
                    return address
            except Exception as exc:
                logger.warning("Google geocoding failed, trying Nominatim: %s", exc)

        # Fallback to Nominatim
        try:
            address = await self._nominatim_geocode(latitude, longitude)
            if address:
                await cache_set(cache_key, {"address": address}, ttl_seconds=GEOCODE_CACHE_TTL)
            return address
        except Exception as exc:
            logger.warning("Nominatim geocoding failed: %s", exc)
            return None

    async def _google_geocode(self, lat: float, lng: float) -> Optional[str]:
        res = await self._http.get(
            GOOGLE_GEO_URL,
            params={
                "latlng":   f"{lat},{lng}",
                "key":      settings.GOOGLE_MAPS_API_KEY,
                "language": "en",
                "result_type": "route|premise|political",
            },
        )
        res.raise_for_status()
        data = res.json()
        if data.get("status") == "OK" and data.get("results"):
            return data["results"][0].get("formatted_address")
        return None

    async def _nominatim_geocode(self, lat: float, lng: float) -> Optional[str]:
        res = await self._http.get(
            NOMINATIM_URL,
            params={
                "lat":    lat,
                "lon":    lng,
                "format": "json",
                "zoom":   16,
                "addressdetails": 1,
            },
        )
        res.raise_for_status()
        data = res.json()

        if "error" in data:
            return None

        addr = data.get("address", {})
        parts = []

        # Build readable address for Indian roads
        for key in ["road", "suburb", "city_district", "city", "state_district", "state"]:
            val = addr.get(key)
            if val and val not in parts:
                parts.append(val)

        return ", ".join(parts[:4]) if parts else data.get("display_name")

    async def close(self):
        await self._http.aclose()


geocoding_service = GeocodingService()
