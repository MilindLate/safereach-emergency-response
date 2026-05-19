"""
SafeReach — Notification Service
Twilio SMS for family alerts + offline fallback + Firebase push notifications.
"""

import logging
from typing import Optional

from app.core.config import settings
from app.models.incident import EmergencyContact, Hospital, Incident

logger = logging.getLogger(__name__)


class NotificationService:

    # ─── Family SMS ───────────────────────────────────────────────────────────

    async def notify_family(self, incident: Incident, tracker_url: str) -> None:
        """
        Send SMS to all emergency contacts within 60 seconds of SOS trigger.
        Uses Twilio for internet-connected, falls back to direct SMS for offline.
        """
        if not incident.emergency_contacts:
            logger.info("Incident %s — no emergency contacts registered.", incident.id)
            return

        hospital_name = incident.hospital.name if incident.hospital else "nearest hospital"
        severity_label = {
            "low": "minor road accident",
            "medium": "road accident",
            "critical": "serious road accident",
        }.get(incident.severity.value, "road accident")

        message = (
            f"[SafeReach Alert] Your contact was in a {severity_label}. "
            f"An ambulance is on the way. Track live: {tracker_url}\n"
            f"Receiving hospital: {hospital_name}. —SafeReach Emergency System"
        )

        for contact in incident.emergency_contacts:
            await self._send_sms(contact.phone, message, contact=contact)

    async def _send_sms(
        self,
        to_phone: str,
        message: str,
        contact: Optional[EmergencyContact] = None,
    ) -> bool:
        """Send SMS via Twilio. Returns True on success."""
        try:
            from twilio.rest import Client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            msg = client.messages.create(
                body=message,
                from_=settings.TWILIO_FROM_NUMBER,
                to=to_phone,
            )
            if contact:
                from datetime import datetime, timezone
                contact.notified_at = datetime.now(timezone.utc)
                contact.sms_sid = msg.sid
            logger.info("SMS sent to %s (%s)", to_phone[:7] + "****", msg.sid)
            return True

        except ImportError:
            logger.error("Twilio not installed — SMS not sent to %s", to_phone[:7] + "****")
            return False
        except Exception as exc:
            logger.exception("Twilio SMS failed for %s: %s", to_phone[:7] + "****", exc)
            return False

    async def send_offline_sos_sms(self, latitude: float, longitude: float) -> bool:
        """
        Fallback SMS to 112 when internet is unavailable.
        Triggered by the mobile app's service worker — this endpoint is a server-side mirror.
        """
        maps_url = f"https://maps.google.com/?q={latitude},{longitude}"
        message = (
            f"[SafeReach EMERGENCY] Road accident reported. "
            f"GPS location: {latitude:.5f},{longitude:.5f} — {maps_url}"
        )
        return await self._send_sms(settings.EMERGENCY_NUMBER, message)

    # ─── Hospital pre-alert ───────────────────────────────────────────────────

    async def send_hospital_prealert(
        self,
        hospital: Hospital,
        incident: Incident,
        eta_minutes: int,
    ) -> None:
        """
        Alert receiving hospital 10 minutes before ambulance arrives.
        Sends SMS to hospital phone and (in production) pushes to hospital system API.
        """
        if not hospital.phone:
            logger.warning("Hospital %s has no phone on record for pre-alert.", hospital.name)
            return

        severity_label = incident.severity.value.upper()
        message = (
            f"[SafeReach Pre-Alert] INCOMING PATIENT — {severity_label} severity. "
            f"Ambulance ETA: {eta_minutes} minutes. Incident ID: {str(incident.id)[:8]}. "
            f"Prepare trauma bay. —SafeReach System"
        )
        await self._send_sms(hospital.phone, message)
        logger.info("Pre-alert sent to hospital %s — ETA %d min", hospital.name, eta_minutes)

    # ─── Firebase push (crew app) ─────────────────────────────────────────────

    async def push_dispatch_to_crew(
        self,
        fcm_token: str,
        incident_id: str,
        route_polyline: str,
        severity: str,
    ) -> None:
        """Push dispatch notification and route to ambulance crew app via FCM."""
        try:
            import firebase_admin
            from firebase_admin import credentials, messaging

            if not firebase_admin._apps:
                cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
                firebase_admin.initialize_app(cred)

            message = messaging.Message(
                notification=messaging.Notification(
                    title=f"DISPATCH — {severity.upper()} incident",
                    body="New incident assigned. Route loaded. Proceed immediately.",
                ),
                data={
                    "type": "dispatch",
                    "incident_id": incident_id,
                    "route_polyline": route_polyline,
                    "severity": severity,
                },
                token=fcm_token,
                android=messaging.AndroidConfig(priority="high"),
                apns=messaging.APNSConfig(
                    headers={"apns-priority": "10"},
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(sound="default", badge=1)
                    ),
                ),
            )
            messaging.send(message)
            logger.info("FCM push sent to crew token %s…", fcm_token[:12])

        except ImportError:
            logger.error("firebase-admin not installed — push not sent.")
        except Exception as exc:
            logger.exception("FCM push failed: %s", exc)


notification_service = NotificationService()
