from __future__ import annotations

import json

from pydantic import ValidationError

from atlas.core.errors import ExtractionValidationError, ModelPDFUnreadableError
from atlas.models import ExtractionResult, Readability


class ExtractionValidator:
    """Reject structurally invalid or ungrounded model output before persistence."""

    def validate(
        self,
        raw: str,
        *,
        expected_document_id: str,
        expected_semantic_version: str,
        expected_title: str,
        maximum_page_number: int | None = None,
    ) -> ExtractionResult:
        if raw.lstrip().startswith("```"):
            raise ExtractionValidationError(["FORMAT_MARKDOWN_FENCE"])
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ExtractionValidationError([f"FORMAT_INVALID_JSON:{exc.msg}"]) from exc
        if not isinstance(payload, dict):
            raise ExtractionValidationError(["FORMAT_ROOT_NOT_OBJECT"])
        try:
            result = ExtractionResult.model_validate(payload)
        except ValidationError as exc:
            errors = [
                f"SCHEMA:{'.'.join(str(part) for part in error['loc'])}:{error['type']}"
                for error in exc.errors()
            ]
            raise ExtractionValidationError(errors) from exc
        errors: list[str] = []
        if result.document_id != expected_document_id:
            errors.append("CONSTRAINT_DOCUMENT_ID_MISMATCH")
        if result.semantic_version != expected_semantic_version:
            errors.append("CONSTRAINT_SEMANTIC_VERSION_MISMATCH")
        if maximum_page_number is not None:
            referenced_pages = [
                page
                for page in [
                    result.document_assessment.last_page_referenced,
                    *[
                        item.page_number
                        for item in result.entity_mentions
                    ],
                    *[
                        item.page_number
                        for item in result.relation_claims
                    ],
                    *[
                        item.page_number
                        for item in result.quantified_claims
                    ],
                    *[
                        item.page_number
                        for item in result.analyst_views
                    ],
                    *[
                        item.page_number
                        for item in result.unknown_semantic_terms
                    ],
                ]
                if page is not None
            ]
            if any(page > maximum_page_number for page in referenced_pages):
                errors.append("CONSTRAINT_PAGE_OUT_OF_RANGE")
        if errors:
            raise ExtractionValidationError(errors)
        assessment = result.document_assessment
        all_empty = not (
            result.entity_mentions
            or result.relation_claims
            or result.quantified_claims
            or result.analyst_views
        )
        title_matches = bool(
            assessment.observed_title
            and expected_title
            and (
                assessment.observed_title in expected_title
                or expected_title in assessment.observed_title
            )
        )
        if assessment.readability == Readability.UNREADABLE or (all_empty and not title_matches):
            raise ModelPDFUnreadableError(
                assessment.readability_reason or "model did not prove PDF readability"
            )
        return result
