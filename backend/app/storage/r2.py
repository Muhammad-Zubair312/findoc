"""Unified storage client: local filesystem in dev, Cloudflare R2 in prod.

NEVER references B2 or Backblaze. R2 is S3-compatible via aioboto3/boto3.
"""

from pathlib import Path

import aioboto3

from app.config import settings
from app.logging import get_logger

log = get_logger(__name__)


def _r2_endpoint_url() -> str:
    return f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"


class StorageClient:
    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        """Returns storage key. Saves locally if USE_LOCAL_STORAGE=True, else to R2."""
        if settings.USE_LOCAL_STORAGE:
            path = Path(settings.LOCAL_UPLOAD_DIR) / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return str(path)

        async with aioboto3.Session().client(
            "s3",
            endpoint_url=_r2_endpoint_url(),
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name="auto",
        ) as s3:
            await s3.put_object(
                Bucket=settings.R2_BUCKET, Key=key, Body=data, ContentType=content_type
            )
            return key

    async def download(self, storage_key: str) -> bytes:
        """Downloads file by key. Works for both local and R2."""
        if settings.USE_LOCAL_STORAGE or storage_key.startswith("/") or ":" in storage_key[:3]:
            return Path(storage_key).read_bytes()

        async with aioboto3.Session().client(
            "s3",
            endpoint_url=_r2_endpoint_url(),
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name="auto",
        ) as s3:
            response = await s3.get_object(Bucket=settings.R2_BUCKET, Key=storage_key)
            body: bytes = await response["Body"].read()
            return body

    async def delete(self, storage_key: str) -> None:
        """Deletes file. Works for both local and R2."""
        if settings.USE_LOCAL_STORAGE or storage_key.startswith("/") or ":" in storage_key[:3]:
            path = Path(storage_key)
            path.unlink(missing_ok=True)
            return

        async with aioboto3.Session().client(
            "s3",
            endpoint_url=_r2_endpoint_url(),
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name="auto",
        ) as s3:
            await s3.delete_object(Bucket=settings.R2_BUCKET, Key=storage_key)


storage_client = StorageClient()
