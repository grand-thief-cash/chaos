"""Tests for document ingestion — text extraction and chunking."""
import pytest

from atlas.services.ingestion import (
    split_into_chunks,
    extract_text,
    compute_hash,
)


class TestComputeHash:
    def test_deterministic(self):
        h1 = compute_hash(b"hello")
        h2 = compute_hash(b"hello")
        assert h1 == h2

    def test_different_content_different_hash(self):
        h1 = compute_hash(b"hello")
        h2 = compute_hash(b"world")
        assert h1 != h2

    def test_returns_hex_string(self):
        h = compute_hash(b"test")
        assert len(h) == 64  # SHA-256 hex
        int(h, 16)  # Valid hex


class TestSplitIntoChunks:
    def test_short_text_single_chunk(self):
        chunks = split_into_chunks("Short paragraph.", max_chars=1000)
        assert len(chunks) == 1
        assert chunks[0] == "Short paragraph."

    def test_splits_at_paragraph_boundary(self):
        text = "Para 1.\n\nPara 2.\n\nPara 3."
        chunks = split_into_chunks(text, max_chars=20, overlap=0)
        assert len(chunks) >= 2
        assert "Para 1." in chunks[0]

    def test_handles_empty_text(self):
        chunks = split_into_chunks("", max_chars=1000)
        assert len(chunks) == 0

    def test_handles_single_paragraph(self):
        text = "A" * 500
        chunks = split_into_chunks(text, max_chars=1000)
        assert len(chunks) == 1

    def test_oversized_paragraph_force_split(self):
        text = "A" * 5000
        chunks = split_into_chunks(text, max_chars=1000, overlap=100)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 1000

    def test_overlap_present(self):
        text = ("A" * 200) + "\n\n" + ("B" * 200) + "\n\n" + ("C" * 200)
        chunks = split_into_chunks(text, max_chars=250, overlap=50)
        # With overlap, later chunks should start with tail of previous
        assert len(chunks) >= 2


class TestExtractText:
    def test_plain_text(self):
        data = "Hello world".encode("utf-8")
        text = extract_text("test.txt", data)
        assert text == "Hello world"

    def test_html_extraction(self):
        html = b"<html><body><p>Hello</p><script>bad()</script></body></html>"
        text = extract_text("page.html", html)
        assert "Hello" in text
        assert "bad()" not in text

    def test_unknown_extension_treated_as_text(self):
        data = "Some data".encode("utf-8")
        text = extract_text("file.xyz", data)
        assert text == "Some data"

