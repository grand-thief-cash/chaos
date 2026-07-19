from __future__ import annotations

from typing import Any, Mapping


class FeaturePlatformError(RuntimeError):
    """Structured error shared by validation, planning and execution."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 422,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.context = dict(context or {})

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "error": self.message}
        if self.context:
            payload["context"] = self.context
        return payload
