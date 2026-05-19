"""
SafeReach — AI Service
Wraps the three AI models:
  1. EfficientNet-B2 Severity CNN (PyTorch)
  2. XGBoost Hotspot Predictor
  3. OSRM Route Optimiser (in routing_service.py)
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

import numpy as np

from app.core.config import settings
from app.schemas.incident import HotspotPrediction, SeverityPrediction

logger = logging.getLogger(__name__)

# ─── Lazy model loading — avoids cold-start penalty on import ─────────────────

_cnn_model = None
_hotspot_model = None
_transform = None


def _load_cnn():
    global _cnn_model, _transform
    if _cnn_model is not None:
        return _cnn_model

    try:
        import torch
        import torchvision.transforms as T
        from torchvision.models import efficientnet_b2

        model = efficientnet_b2(weights=None)
        # Replace head for 3-class classification (low / medium / critical)
        in_features = model.classifier[1].in_features
        import torch.nn as nn
        model.classifier = nn.Sequential(
            nn.Dropout(p=0.3, inplace=True),
            nn.Linear(in_features, 3),
        )

        model_path = Path(settings.SEVERITY_CNN_MODEL_PATH)
        if model_path.exists():
            state = torch.load(model_path, map_location="cpu", weights_only=True)
            model.load_state_dict(state)
            logger.info("Severity CNN loaded from %s", model_path)
        else:
            logger.warning(
                "Severity CNN weights not found at %s — running in stub mode.", model_path
            )

        model.eval()
        _cnn_model = model

        _transform = T.Compose([
            T.Resize((224, 224)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
        return model

    except ImportError:
        logger.error("PyTorch not installed — CNN inference unavailable.")
        return None


def _load_hotspot():
    global _hotspot_model
    if _hotspot_model is not None:
        return _hotspot_model

    try:
        import pickle
        model_path = Path(settings.HOTSPOT_MODEL_PATH)
        if model_path.exists():
            with open(model_path, "rb") as f:
                _hotspot_model = pickle.load(f)
            logger.info("Hotspot XGBoost model loaded from %s", model_path)
        else:
            logger.warning("Hotspot model not found at %s — stub mode.", model_path)
            _hotspot_model = None
        return _hotspot_model
    except ImportError:
        logger.error("XGBoost / pickle not available.")
        return None


# ─── AI Service class ─────────────────────────────────────────────────────────

class AIService:
    """
    All model inference runs in a thread pool executor so FastAPI's event loop
    is never blocked by CPU-bound PyTorch / XGBoost calls.
    """

    SEVERITY_CLASSES = ["low", "medium", "critical"]

    async def predict_severity(self, photo_s3_key: str) -> Optional[SeverityPrediction]:
        """
        Download image from S3, run EfficientNet-B2 inference.
        Returns SeverityPrediction with class scores and confidence.
        Target: < 1.5 s end-to-end on CPU.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_predict_severity, photo_s3_key)

    def _sync_predict_severity(self, photo_s3_key: str) -> Optional[SeverityPrediction]:
        t0 = time.perf_counter()
        model = _load_cnn()

        if model is None:
            # Stub: return medium severity when model unavailable
            return SeverityPrediction(
                severity="medium",
                confidence=0.70,
                class_scores={"low": 0.10, "medium": 0.70, "critical": 0.20},
                inference_ms=0.0,
            )

        try:
            import torch
            import torch.nn.functional as F
            from PIL import Image
            import boto3, io

            # Download from S3
            s3 = boto3.client("s3", region_name=settings.AWS_REGION)
            obj = s3.get_object(Bucket=settings.S3_BUCKET_NAME, Key=photo_s3_key)
            image = Image.open(io.BytesIO(obj["Body"].read())).convert("RGB")

            # Preprocess + inference
            tensor = _transform(image).unsqueeze(0)  # [1, 3, 224, 224]
            with torch.no_grad():
                logits = model(tensor)
                probs = F.softmax(logits, dim=1)[0].tolist()

            severity_idx = int(np.argmax(probs))
            inference_ms = (time.perf_counter() - t0) * 1000

            class_scores = dict(zip(self.SEVERITY_CLASSES, [round(p, 4) for p in probs]))
            return SeverityPrediction(
                severity=self.SEVERITY_CLASSES[severity_idx],
                confidence=round(probs[severity_idx], 4),
                class_scores=class_scores,
                inference_ms=round(inference_ms, 1),
            )

        except Exception as exc:
            logger.exception("CNN inference failed: %s", exc)
            return None

    async def predict_hotspot(self, latitude: float, longitude: float) -> Optional[HotspotPrediction]:
        """
        XGBoost hotspot risk prediction for given location + current time.
        Uses 14 features: temporal, weather (via Open-Meteo), road type, historical density.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._sync_predict_hotspot, latitude, longitude
        )

    def _sync_predict_hotspot(self, latitude: float, longitude: float) -> Optional[HotspotPrediction]:
        from datetime import datetime, timezone
        import math

        model = _load_hotspot()
        now = datetime.now(timezone.utc)

        features = self._build_hotspot_features(latitude, longitude, now)

        if model is None:
            # Stub: use simple heuristic
            risk = min(0.8, max(0.1, 0.3 + 0.1 * math.sin(latitude) + 0.05 * (now.hour / 24)))
            return HotspotPrediction(
                risk_score=round(risk, 3),
                risk_label=self._risk_label(risk),
                top_features={"hour_of_day": 0.25, "historical_density": 0.20},
            )

        try:
            risk = float(model.predict_proba([features])[0][1])
            # SHAP-based top features (simplified — real impl uses shap.TreeExplainer)
            top_features = {"historical_density": 0.30, "hour_of_day": 0.22, "road_type": 0.18}
            return HotspotPrediction(
                risk_score=round(risk, 3),
                risk_label=self._risk_label(risk),
                top_features=top_features,
            )
        except Exception as exc:
            logger.exception("Hotspot inference failed: %s", exc)
            return None

    def _build_hotspot_features(self, lat: float, lon: float, now) -> list:
        """
        Build the 14-feature vector for the XGBoost model.
        In production these would be enriched from Open-Meteo API and iRAD.
        """
        hour = now.hour
        dow = now.weekday()   # 0=Monday
        month = now.month

        # Weather stub (would call Open-Meteo in production)
        weather_code = 0       # 0=clear, 1=rain, 2=fog
        temperature = 28.0
        visibility = 1.0       # normalised 0–1

        # Road type stub (would query OSM / iRAD)
        road_type = 1          # 0=NH, 1=SH, 2=urban, 3=rural
        speed_limit = 60
        junction_type = 0      # 0=signalised, 1=uncontrolled, 2=roundabout

        # Historical density (stub — would come from iRAD grid lookup)
        hist_density_3yr = 0.4
        traffic_density = 0.5

        # Festival flag (stub — would look up public holiday calendar)
        festival_flag = 0

        return [
            hour, dow, month,
            weather_code, temperature, visibility,
            road_type, speed_limit,
            hist_density_3yr, traffic_density,
            junction_type, speed_limit,
            festival_flag, lat,
        ]

    @staticmethod
    def _risk_label(score: float) -> str:
        if score >= 0.70:
            return "high"
        if score >= 0.40:
            return "moderate"
        return "low"


ai_service = AIService()
