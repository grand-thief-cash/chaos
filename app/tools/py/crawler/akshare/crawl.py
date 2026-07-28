#!/usr/bin/env python
"""Mirror and split the AKShare SDK documentation."""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence
from urllib.parse import quote, urljoin, urlsplit

import requests


# -----------------------------------------------------------------------------
# 运行配置：需要调整抓取行为时，直接修改这里。
# -----------------------------------------------------------------------------
SOURCE_INDEX_URL = "https://akshare.akfamily.xyz/_sources/data/index.rst.txt"
OUTPUT_DIR = Path("docs/third_party_sdk/akshare")
SECTIONS_PER_FILE = 10
WORKERS = 4
TIMEOUT_SECONDS = 60.0
RETRIES = 3

MANIFEST_FILENAME = ".akshare-crawler-manifest.json"
USER_AGENT = "chaos-akshare-doc-crawler/1.0 (+https://akshare.akfamily.xyz/)"

TOCTREE_RE = re.compile(r"^\s*\.\.\s+toctree::\s*$")
HEADING_RE = re.compile(
    r"^[ \t]{0,3}(#{1,6})(?:[ \t]+|$)(.*?)[ \t]*(?:\r?\n)?$"
)
FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})(.*?)(?:\r?\n)?$")
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)]\([^)]+\)")
SAFE_SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class SourceRef:
    route: str
    category: str
    slug: str


@dataclass(frozen=True)
class DownloadedDocument:
    ref: SourceRef
    source_url: str
    title: str
    markdown: str


@dataclass(frozen=True)
class ChunkPart:
    content: str
    headings: tuple[str, ...]


@dataclass(frozen=True)
class RenderedChunk:
    filename: str
    title: str
    first_heading: str
    last_heading: str
    headings: tuple[str, ...]
    section_count: int
    content: str


@dataclass(frozen=True)
class RenderedDocument:
    source: DownloadedDocument
    chunks: tuple[RenderedChunk, ...]


class HttpClient:
    """Small retrying HTTP client with one requests session per thread."""

    def __init__(self, timeout: float, retries: int) -> None:
        self.timeout = timeout
        self.retries = retries
        self._local = threading.local()

    def get_text(self, url: str, *, allow_not_found: bool = False) -> str | None:
        last_error: BaseException | None = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self._session().get(url, timeout=self.timeout)
                if response.status_code == 404 and allow_not_found:
                    return None
                if response.status_code == 429 or response.status_code >= 500:
                    raise RuntimeError(
                        f"temporary HTTP {response.status_code} response from {url}"
                    )
                response.raise_for_status()
                try:
                    return response.content.decode("utf-8-sig")
                except UnicodeDecodeError:
                    response.encoding = response.apparent_encoding or "utf-8"
                    return response.text
            except (requests.RequestException, RuntimeError) as exc:
                last_error = exc
                if attempt == self.retries:
                    break
                time.sleep(min(2 ** (attempt - 1), 8))
        raise RuntimeError(
            f"request failed after {self.retries} attempts: {url}: {last_error}"
        )

    def _session(self) -> requests.Session:
        session = getattr(self._local, "session", None)
        if session is None:
            session = requests.Session()
            session.headers.update(
                {
                    "Accept": "text/plain,text/markdown;q=0.9,*/*;q=0.5",
                    "User-Agent": USER_AGENT,
                }
            )
            self._local.session = session
        return session


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    raise RuntimeError(f"could not find repository root above {start}")


def parse_toctree_entries(rst_text: str) -> list[str]:
    """Return normalized local document routes from all RST toctree blocks."""

    entries: list[str] = []
    lines = rst_text.splitlines()
    index = 0
    while index < len(lines):
        if not TOCTREE_RE.match(lines[index]):
            index += 1
            continue

        index += 1
        while index < len(lines):
            line = lines[index]
            if not line.strip():
                index += 1
                continue
            if not line[:1].isspace():
                break

            value = line.strip()
            index += 1
            if value.startswith(":"):
                continue
            route = normalize_route(value)
            if route and route not in entries:
                entries.append(route)

    if not entries:
        raise ValueError("the AKShare source index did not contain any toctree entries")
    return entries


def normalize_route(value: str) -> str | None:
    titled_entry = re.fullmatch(r".+?\s*<([^>]+)>", value)
    if titled_entry:
        value = titled_entry.group(1)

    value = value.strip().split("#", 1)[0].strip()
    if not value or "://" in value or value.startswith("/"):
        return None

    route_path = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in route_path.parts):
        return None

    route = route_path.as_posix()
    for suffix in (".html", ".md", ".rst"):
        if route.endswith(suffix):
            route = route[: -len(suffix)]
            break
    return route


