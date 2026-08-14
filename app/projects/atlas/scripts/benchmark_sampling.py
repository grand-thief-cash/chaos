"""Run Atlas field discovery on one MinIO PDF without writing database state.

Example:
    python scripts/benchmark_sampling.py \
      --config config/config-home.yaml \
      --object-key 'stock/600998/2024-07-01_....pdf' \
      --document-id eastmoney:AP202407011637141093 \
      --title '拟启动医药物流仓储资产Pre-REITs项目，持续推进不动产证券化战略落地' \
      --report-type stock
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time

from atlas.core.clients import (
    MinIOPDFReader,
    OllamaChatClient,
    OpenAICompatiblePDFClient,
    OpenRouterTextPDFClient,
    ZhipuTextPDFClient,
)
from atlas.core.config_manager import ConfigManager
from atlas.application.runtime import _build_stage_harness
from atlas.core.llm import KeyPool
from atlas.knowledge_production.extractor import (
    FreeExtractionExtractor,
    FreeExtractionPromptBuilder,
)
from atlas.knowledge_production.pdf_preprocessor import (
    PikePDFUnlocker,
    PDFTextPage,
    RapidOCRLayoutParser,
    chunk_pdf_pages,
    extract_pdf_pages,
)
from atlas.models import ModelProvider


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/config-home.yaml")
    parser.add_argument("--object-key", required=True)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--report-type", required=True)
    parser.add_argument("--maximum-chunks", type=int)
    parser.add_argument("--attempts", type=int, default=1)
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    config = ConfigManager().init_config(args.config)
    knowledge = config.engine.knowledge_engine
    maximum_chunks = args.maximum_chunks or knowledge.sampling_maximum_chunks
    _, model = config.llm.model_for_role("extraction")
    harness = _build_stage_harness("sampling_extraction", config, {}, {})
    pool = KeyPool(model.api_keys, total_concurrency=1)
    if harness is not None:
        client = harness
    elif model.provider == ModelProvider.OLLAMA:
        client = OllamaChatClient(model, pool)
    elif model.provider == ModelProvider.ZHIPU_TEXT:
        client = ZhipuTextPDFClient(model, pool)
    elif model.provider == ModelProvider.OPENAI_COMPATIBLE_PDF:
        client = OpenAICompatiblePDFClient(model, pool)
    else:
        client = OpenRouterTextPDFClient(model, pool)

    endpoint, bucket = config.minio.resolve_sampling_bucket()
    reader = MinIOPDFReader(
        endpoint.endpoint,
        endpoint.access_key,
        endpoint.secret_key,
        bucket,
        secure=endpoint.secure,
    )
    started = time.perf_counter()
    source = await asyncio.to_thread(reader.read, args.object_key)
    unlocked = await asyncio.to_thread(PikePDFUnlocker().unlock, source)
    try:
        pages = await asyncio.to_thread(extract_pdf_pages, unlocked.content)
    except Exception:
        # Extraction itself owns the gated OCR fallback. Benchmark metadata
        # still needs a harmless representation before that call.
        pages = [PDFTextPage(1, "")]
    chunk_output_tokens = knowledge.sampling_chunk_output_tokens
    prompt_reserve_tokens = knowledge.sampling_prompt_reserve_tokens
    chunk_budget = max(
        512,
        model.context_window_tokens - chunk_output_tokens - prompt_reserve_tokens,
    )
    chunks = chunk_pdf_pages(
        pages,
        maximum_chunk_tokens=chunk_budget,
        maximum_chunks=maximum_chunks,
    )
    extractor = FreeExtractionExtractor(
        client,
        prompt_builder=FreeExtractionPromptBuilder(knowledge.prompt_mapping_path),
        maximum_total_attempts=args.attempts,
        maximum_chunks=maximum_chunks,
        chunk_output_tokens=chunk_output_tokens,
        merge_output_tokens=knowledge.sampling_merge_output_tokens,
        prompt_reserve_tokens=prompt_reserve_tokens,
        thinking_mode=None if harness is not None else model.thinking_mode,
        layout_sidecar=(
            RapidOCRLayoutParser(
                dpi=knowledge.document_local_ocr_dpi,
                maximum_pages=knowledge.document_local_ocr_maximum_pages,
            )
            if knowledge.document_local_ocr_enabled
            else None
        ),
    )
    try:
        result, attempts = await extractor.extract(
            pdf=unlocked.content,
            filename=args.object_key.rsplit("/", 1)[-1],
            document_id=args.document_id,
            title=args.title,
            report_type=args.report_type,
            report_profile={},
        )
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            await close()
    payload = {
        "benchmark": {
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "source_bytes": len(source),
            "page_count": len(pages),
            "extracted_characters": sum(len(page.text) for page in pages),
            "context_window_tokens": model.context_window_tokens,
            "chunk_input_budget_tokens": chunk_budget,
            "chunk_page_ranges": [chunk.page_numbers for chunk in chunks],
            "coverage_truncated": any(chunk.coverage_truncated for chunk in chunks),
            "model_attempts": attempts,
            "document_json_top_level_keys": list(result.content.keys()),
            "document_json_characters": len(json.dumps(result.content, ensure_ascii=False)),
        },
        "result": result.model_dump(mode="json"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.readable else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
