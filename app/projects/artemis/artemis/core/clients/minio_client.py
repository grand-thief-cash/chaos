"""MinIO object-storage client for artemis.

Research-report (and future) tasks sink downloaded PDFs to MinIO via this
client. It wraps the `minio` Python SDK and exposes a narrow interface
(`put_pdf`) so tasks stay decoupled from the SDK.

When MinIO is not configured (no `minio.endpoint` in config.yaml) or the
client fails to initialize, `NoopMinioClient` is used instead — it logs a
warning and returns the object key unchanged so the task pipeline can be
exercised end-to-end before a real MinIO instance is available.
"""
from io import BytesIO
from typing import Any, Optional

from artemis.core.clients.dept_clients import BaseDeptServiceClient


class MinioClient(BaseDeptServiceClient):
    """Real MinIO client backed by the `minio` SDK.

    Object key convention (research reports):
        stock:    "{stock_prefix}/{symbol}/{publish_date}_{title}.pdf"
        industry: "{industry_prefix}/{industry_code}/{publish_date}_{title}.pdf"

    The caller builds the object key; this client only puts bytes and returns
    the same object key (the path within the bucket). The bucket name is held
    here so callers don't need to know it.
    """

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        secure: bool,
        bucket: str,
        stock_prefix: str = "stock",
        industry_prefix: str = "industry",
        logger: Any = None,
    ):
        from minio import Minio  # imported lazily so missing dep doesn't break import

        self.endpoint = endpoint
        self.bucket = bucket
        self.stock_prefix = stock_prefix
        self.industry_prefix = industry_prefix
        self.logger = logger
        self._client = Minio(
            endpoint,
            access_key=access_key or None,
            secret_key=secret_key or None,
            secure=secure,
        )
        # Ensure the bucket exists (best-effort; logged on failure).
        try:
            if not self._client.bucket_exists(bucket):
                self._client.make_bucket(bucket)
                if self.logger:
                    self.logger.info({'event': 'minio_bucket_created', 'bucket': bucket})
        except Exception as e:
            if self.logger:
                self.logger.warning({
                    'event': 'minio_bucket_check_failed',
                    'bucket': bucket,
                    'endpoint': endpoint,
                    'error': str(e),
                })

    def put_pdf(self, object_key: str, data: bytes, content_type: str = "application/pdf") -> str:
        """Put PDF bytes under object_key in the bucket. Returns object_key."""
        stream = BytesIO(data)
        self._client.put_object(
            self.bucket, object_key, stream,
            length=len(data), content_type=content_type,
        )
        if self.logger:
            self.logger.info({
                'event': 'minio_put_pdf',
                'bucket': self.bucket,
                'object_key': object_key,
                'size': len(data),
            })
        return object_key

    def is_noop(self) -> bool:
        return False


class NoopMinioClient(BaseDeptServiceClient):
    """Mock MinIO client used when MinIO is not configured.

    Returns the object key unchanged (no bytes stored) and logs a warning so
    the absence of real storage is visible. This lets the full download →
    sink → phoenixA-record pipeline run during development.
    """

    def __init__(self, logger: Any = None, bucket: str = "research-report",
                 stock_prefix: str = "stock", industry_prefix: str = "industry"):
        self.logger = logger
        self.bucket = bucket
        self.stock_prefix = stock_prefix
        self.industry_prefix = industry_prefix

    def put_pdf(self, object_key: str, data: bytes, content_type: str = "application/pdf") -> str:
        if self.logger:
            self.logger.warning({
                'event': 'minio_noop_put_pdf',
                'object_key': object_key,
                'size': len(data),
                'reason': 'minio not configured; PDF bytes discarded',
            })
        return object_key

    def is_noop(self) -> bool:
        return True


def build_minio_client_from_config(logger: Any = None) -> BaseDeptServiceClient:
    """Build a MinioClient from cfg_mgr, falling back to NoopMinioClient.

    Reads `minio` (connection) and `minio_business` (bucket/prefixes) config
    sections. If endpoint is empty or construction fails, returns the noop
    client so tasks degrade gracefully instead of crashing.
    """
    from artemis.core.config_manager import cfg_mgr

    try:
        config = cfg_mgr.get_config()
        minio_cfg = config.minio
        biz_cfg = config.minio_business
    except Exception as e:
        if logger:
            logger.warning({'event': 'minio_config_unavailable', 'error': str(e)})
        return NoopMinioClient(logger=logger)

    if not minio_cfg or not minio_cfg.endpoint:
        return NoopMinioClient(
            logger=logger,
            bucket=biz_cfg.bucket if biz_cfg else "research-report",
            stock_prefix=biz_cfg.stock_prefix if biz_cfg else "stock",
            industry_prefix=biz_cfg.industry_prefix if biz_cfg else "industry",
        )

    try:
        return MinioClient(
            endpoint=minio_cfg.endpoint,
            access_key=minio_cfg.access_key,
            secret_key=minio_cfg.secret_key,
            secure=minio_cfg.secure,
            bucket=biz_cfg.bucket,
            stock_prefix=biz_cfg.stock_prefix,
            industry_prefix=biz_cfg.industry_prefix,
            logger=logger,
        )
    except Exception as e:
        if logger:
            logger.warning({
                'event': 'minio_client_init_failed',
                'endpoint': minio_cfg.endpoint,
                'error': str(e),
            })
        return NoopMinioClient(
            logger=logger,
            bucket=biz_cfg.bucket,
            stock_prefix=biz_cfg.stock_prefix,
            industry_prefix=biz_cfg.industry_prefix,
        )
