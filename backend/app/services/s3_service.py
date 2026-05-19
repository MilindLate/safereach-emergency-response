"""
SafeReach — S3 Service
Crash photo upload and presigned URL generation.
Photos are compressed before upload for 2G/3G network performance.
"""

import io
import logging
import uuid
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

PHOTO_MAX_SIZE_BYTES = 800_000  # 800KB target for 2G upload
PHOTO_QUALITY = 80              # JPEG quality for re-compression


class S3Service:

    def _get_client(self):
        import boto3
        return boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )

    async def upload_crash_photo(self, image_bytes: bytes, incident_id: str) -> Optional[str]:
        """
        Compress image if needed, upload to S3, return S3 key.
        Key format: crashes/{incident_id}/{uuid}.jpg
        """
        try:
            from PIL import Image

            # Re-compress if too large
            if len(image_bytes) > PHOTO_MAX_SIZE_BYTES:
                img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                # Resize to max 1920px on longest side
                img.thumbnail((1920, 1920), Image.LANCZOS)
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=PHOTO_QUALITY, optimize=True)
                image_bytes = buffer.getvalue()
                logger.debug("Photo compressed to %d KB", len(image_bytes) // 1024)

            s3_key = f"crashes/{incident_id}/{uuid.uuid4().hex}.jpg"
            s3 = self._get_client()
            s3.put_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=s3_key,
                Body=image_bytes,
                ContentType="image/jpeg",
                ServerSideEncryption="AES256",
            )
            logger.info("Uploaded crash photo to s3://%s/%s", settings.S3_BUCKET_NAME, s3_key)
            return s3_key

        except ImportError:
            logger.error("Pillow or boto3 not installed — photo upload skipped.")
            return None
        except Exception as exc:
            logger.exception("S3 upload failed: %s", exc)
            return None

    async def get_presigned_url(self, s3_key: Optional[str], expires_in: int = 3600) -> Optional[str]:
        """Generate a presigned URL for reading a crash photo (1-hour expiry by default)."""
        if not s3_key:
            return None
        try:
            s3 = self._get_client()
            return s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.S3_BUCKET_NAME, "Key": s3_key},
                ExpiresIn=expires_in,
            )
        except Exception as exc:
            logger.exception("Presigned URL generation failed: %s", exc)
            return None


s3_service = S3Service()
