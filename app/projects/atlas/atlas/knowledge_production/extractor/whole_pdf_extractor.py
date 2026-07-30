from __future__ import annotations

from atlas.core.clients import PDFLLMClient
from atlas.core.errors import ExtractionValidationError
from atlas.knowledge_production.extractor.extraction_validator import ExtractionValidator
from atlas.knowledge_production.extractor.prompt_builder import PromptBuilder
from atlas.models import ExtractionResult


class WholePDFExtractor:
    def __init__(
        self,
        llm: PDFLLMClient,
        *,
        prompt_builder: PromptBuilder | None = None,
        validator: ExtractionValidator | None = None,
        maximum_total_attempts: int = 3,
    ) -> None:
        self.llm = llm
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.validator = validator or ExtractionValidator()
        self.maximum_total_attempts = maximum_total_attempts

    async def extract(
        self,
        *,
        pdf: bytes,
        filename: str,
        document_id: str,
        title: str,
        report_type: str,
        semantic_config: dict,
        report_profile: dict,
        page_count: int | None = None,
    ) -> tuple[ExtractionResult, int, list[str]]:
        validation_errors: list[str] = []
        for attempt in range(1, self.maximum_total_attempts + 1):
            prompt = self.prompt_builder.build(
                document_id=document_id,
                title=title,
                report_type=report_type,
                semantic_config=semantic_config,
                report_profile=report_profile,
                validation_errors=validation_errors or None,
            )
            raw = await self.llm.complete_pdf(prompt=prompt, pdf=pdf, filename=filename)
            try:
                result = self.validator.validate(
                    raw,
                    expected_document_id=document_id,
                    expected_semantic_version=semantic_config["version"],
                    expected_title=title,
                    maximum_page_number=page_count,
                )
                return result, attempt, validation_errors
            except ExtractionValidationError as exc:
                validation_errors.extend(exc.errors)
                if attempt == self.maximum_total_attempts:
                    raise ExtractionValidationError(validation_errors) from exc
        raise AssertionError("unreachable")
