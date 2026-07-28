from __future__ import annotations

from typing import Protocol


class PDFObjectReader(Protocol):
    def read(self, object_key: str) -> bytes: ...


class MinIOPDFReader:
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        *,
        secure: bool = False,
    ) -> None:
        from minio import Minio

        self.bucket = bucket
        self._client = Minio(
            endpoint,
            access_key=access_key or None,
            secret_key=secret_key or None,
            secure=secure,
        )

    def read(self, object_key: str) -> bytes:
        bucket, key = self._resolve(object_key)
        response = self._client.get_object(bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def _resolve(self, object_key: str) -> tuple[str, str]:
        if object_key.startswith("s3://"):
            bucket, separator, key = object_key[5:].partition("/")
            if not separator or not bucket or not key:
                raise ValueError("invalid s3 object key")
            return bucket, key
        return self.bucket, object_key.lstrip("/")
