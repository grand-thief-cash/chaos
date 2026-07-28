from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from atlas.core.errors import PDFUnlockError


@dataclass(frozen=True, slots=True)
class PDFUnlockResult:
    content: bytes
    page_count: int
    status: str = "UNLOCKED_IN_MEMORY"


class PikePDFUnlocker:
    """Remove owner restrictions in memory; this fixed behavior has no config switch."""

    version = "pikepdf-v1"

    def unlock(self, source: bytes) -> PDFUnlockResult:
        if not source:
            raise PDFUnlockError("empty PDF input")
        try:
            import pikepdf

            source_stream = BytesIO(source)
            output_stream = BytesIO()
            try:
                with pikepdf.Pdf.open(source_stream, password="") as pdf:
                    page_count = len(pdf.pages)
                    pdf.save(output_stream, encryption=False)
                return PDFUnlockResult(output_stream.getvalue(), page_count)
            finally:
                output_stream.close()
                source_stream.close()
        except PDFUnlockError:
            raise
        except Exception as exc:
            raise PDFUnlockError(str(exc)) from exc
