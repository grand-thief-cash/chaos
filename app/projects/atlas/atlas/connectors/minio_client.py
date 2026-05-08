"""MinIO S3 client — manages document file storage."""
from __future__ import annotations

import io
import logging
from typing import Any

from atlas.core.config import get_config

logger = logging.getLogger(__name__)

_client: Any = None
_BUCKET = "atlas-documents"

# Document type → subdirectory mapping
_DOC_TYPE_DIRS = {
    "earnings": "earnings",
    "research": "research",
    "industry": "industry",
    "news": "news",
    "policy": "policy",
    "announcement": "announcements",
    "manual": "manual",
}


def _get_minio_config() -> dict:
    cfg = get_config()
    return cfg.get("minio", {
        "endpoint": "localhost:9000",
        "access_key": "minioadmin",
        "secret_key": "minioadmin",
        "secure": False,
        "bucket": _BUCKET,
    })


def get_client():
    """Get or create MinIO client (lazy init)."""
    global _client
    if _client is None:
        try:
            from minio import Minio
            mcfg = _get_minio_config()
            _client = Minio(
                mcfg.get("endpoint", "localhost:9000"),
                access_key=mcfg.get("access_key", "minioadmin"),
                secret_key=mcfg.get("secret_key", "minioadmin"),
                secure=mcfg.get("secure", False),
            )
            bucket = mcfg.get("bucket", _BUCKET)
            if not _client.bucket_exists(bucket):
                _client.make_bucket(bucket)
                logger.info("Created MinIO bucket: %s", bucket)
        except ImportError:
            logger.warning("minio package not installed — file storage disabled")
            return None
        except Exception as e:
            logger.warning("MinIO connection failed: %s — file storage disabled", e)
            _client = None
            return None
    return _client


def upload_document(data: bytes, doc_id: str, filename: str, doc_type: str = "manual") -> str:
    """Upload a document to MinIO and return the object path."""
    client = get_client()
    subdir = _DOC_TYPE_DIRS.get(doc_type, "manual")
    bucket = _get_minio_config().get("bucket", _BUCKET)
    object_name = f"{subdir}/{doc_id}_{filename}"

    if client is None:
        logger.warning("MinIO unavailable — skipping upload for %s", object_name)
        return object_name

    client.put_object(
        bucket,
        object_name,
        io.BytesIO(data),
        length=len(data),
    )
    logger.info("Uploaded %s to MinIO bucket=%s", object_name, bucket)
    return object_name


def download_document(object_path: str) -> bytes | None:
    """Download a document from MinIO."""
    client = get_client()
    if client is None:
        return None
    bucket = _get_minio_config().get("bucket", _BUCKET)
    try:
        response = client.get_object(bucket, object_path)
        data = response.read()
        response.close()
        response.release_conn()
        return data
    except Exception as e:
        logger.error("Failed to download %s: %s", object_path, e)
        return None


def list_documents(prefix: str = "", limit: int = 100) -> list[str]:
    """List document paths in MinIO."""
    client = get_client()
    if client is None:
        return []
    bucket = _get_minio_config().get("bucket", _BUCKET)
    objects = client.list_objects(bucket, prefix=prefix, recursive=True)
    paths = []
    for obj in objects:
        paths.append(obj.object_name)
        if len(paths) >= limit:
            break
    return paths

