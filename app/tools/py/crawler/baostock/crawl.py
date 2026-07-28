#!/usr/bin/env python
"""Download all BaoStock documentation into one Markdown file."""

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
from typing import Any, Mapping, Sequence
from urllib.parse import quote, urlencode, urljoin

import requests


# -----------------------------------------------------------------------------
# 运行配置：需要调整抓取行为时，直接修改这里。
# -----------------------------------------------------------------------------
SITE_ROOT = "https://baostock.com/"
MENU_API_URL = urljoin(SITE_ROOT, "helpdocs/api/menu")
MARKDOWN_API_ROOT = urljoin(SITE_ROOT, "helpdocs/api/markdown/")
OUTPUT_DIR = Path("docs/third_party_sdk/baostock")
LEGACY_OUTPUT_FILE = Path("docs/third_party_sdk/baostock.md")
EXCLUDED_MENU_TITLES = {"访问统计"}
DOCUMENTS_PER_FILE = 10
WORKERS = 4
TIMEOUT_SECONDS = 60.0
RETRIES = 3

MANIFEST_FILENAME = ".baostock-crawler-manifest.json"
USER_AGENT = "chaos-baostock-doc-crawler/1.0 (+https://baostock.com/)"
FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})(.*?)(?:\r?\n)?$")
ATX_HEADING_RE = re.compile(
    r"^(?P<indent>[ \t]{0,3})(?P<marks>#{1,6})(?P<rest>(?:[ \t]+|$).*?)(?P<newline>\r?\n)?$"
)
MARKDOWN_URL_RE = re.compile(
    r"(?P<prefix>!?\[[^\]\r\n]*\]\()"
    r"(?P<url><[^>\r\n]+>|[^)\s\r\n]+)"
    r"(?P<suffix>(?:\s+[\"'][^\"'\r\n]*[\"'])?\))"
)
LINKED_IMAGE_URL_RE = re.compile(
    r"(?P<prefix>\[!\[[^\]\r\n]*\]\([^)]+\)\]\()"
    r"(?P<url><[^>\r\n]+>|[^)\s\r\n]+)"
    r"(?P<suffix>(?:\s+[\"'][^\"'\r\n]*[\"'])?\))"
)
HTML_URL_RE = re.compile(
    r"(?P<prefix>\b(?:src|href)\s*=\s*[\"'])"
    r"(?P<url>[^\"']+)"
    r"(?P<suffix>[\"'])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MenuItem:
    title: str
    filename: str


@dataclass(frozen=True)
class DownloadedDocument:
    menu_item: MenuItem
    markdown: str


@dataclass(frozen=True)
class RenderedChunk:
    filename: str
    first_document_number: int
    last_document_number: int
    documents: tuple[DownloadedDocument, ...]
    content: str


class HttpClient:
    """Retrying HTTP client with one requests session per worker thread."""

    def __init__(self, timeout: float, retries: int) -> None:
        self.timeout = timeout
        self.retries = retries
        self._local = threading.local()

    def post_json(self, url: str) -> Any:
        response = self._post(url)
        try:
            return response.json()
        except requests.JSONDecodeError as exc:
            raise RuntimeError(f"response was not valid JSON: {url}") from exc

    def post_text(self, url: str) -> str:
        response = self._post(url)
        try:
            return response.content.decode("utf-8-sig")
        except UnicodeDecodeError:
            response.encoding = response.apparent_encoding or "utf-8"
            return response.text

    def _post(self, url: str) -> requests.Response:
        last_error: BaseException | None = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self._session().post(
                    url,
                    json={},
                    timeout=self.timeout,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    raise RuntimeError(
                        f"temporary HTTP {response.status_code} response from {url}"
                    )
                response.raise_for_status()
                return response
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
                    "Accept": "application/json, text/plain, */*",
                    "Referer": urljoin(SITE_ROOT, "mainContent?file=home.md"),
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


def parse_menu(payload: Any) -> list[MenuItem]:
    if not isinstance(payload, list):
        raise ValueError("BaoStock menu response must be a JSON array")

    items: list[MenuItem] = []
    seen_filenames: set[str] = set()
    for index, raw_item in enumerate(payload):
        if not isinstance(raw_item, Mapping):
            raise ValueError(f"BaoStock menu item {index} must be an object")

        title = str(raw_item.get("menuTitle") or "").strip()
        filename = str(raw_item.get("markdownFileName") or "").strip()
        if not title or not filename:
            raise ValueError(f"BaoStock menu item {index} is missing title or filename")
        if title in EXCLUDED_MENU_TITLES:
            continue

        validate_markdown_filename(filename)
        if filename in seen_filenames:
            continue
        seen_filenames.add(filename)
        items.append(MenuItem(title=normalize_menu_title(title), filename=filename))

    if not items:
        raise ValueError("BaoStock menu did not contain any Markdown documents")
    return items


def validate_markdown_filename(filename: str) -> None:
    path = PurePosixPath(filename)
    if (
        path.is_absolute()
        or len(path.parts) != 1
        or path.name != filename
        or path.suffix.lower() != ".md"
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"unsafe BaoStock Markdown filename: {filename!r}")


def normalize_menu_title(title: str) -> str:
    normalized = re.sub(r"^[\s-]+", "", title).strip()
    return normalized or title


def markdown_api_url(filename: str) -> str:
    validate_markdown_filename(filename)
    return urljoin(MARKDOWN_API_ROOT, quote(filename, safe=""))


def public_document_url(filename: str) -> str:
    validate_markdown_filename(filename)
    return urljoin(SITE_ROOT, "mainContent") + "?" + urlencode({"file": filename})


def transform_source_markdown(markdown: str) -> str:
    """Nest source headings and make relative resources usable outside the site."""

    output: list[str] = []
    in_fence = False
    fence_char = ""
    fence_length = 0

    for line in ensure_trailing_newline(markdown).splitlines(keepends=True):
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
            output.append(line)
            continue

        if in_fence:
            output.append(line)
            continue

        line = demote_heading(line, levels=2)
        line = absolutize_urls(line)
        output.append(line)

    return "".join(output)


def demote_heading(line: str, levels: int) -> str:
    heading = ATX_HEADING_RE.match(line)
    if not heading:
        return line
    new_level = min(6, len(heading.group("marks")) + levels)
    return (
        heading.group("indent")
        + "#" * new_level
        + heading.group("rest")
        + (heading.group("newline") or "")
    )


def absolutize_urls(line: str) -> str:
    def replace_markdown(match: re.Match[str]) -> str:
        original = match.group("url")
        wrapped = original.startswith("<") and original.endswith(">")
        url = original[1:-1] if wrapped else original
        absolute = make_absolute_url(url)
        if wrapped:
            absolute = f"<{absolute}>"
        return match.group("prefix") + absolute + match.group("suffix")

    def replace_html(match: re.Match[str]) -> str:
        return (
            match.group("prefix")
            + make_absolute_url(match.group("url"))
            + match.group("suffix")
        )

    line = LINKED_IMAGE_URL_RE.sub(replace_markdown, line)
    line = MARKDOWN_URL_RE.sub(replace_markdown, line)
    return HTML_URL_RE.sub(replace_html, line)


def make_absolute_url(url: str) -> str:
    stripped = url.strip()
    if (
        not stripped
        or stripped.startswith("#")
        or stripped.startswith("//")
        or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", stripped)
    ):
        return url
    return urljoin(SITE_ROOT, stripped)


def build_output_files(
    documents: Sequence[DownloadedDocument],
    documents_per_file: int,
) -> tuple[dict[str, str], list[RenderedChunk]]:
    if not documents:
        raise ValueError("at least one BaoStock document is required")
    if documents_per_file <= 0:
        raise ValueError("documents_per_file must be greater than zero")

    chunk_count = (len(documents) + documents_per_file - 1) // documents_per_file
    width = max(3, len(str(chunk_count)))
    chunks: list[RenderedChunk] = []
    files: dict[str, str] = {}

    for chunk_index, start in enumerate(
        range(0, len(documents), documents_per_file),
        start=1,
    ):
        group = tuple(documents[start : start + documents_per_file])
        filename = f"baostock-{chunk_index:0{width}d}.md"
        first_number = start + 1
        last_number = start + len(group)
        content = render_chunk_markdown(
            group,
            chunk_number=chunk_index,
            first_document_number=first_number,
            last_document_number=last_number,
        )
        chunk = RenderedChunk(
            filename=filename,
            first_document_number=first_number,
            last_document_number=last_number,
            documents=group,
            content=content,
        )
        chunks.append(chunk)
        files[filename] = content

    files["index.md"] = render_index(chunks, len(documents), documents_per_file)
    return files, chunks


def render_index(
    chunks: Sequence[RenderedChunk],
    document_count: int,
    documents_per_file: int,
) -> str:
    lines = [
        "# BaoStock SDK 文档索引",
        "",
        (
            "> 本目录由爬虫根据 "
            f"[BaoStock 官方文档菜单]({urljoin(SITE_ROOT, 'mainContent?file=home.md')})"
            f" 自动生成，共 {document_count} 份文档；每个分片最多包含 "
            f"{documents_per_file} 份文档。"
        ),
        "",
        "## 分片目录",
    ]

    for chunk in chunks:
        first_title = chunk.documents[0].menu_item.title
        last_title = chunk.documents[-1].menu_item.title
        title_range = (
            first_title if first_title == last_title else f"{first_title} → {last_title}"
        )
        lines.extend(
            [
                "",
                (
                    f"- [{chunk.filename.removesuffix('.md')}："
                    f"{escape_markdown_label(title_range)}]"
                    f"({chunk.filename})（{len(chunk.documents)} 份文档）"
                ),
            ]
        )
        for offset, document in enumerate(chunk.documents):
            document_number = chunk.first_document_number + offset
            title = escape_markdown_label(document.menu_item.title)
            lines.append(
                f"  - [{document_number}. {title}]"
                f"({chunk.filename}#{document_anchor(document_number)})"
            )

    return "\n".join(lines).rstrip() + "\n"


def render_chunk_markdown(
    documents: Sequence[DownloadedDocument],
    *,
    chunk_number: int,
    first_document_number: int,
    last_document_number: int,
) -> str:
    if not documents:
        raise ValueError("a BaoStock chunk must contain at least one document")

    lines = [
        f"# BaoStock SDK 文档 · 分片 {chunk_number:03d}",
        "",
        (
            f"> 本分片包含第 {first_document_number}–{last_document_number} 份文档。"
            "导航：[返回总索引](index.md)。"
        ),
        "",
        "## 本分片目录",
        "",
    ]

    for offset, document in enumerate(documents):
        document_number = first_document_number + offset
        title = escape_markdown_label(document.menu_item.title)
        lines.append(f"{document_number}. [{title}](#{document_anchor(document_number)})")

    for offset, document in enumerate(documents):
        number = first_document_number + offset
        item = document.menu_item
        lines.extend(
            [
                "",
                "---",
                "",
                f'<a id="{document_anchor(number)}"></a>',
                "",
                f"## {number}. {item.title}",
                "",
                (
                    f"> 官方页面：[{item.filename}]"
                    f"({public_document_url(item.filename)})"
                ),
                "",
                transform_source_markdown(document.markdown).rstrip(),
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def document_anchor(number: int) -> str:
    return f"baostock-document-{number:03d}"


def escape_markdown_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def resolve_output_dir() -> Path:
    if OUTPUT_DIR.is_absolute():
        return OUTPUT_DIR
    return find_repo_root(Path(__file__).resolve()) / OUTPUT_DIR


def resolve_legacy_output_file() -> Path:
    if LEGACY_OUTPUT_FILE.is_absolute():
        return LEGACY_OUTPUT_FILE
    return find_repo_root(Path(__file__).resolve()) / LEGACY_OUTPUT_FILE


def write_generated_files(
    output_dir: Path,
    files: Mapping[str, str],
    chunks: Sequence[RenderedChunk],
    *,
    document_count: int,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / MANIFEST_FILENAME
    previous_files = load_previous_generated_files(manifest_path)

    for relative_path, content in sorted(files.items()):
        target = resolve_output_path(output_dir, relative_path)
        atomic_write_text(target, content)

    current_files = set(files)
    for relative_path in sorted(previous_files - current_files):
        stale_path = resolve_output_path(output_dir, relative_path)
        if stale_path.is_file():
            stale_path.unlink()

    manifest = {
        "format_version": 1,
        "menu_api_url": MENU_API_URL,
        "documents_per_file": DOCUMENTS_PER_FILE,
        "document_count": document_count,
        "files": sorted(current_files),
        "chunks": [
            {
                "filename": chunk.filename,
                "first_document_number": chunk.first_document_number,
                "last_document_number": chunk.last_document_number,
                "document_count": len(chunk.documents),
            }
            for chunk in chunks
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
            temp_file.write(ensure_trailing_newline(content))
        os.replace(temp_name, path)
        temp_name = None
    finally:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)


def ensure_trailing_newline(value: str) -> str:
    return value.rstrip("\r\n") + "\n"


def validate_configuration() -> None:
    if DOCUMENTS_PER_FILE <= 0:
        raise ValueError("DOCUMENTS_PER_FILE must be greater than zero")
    if WORKERS <= 0:
        raise ValueError("WORKERS must be greater than zero")
    if TIMEOUT_SECONDS <= 0:
        raise ValueError("TIMEOUT_SECONDS must be greater than zero")
    if RETRIES <= 0:
        raise ValueError("RETRIES must be greater than zero")
    if OUTPUT_DIR.suffix:
        raise ValueError("OUTPUT_DIR must point to a directory")
    if LEGACY_OUTPUT_FILE.suffix.lower() != ".md":
        raise ValueError("LEGACY_OUTPUT_FILE must point to a Markdown file")


def crawl() -> None:
    validate_configuration()
    client = HttpClient(timeout=TIMEOUT_SECONDS, retries=RETRIES)

    print(f"Fetching BaoStock document menu: {MENU_API_URL}", flush=True)
    menu_items = parse_menu(client.post_json(MENU_API_URL))
    print(f"Discovered {len(menu_items)} Markdown documents", flush=True)

    def download(menu_item: MenuItem) -> DownloadedDocument:
        url = markdown_api_url(menu_item.filename)
        markdown = client.post_text(url)
        if not markdown.strip():
            raise RuntimeError(f"BaoStock returned an empty document: {menu_item.filename}")
        print(
            f"Fetched {menu_item.filename}: {len(markdown):,} characters",
            flush=True,
        )
        return DownloadedDocument(menu_item=menu_item, markdown=markdown)

    if WORKERS == 1:
        documents = [download(item) for item in menu_items]
    else:
        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            documents = list(executor.map(download, menu_items))

    output_dir = resolve_output_dir()
    files, chunks = build_output_files(documents, DOCUMENTS_PER_FILE)
    write_generated_files(
        output_dir,
        files,
        chunks,
        document_count=len(documents),
    )

    legacy_output_file = resolve_legacy_output_file()
    if legacy_output_file.is_file():
        legacy_output_file.unlink()
        print(f"Removed legacy output file: {legacy_output_file.resolve()}", flush=True)

    print(
        f"Wrote {len(documents)} documents across {len(chunks)} chunks to "
        f"{output_dir.resolve()}",
        flush=True,
    )


def main() -> None:
    crawl()


if __name__ == "__main__":
    main()
