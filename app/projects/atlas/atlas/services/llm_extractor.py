"""LLM-based structured extraction — calls LLM with the skill prompt and validates output."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from atlas.connectors.llm_client import call_extraction
from atlas.models.graph_schema import ExtractionResult

logger = logging.getLogger(__name__)

# Path to the skill prompt (relative to project root)
_SKILL_PATH = Path(__file__).resolve().parents[3] / ".." / "tools" / "py" / "skills" / "industry_extraction_skills.md"

_cached_prompt: str | None = None


def _load_skill_prompt() -> str:
    global _cached_prompt
    if _cached_prompt is None:
        # Try multiple possible locations
        candidates = [
            _SKILL_PATH,
            Path(__file__).resolve().parents[4] / "tools" / "py" / "skills" / "industry_extraction_skills.md",
        ]
        for p in candidates:
            if p.exists():
                _cached_prompt = p.read_text(encoding="utf-8")
                logger.info("Loaded extraction skill prompt from %s", p)
                break
        if _cached_prompt is None:
            raise FileNotFoundError(
                f"Cannot find industry_extraction_skills.md in {[str(c) for c in candidates]}"
            )
    return _cached_prompt


async def extract_from_chunk(
    chunk_text: str,
    doc_id: str = "",
    chunk_index: int = 0,
    model: str | None = None,
) -> tuple[ExtractionResult | None, dict[str, Any]]:
    """Extract structured knowledge graph data from a single text chunk.

    Returns:
        (validated_result, raw_llm_response_dict)
        validated_result is None if validation failed.
    """
    prompt = _load_skill_prompt()

    raw = await call_extraction(chunk_text, system_prompt=prompt, model=model)

    parsed = raw.get("parsed")
    if parsed is None:
        logger.error(
            "Extraction returned non-JSON for doc=%s chunk=%d", doc_id, chunk_index
        )
        return None, raw

    # Inject doc_id into meta
    if "meta" not in parsed:
        parsed["meta"] = {}
    parsed["meta"]["doc_id"] = doc_id

    # Validate with Pydantic
    try:
        result = ExtractionResult.model_validate(parsed)
    except ValidationError as e:
        logger.error(
            "Extraction result validation failed for doc=%s chunk=%d: %s",
            doc_id, chunk_index, e,
        )
        return None, raw

    node_counts = {
        k: len(getattr(result.nodes, k))
        for k in result.nodes.model_fields
        if len(getattr(result.nodes, k)) > 0
    }
    logger.info(
        "Extracted doc=%s chunk=%d → nodes=%s edges=%d (cost=$%.4f)",
        doc_id, chunk_index, node_counts, len(result.edges), raw.get("cost", 0),
    )
    return result, raw


async def extract_document_chunks(
    chunks: list[str],
    doc_id: str = "",
    model: str | None = None,
) -> list[tuple[ExtractionResult | None, dict[str, Any]]]:
    """Extract all chunks of a document sequentially.

    For batch parallelism, use the batch_extract pipeline instead.
    """
    results = []
    for i, chunk in enumerate(chunks):
        result, raw = await extract_from_chunk(chunk, doc_id=doc_id, chunk_index=i, model=model)
        results.append((result, raw))
    return results

