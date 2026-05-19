"""
SafeReach — Bhashini / Whisper Multilingual Service
Provides voice-based SOS detection and transcription for:
  - 8 Scheduled Indian languages via Bhashini API
  - On-device Whisper-tiny fallback (offline)

Bhashini (Digital India Language API) is the recommended integration
per the submission doc §3.3 — "voice-based SOS trigger for regional
language support using Bhashini/ULCA."
"""

import asyncio
import logging
import io
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {
    "hi": "Hindi",   "mr": "Marathi",  "ta": "Tamil",
    "te": "Telugu",  "bn": "Bengali",  "kn": "Kannada",
    "gu": "Gujarati","or": "Odia",     "en": "English",
}

# Bhashini ULCA API endpoints
BHASHINI_ASR_URL    = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
BHASHINI_TTS_URL    = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"

# Emergency keywords per language (for voice SOS trigger detection)
EMERGENCY_KEYWORDS = {
    "hi": ["मदद", "बचाओ", "दुर्घटना", "एम्बुलेंस"],
    "mr": ["मदत करा", "अपघात", "रुग्णवाहिका"],
    "ta": ["உதவி", "விபத்து", "ஆம்புலன்ஸ்"],
    "te": ["సహాయం", "ప్రమాదం", "అంబులెన్స్"],
    "en": ["help", "emergency", "accident", "ambulance"],
    "bn": ["সাহায্য", "দুর্ঘটনা", "এ্যাম্বুলেন্স"],
    "kn": ["ಸಹಾಯ", "ಅಪಘಾತ", "ಆಂಬ್ಯುಲೆನ್ಸ್"],
}