def make_source_ref(route: str) -> SourceRef:
    parts = PurePosixPath(route).parts
    if not parts:
        raise ValueError(f"invalid empty source route: {route!r}")
    category = safe_slug(parts[0])
    slug_parts = parts[1:] or parts
    slug = safe_slug("-".join(slug_parts))
    return SourceRef(route=route, category=category, slug=slug)


def safe_slug(value: str) -> str:
    slug = SAFE_SLUG_RE.sub("-", value.strip()).strip("._-").lower()
    if not slug:
        raise ValueError(f"value cannot be converted to a safe filename: {value!r}")
    return slug


def site_root_from_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"expected an HTTP(S) source index URL, got: {url}")
    return f"{parsed.scheme}://{parsed.netloc}/"


def fetch_document(
    ref: SourceRef,
    *,
    site_root: str,
    client: HttpClient,
) -> DownloadedDocument:
    encoded_route = quote(ref.route, safe="/")
    candidates = [
        urljoin(site_root, f"_sources/data/{encoded_route}.md.txt"),
        urljoin(site_root, f"_sources/data/{encoded_route}.rst.txt"),
    ]
    for source_url in candidates:
        markdown = client.get_text(source_url, allow_not_found=True)
        if markdown is not None:
            return DownloadedDocument(
                ref=ref,
                source_url=source_url,
                title=extract_document_title(markdown, ref.route),
                markdown=ensure_trailing_newline(markdown),
            )
    raise RuntimeError(
        f"no Markdown or RST source was found for {ref.route}: {', '.join(candidates)}"
    )


def extract_document_title(markdown: str, fallback: str) -> str:
    in_fence = False
    fence_char = ""
    fence_length = 0
    for line in markdown.splitlines(keepends=True):
        fence = FENCE_RE.match(line)
        if fence:
            marker = fence.group(1)
            if not in_fence:
                in_fence = True
                fence_char = marker[0]
                fence_length = len(marker)
            elif (
                marker[0] == fence_char
                and len(marker) >= fence_length
                and not fence.group(2).strip()
            ):
                in_fence = False
            continue
        if in_fence:
            continue
        heading = HEADING_RE.match(line)
        if heading and len(heading.group(1)) <= 2:
            title = clean_heading(heading.group(2))
            if title:
                return title
    return fallback


def split_markdown_by_h3(markdown: str, sections_per_file: int) -> list[ChunkPart]:
    if sections_per_file <= 0:
        raise ValueError("sections_per_file must be greater than zero")

    positions = find_h3_positions(markdown)
    if not positions:
        return [ChunkPart(content=ensure_trailing_newline(markdown), headings=())]

    preamble = markdown[: positions[0][0]]
    sections: list[tuple[str, str]] = []
    for section_index, (start, heading) in enumerate(positions):
        end = (
            positions[section_index + 1][0]
            if section_index + 1 < len(positions)
            else len(markdown)
        )
        sections.append((heading, markdown[start:end]))

    chunks: list[ChunkPart] = []
    for start in range(0, len(sections), sections_per_file):
        group = sections[start : start + sections_per_file]
        body = "".join(section_text for _, section_text in group)
        if start == 0:
            body = preamble + body
        chunks.append(
            ChunkPart(
                content=ensure_trailing_newline(body),
                headings=tuple(heading for heading, _ in group),
            )
        )
    return chunks


def find_h3_positions(markdown: str) -> list[tuple[int, str]]:
    positions: list[tuple[int, str]] = []
    offset = 0
    in_fence = False
    fence_char = ""
    fence_length = 0

    for line in markdown.splitlines(keepends=True):
        fence = FENCE_RE.match(line)
        if fence:
            marker = fence.group(1)
            if not in_fence:
                in_fence = True
                fence_char = marker[0]
                fence_length = len(marker)
            elif (
                marker[0] == fence_char
                and len(marker) >= fence_length
                and not fence.group(2).strip()
            ):
                in_fence = False
            offset += len(line)
            continue

        if not in_fence:
            heading = HEADING_RE.match(line)
            if heading and len(heading.group(1)) == 3:
                positions.append((offset, clean_heading(heading.group(2))))
        offset += len(line)
    return positions


def clean_heading(value: str) -> str:
    value = re.sub(r"[ \t]+#+[ \t]*$", "", value.strip())
    value = MARKDOWN_LINK_RE.sub(r"\1", value)
    value = value.replace("`", "")
    return re.sub(r"\s+", " ", value).strip()


