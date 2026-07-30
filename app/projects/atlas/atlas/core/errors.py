class AtlasError(Exception):
    """Base domain error carrying a stable machine-readable code."""

    code = "ATLAS_ERROR"


class PDFUnlockError(AtlasError):
    code = "PDF_UNLOCK_FAILED"


class ModelPDFUnreadableError(AtlasError):
    code = "MODEL_PDF_UNREADABLE"


class PDFTextExtractionError(AtlasError):
    code = "PDF_TEXT_EXTRACTION_FAILED"


class ModelTimeoutError(AtlasError):
    code = "MODEL_TIMEOUT"


class ModelRequestError(AtlasError):
    code = "MODEL_REQUEST_FAILED"


class ExtractionValidationError(AtlasError):
    code = "MODEL_OUTPUT_INVALID"

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


class NoEnabledReportTypesError(AtlasError):
    code = "NO_ENABLED_REPORT_TYPES"
