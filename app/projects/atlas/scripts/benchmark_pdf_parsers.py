"""Compare low-cost pdfplumber text modes before escalating to OCR/layout models."""

from __future__ import annotations

import argparse
import asyncio
import json
import time

from atlas.core.clients import MinIOPDFReader
from atlas.core.config_manager import ConfigManager
from atlas.knowledge_production.pdf_preprocessor import (
    PikePDFUnlocker,
    assess_pdf_text_quality,
    extract_pdf_pages,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/config-home.yaml")
    parser.add_argument("--object-key", required=True)
    parser.add_argument("--excerpt-characters", type=int, default=1200)
    return parser.parse_args()


def _measure(pdf: bytes, *, layout: bool, excerpt_characters: int) -> dict:
    started = time.perf_counter()
    pages = extract_pdf_pages(pdf, layout=layout, allow_empty=True)
    quality = assess_pdf_text_quality(pages)
    text = "\n".join(page.text for page in pages)
    return {
        "mode": "layout" if layout else "standard",
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "quality": {
            "page_count": quality.page_count,
            "empty_page_count": quality.empty_page_count,
            "low_text_page_count": quality.low_text_page_count,
            "visible_characters": quality.visible_characters,
            "research_signal_count": quality.research_signal_count,
            "suspicious_axis_page_count": quality.suspicious_axis_page_count,
            "escalation_reasons": list(quality.escalation_reasons),
            "recommended_parser": quality.recommended_parser,
        },
        "excerpt": text[:excerpt_characters],
    }


async def main() -> int:
    args = parse_args()
    config = ConfigManager().init_config(args.config)
    endpoint, bucket = config.minio.resolve_bucket(config.minio.source_bucket)
    reader = MinIOPDFReader(
        endpoint.endpoint,
        endpoint.access_key,
        endpoint.secret_key,
        bucket,
        secure=endpoint.secure,
    )
    source = await asyncio.to_thread(reader.read, args.object_key)
    unlocked = await asyncio.to_thread(PikePDFUnlocker().unlock, source)
    results = await asyncio.gather(*(
        asyncio.to_thread(
            _measure,
            unlocked.content,
            layout=layout,
            excerpt_characters=args.excerpt_characters,
        )
        for layout in (False, True)
    ))
    print(json.dumps({
        "object_key": args.object_key,
        "source_bytes": len(source),
        "results": results,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