def render_document(
    document: DownloadedDocument, sections_per_file: int
) -> RenderedDocument:
    parts = split_markdown_by_h3(document.markdown, sections_per_file)
    width = max(3, len(str(len(parts))))
    chunks: list[RenderedChunk] = []
    for number, part in enumerate(parts, start=1):
        filename = f"{document.ref.slug}-{number:0{width}d}.md"
        first_heading = part.headings[0] if part.headings else document.title
        last_heading = part.headings[-1] if part.headings else document.title
        title = f"{document.title} · 分片 {number:0{width}d}"
        navigation = (
            f"# {title}\n\n"
            f"> 官方源码：[{document.ref.route}]({document.source_url})\n"
            f">\n"
            f"> 导航：[返回分类索引](index.md) · [返回总索引](../index.md)\n\n"
        )
        chunks.append(
            RenderedChunk(
                filename=filename,
                title=title,
                first_heading=first_heading,
                last_heading=last_heading,
                headings=part.headings,
                section_count=len(part.headings),
                content=navigation + part.content.lstrip("\ufeff"),
            )
        )
    return RenderedDocument(source=document, chunks=tuple(chunks))


def build_output_files(
    documents: Sequence[DownloadedDocument],
    *,
    sections_per_file: int,
    source_index_url: str,
) -> tuple[dict[str, str], list[RenderedDocument]]:
    rendered = [
        render_document(document, sections_per_file) for document in documents
    ]
    files: dict[str, str] = {}

    category_order: list[str] = []
    by_category: dict[str, list[RenderedDocument]] = {}
    for document in rendered:
        category = document.source.ref.category
        if category not in by_category:
            category_order.append(category)
            by_category[category] = []
        by_category[category].append(document)
        for chunk in document.chunks:
            relative_path = f"{category}/{chunk.filename}"
            if relative_path in files:
                raise ValueError(f"duplicate generated output path: {relative_path}")
            files[relative_path] = chunk.content

    for category in category_order:
        files[f"{category}/index.md"] = render_category_index(
            category, by_category[category]
        )
    files["index.md"] = render_root_index(
        category_order,
        by_category,
        source_index_url=source_index_url,
        sections_per_file=sections_per_file,
    )
    return files, rendered


