"""
SafeReach — Application Configuration
All settings are loaded from environment variables / .env file.
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ─── App ──────────────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me-in-production"
    ALLOWED_HOSTS: List[str] = ["*"]
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8081"]

    # ─── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://safereach:safereach@localhost:5432/safereach"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # ─── Redis ────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ─── JWT ──────────────────────────────────────────────────────────────────
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    JWT_DEVICE_TOKEN_EXPIRE_DAYS: int = 365

    # ─── AWS S3 ───────────────────────────────────────────────────────────────
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-south-1"
    S3_BUCKET_NAME: str = "safereach-media"

    # ─── Twilio SMS ───────────────────────────────────────────────────────────
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = "+1234567890"
    EMERGENCY_NUMBER: str = "112"

    # ─── Google Maps ──────────────────────────────────────────────────────────
    GOOGLE_MAPS_API_KEY: str = ""

    # ─── Firebase ─────────────────────────────────────────────────────────────
    FIREBASE_CREDENTIALS_PATH: str = "firebase-credentials.json"

    # ─── Bhashini ─────────────────────────────────────────────────────────────
    BHASHINI_API_KEY: str = ""
    BHASHINI_USER_ID: str = ""

    # ─── AI Models ────────────────────────────────────────────────────────────
    SEVERITY_CNN_MODEL_PATH: str = "app/ai/models/severity_cnn.pt"
    HOTSPOT_MODEL_PATH: str = "app/ai/models/hotspot_xgboost.pkl"
    CNN_INFERENCE_TIMEOUT_S: float = 2.0

    # ─── OSRM ─────────────────────────────────────────────────────────────────
    OSRM_BASE_URL: str = "http://localhost:5000"
    ROUTE_REFRESH_INTERVAL_S: int = 30

    # ─── Celery ───────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ─── Feature flags ────────────────────────────────────────────────────────
    AUTO_DISPATCH_CRITICAL_TIMEOUT_S: int = 30
    HOSPITAL_PREALERT_MINUTES_BEFORE: int = 10
    HOTSPOT_REFRESH_HOURS: int = 6


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