class BhashiniService:
    """
    Wraps Bhashini ULCA API for ASR (speech-to-text) and TTS (text-to-speech).
    Falls back to local Whisper-tiny when offline.
    """

    def __init__(self):
        self._http = httpx.AsyncClient(timeout=8.0)
        self._whisper_model = None

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        language: str = "hi",
        sample_rate: int = 16000,
    ) -> Optional[str]:
        """
        Transcribe audio bytes to text.
        Tries Bhashini first, falls back to Whisper-tiny.
        Returns transcribed text or None on failure.
        """
        # Attempt Bhashini cloud ASR
        if settings.BHASHINI_API_KEY:
            try:
                result = await self._bhashini_asr(audio_bytes, language, sample_rate)
                if result:
                    logger.info("Bhashini ASR successful (lang=%s)", language)
                    return result
            except Exception as exc:
                logger.warning("Bhashini ASR failed, falling back to Whisper: %s", exc)

        # Fallback: local Whisper-tiny
        return await self._whisper_transcribe(audio_bytes, language)

    async def detect_sos_in_audio(
        self,
        audio_bytes: bytes,
        language: str = "hi",
    ) -> bool:
        """
        Detect if audio contains emergency/SOS keywords.
        Used for hands-free voice SOS activation.
        Called from mobile service worker every 2 seconds when monitoring.
        Target: < 1.5s total latency on-device.
        """
        text = await self.transcribe_audio(audio_bytes, language)
        if not text:
            return False

        text_lower = text.lower()
        keywords   = EMERGENCY_KEYWORDS.get(language, EMERGENCY_KEYWORDS["en"])
        detected   = any(kw.lower() in text_lower for kw in keywords)

        if detected:
            logger.info("Voice SOS keyword detected (lang=%s): %r", language, text[:60])

        return detected

    async def text_to_speech(
        self,
        text: str,
        language: str = "hi",
    ) -> Optional[bytes]:
        """
        Convert text to speech audio bytes (WAV).
        Used for spoken ETA announcements in victim app and crew app.
        Example: "Ambulance will arrive in 8 minutes."
        """
        if settings.BHASHINI_API_KEY:
            try:
                return await self._bhashini_tts(text, language)
            except Exception as exc:
                logger.warning("Bhashini TTS failed: %s", exc)
        return None

    async def translate_to_language(
        self,
        text: str,
        source_lang: str = "en",
        target_lang: str = "hi",
    ) -> str:
        """
        Translate notification text (e.g. SMS message) to victim's preferred language.
        Uses Bhashini NMT (Neural Machine Translation) pipeline.
        """
        if source_lang == target_lang:
            return text
        if not settings.BHASHINI_API_KEY:
            return text  # fallback to English

        try:
            payload = {
                "pipelineTasks": [
                    {
                        "taskType": "translation",
                        "config": {
                            "language": {
                                "sourceLanguage": source_lang,
                                "targetLanguage": target_lang,
                            }
                        },
                    }
                ],
                "inputData": {"input": [{"source": text}]},
            }
            headers = {
                "Authorization": settings.BHASHINI_API_KEY,
                "userID":        settings.BHASHINI_USER_ID,
                "Content-Type":  "application/json",
            }
            res = await self._http.post(BHASHINI_ASR_URL, json=payload, headers=headers)
            res.raise_for_status()
            data = res.json()
            translated = (
                data.get("pipelineResponse", [{}])[0]
                    .get("output", [{}])[0]
                    .get("target", text)
            )
            return translated

        except Exception as exc:
            logger.warning("Bhashini NMT translation failed: %s", exc)
            return text

    # ── Private: Bhashini ASR ─────────────────────────────────────────────────

    async def _bhashini_asr(self, audio_bytes: bytes, language: str, sample_rate: int) -> Optional[str]:
        import base64
        audio_b64 = base64.b64encode(audio_bytes).decode()

        payload = {
            "pipelineTasks": [
                {
                    "taskType": "asr",
                    "config": {
                        "language": {"sourceLanguage": language},
                        "audioFormat": "wav",
                        "samplingRate": sample_rate,
                    },
                }
            ],
            "inputData": {"audio": [{"audioContent": audio_b64}]},
        }
        headers = {
            "Authorization": settings.BHASHINI_API_KEY,
            "userID":        settings.BHASHINI_USER_ID,
            "Content-Type":  "application/json",
        }
        res = await self._http.post(BHASHINI_ASR_URL, json=payload, headers=headers)
        res.raise_for_status()
        data = res.json()
        return (
            data.get("pipelineResponse", [{}])[0]
                .get("output", [{}])[0]
                .get("source", None)
        )

    async def _bhashini_tts(self, text: str, language: str) -> Optional[bytes]:
        import base64
        payload = {
            "pipelineTasks": [
                {
                    "taskType": "tts",
                    "config": {
                        "language": {"sourceLanguage": language},
                        "gender": "female",
                    },
                }
            ],
            "inputData": {"input": [{"source": text}]},
        }
        headers = {
            "Authorization": settings.BHASHINI_API_KEY,
            "userID":        settings.BHASHINI_USER_ID,
            "Content-Type":  "application/json",
        }
        res = await self._http.post(BHASHINI_TTS_URL, json=payload, headers=headers)
        res.raise_for_status()
        data = res.json()
        audio_b64 = (
            data.get("pipelineResponse", [{}])[0]
                .get("audio", [{}])[0]
                .get("audioContent", None)
        )
        if audio_b64:
            return base64.b64decode(audio_b64)
        return None

    # ── Private: Whisper offline fallback ────────────────────────────────────

    async def _whisper_transcribe(self, audio_bytes: bytes, language: str) -> Optional[str]:
        """
        Local Whisper-tiny inference — runs entirely on device, no network.
        Model size: ~75MB, latency: ~1s on recent mobile CPU.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_whisper, audio_bytes, language)

    def _sync_whisper(self, audio_bytes: bytes, language: str) -> Optional[str]:
        try:
            import whisper
            import numpy as np
            import soundfile as sf

            if self._whisper_model is None:
                self._whisper_model = whisper.load_model("tiny")
                logger.info("Whisper-tiny model loaded.")

            # Convert bytes to numpy array
            audio_file = io.BytesIO(audio_bytes)
            audio_np, sr = sf.read(audio_file)
            if sr != 16000:
                # Resample to 16kHz
                import librosa
                audio_np = librosa.resample(audio_np, orig_sr=sr, target_sr=16000)

            result = self._whisper_model.transcribe(
                audio_np.astype(np.float32),
                language=language if language != "en" else None,
            )
            return result.get("text", "").strip() or None

        except ImportError:
            logger.error("Whisper not installed — voice SOS unavailable.")
            return None
        except Exception as exc:
            logger.exception("Whisper transcription failed: %s", exc)
            return None

    async def close(self):
        await self._http.aclose()


bhashini_service = BhashiniService()