def render_category_index(
    category: str, documents: Sequence[RenderedDocument]
) -> str:
    lines = [
        f"# AKShare `{category}` SDK 文档",
        "",
        "[返回总索引](../index.md)",
        "",
    ]
    for document in documents:
        source = document.source
        lines.extend(
            [
                f"## {escape_markdown_label(source.title)}",
                "",
                f"- 文档路径：`{source.ref.route}`",
                f"- [AKShare 官方源码]({source.source_url})",
                "",
            ]
        )
        for chunk in document.chunks:
            lines.append(
                f"- [{chunk_link_label(chunk)}]({chunk.filename})"
                f"（{chunk.section_count} 个 `###` 章节）"
            )
            for heading in chunk.headings:
                lines.append(f"  - {escape_markdown_label(heading)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_root_index(
    category_order: Sequence[str],
    by_category: Mapping[str, Sequence[RenderedDocument]],
    *,
    source_index_url: str,
    sections_per_file: int,
) -> str:
    lines = [
        "# AKShare SDK 文档索引",
        "",
        (
            f"> 本目录由爬虫根据 [AKShare 官方数据字典源码]({source_index_url})"
            f" 自动生成；每个分片最多包含 {sections_per_file} 个 `###` 章节。"
        ),
        "",
    ]
    for category in category_order:
        lines.extend(
            [
                f"## `{category}`",
                "",
                f"- [进入 `{category}` 分类索引]({category}/index.md)",
            ]
        )
        for document in by_category[category]:
            lines.append(
                f"- `{document.source.ref.route}` — "
                f"{escape_markdown_label(document.source.title)}"
            )
            for chunk in document.chunks:
                lines.append(
                    f"  - [{chunk_link_label(chunk)}]"
                    f"({category}/{chunk.filename})"
                    f"（{chunk.section_count} 个 `###` 章节）"
                )
                for heading in chunk.headings:
                    lines.append(f"    - {escape_markdown_label(heading)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def chunk_link_label(chunk: RenderedChunk) -> str:
    if chunk.first_heading == chunk.last_heading:
        range_text = chunk.first_heading
    else:
        range_text = f"{chunk.first_heading} → {chunk.last_heading}"
    return escape_markdown_label(f"{chunk.title}：{range_text}")


def escape_markdown_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def write_generated_files(
    output_dir: Path,
    files: Mapping[str, str],
    rendered: Sequence[RenderedDocument],
    *,
    source_index_url: str,
    sections_per_file: int,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / MANIFEST_FILENAME
    previous_files = load_previous_generated_files(manifest_path)

    for relative_path, content in sorted(files.items()):
        target = resolve_output_path(output_dir, relative_path)
        atomic_write_text(target, ensure_trailing_newline(content))

    current_files = set(files)
    for relative_path in sorted(previous_files - current_files, reverse=True):
        stale_path = resolve_output_path(output_dir, relative_path)
        if stale_path.is_file():
            stale_path.unlink()
            prune_empty_parents(stale_path.parent, output_dir)

    manifest = {
        "format_version": 1,
        "source_index_url": source_index_url,
        "sections_per_file": sections_per_file,
        "files": sorted(current_files),
        "sources": [
            {
                "route": document.source.ref.route,
                "source_url": document.source.source_url,
                "title": document.source.title,
                "category": document.source.ref.category,
                "chunks": len(document.chunks),
            }
            for document in rendered
        ],
    }
    atomic_write_text(
        manifest_path,
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def load_previous_generated_files(manifest_path: Path) -> set[str]:
    if not manifest_path.is_file():
        return set()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read existing crawler manifest: {manifest_path}") from exc
    files = payload.get("files", [])
    if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
        raise RuntimeError(f"invalid generated file list in manifest: {manifest_path}")
    return set(files)


def resolve_output_path(output_dir: Path, relative_path: str) -> Path:
    path = PurePosixPath(relative_path)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe generated output path: {relative_path!r}")
    return output_dir.joinpath(*path.parts)


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as temp_file:
            temp_name = temp_file.name
            temp_file.write(content)
        os.replace(temp_name, path)
        temp_name = None
    finally:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)


def prune_empty_parents(path: Path, stop: Path) -> None:
    while path != stop:
        try:
            path.rmdir()
        except OSError:
            return
        path = path.parent


def ensure_trailing_newline(value: str) -> str:
    return value.rstrip("\r\n") + "\n"


def crawl() -> None:
    validate_configuration()
    output_dir = resolve_configured_output_dir()
    client = HttpClient(timeout=TIMEOUT_SECONDS, retries=RETRIES)
    print(f"Fetching source index: {SOURCE_INDEX_URL}", flush=True)
    source_index = client.get_text(SOURCE_INDEX_URL)
    if source_index is None:
        raise RuntimeError(f"source index was not found: {SOURCE_INDEX_URL}")

    routes = parse_toctree_entries(source_index)
    refs = [make_source_ref(route) for route in routes]
    print(f"Discovered {len(refs)} source documents", flush=True)

    site_root = site_root_from_url(SOURCE_INDEX_URL)

    def download(ref: SourceRef) -> DownloadedDocument:
        document = fetch_document(ref, site_root=site_root, client=client)
        print(
            f"Fetched {ref.route}: {len(document.markdown):,} characters",
            flush=True,
        )
        return document

    if WORKERS == 1:
        documents = [download(ref) for ref in refs]
    else:
        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            documents = list(executor.map(download, refs))

    files, rendered = build_output_files(
        documents,
        sections_per_file=SECTIONS_PER_FILE,
        source_index_url=SOURCE_INDEX_URL,
    )
    write_generated_files(
        output_dir,
        files,
        rendered,
        source_index_url=SOURCE_INDEX_URL,
        sections_per_file=SECTIONS_PER_FILE,
    )

    chunk_count = sum(len(document.chunks) for document in rendered)
    category_count = len({document.ref.category for document in documents})
    print(
        f"Wrote {chunk_count} chunks across {category_count} categories to "
        f"{output_dir.resolve()}",
        flush=True,
    )


def resolve_configured_output_dir() -> Path:
    if OUTPUT_DIR.is_absolute():
        return OUTPUT_DIR
    repo_root = find_repo_root(Path(__file__).resolve())
    return repo_root / OUTPUT_DIR


def validate_configuration() -> None:
    if SECTIONS_PER_FILE <= 0:
        raise ValueError("SECTIONS_PER_FILE must be greater than zero")
    if WORKERS <= 0:
        raise ValueError("WORKERS must be greater than zero")
    if TIMEOUT_SECONDS <= 0:
        raise ValueError("TIMEOUT_SECONDS must be greater than zero")
    if RETRIES <= 0:
        raise ValueError("RETRIES must be greater than zero")


def main() -> None:
    crawl()


if __name__ == "__main__":
    main()
