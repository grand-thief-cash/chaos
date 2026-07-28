from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import crawl


class ParseToctreeTests(unittest.TestCase):
    def test_parses_multiple_blocks_and_normalizes_titled_entries(self) -> None:
        source = """
Title
=====

.. toctree::
    :maxdepth: 6

    stock/stock
    Funds <fund/fund_public.md>

Other text

.. toctree::

    qhkc/index.rst
    https://example.com/external
"""
        self.assertEqual(
            ["stock/stock", "fund/fund_public", "qhkc/index"],
            crawl.parse_toctree_entries(source),
        )


class SplitMarkdownTests(unittest.TestCase):
    def test_splits_every_ten_h3_headings_and_ignores_fenced_code(self) -> None:
        sections = []
        for number in range(1, 22):
            body = f"### Section {number}\n\nBody {number}\n\n"
            if number == 5:
                body += "```markdown\n### Not a real section\n```\n\n"
            sections.append(body)
        markdown = "## Document title\n\nPreamble\n\n" + "".join(sections)

        chunks = crawl.split_markdown_by_h3(markdown, 10)

        self.assertEqual([10, 10, 1], [len(chunk.headings) for chunk in chunks])
        self.assertIn("Preamble", chunks[0].content)
        self.assertNotIn("Preamble", chunks[1].content)
        self.assertEqual("Section 1", chunks[0].headings[0])
        self.assertEqual("Section 21", chunks[-1].headings[-1])

    def test_document_without_h3_is_kept_in_one_chunk(self) -> None:
        chunks = crawl.split_markdown_by_h3("## Only a title\n\nBody", 10)
        self.assertEqual(1, len(chunks))
        self.assertEqual((), chunks[0].headings)
        self.assertIn("Body", chunks[0].content)


class OutputTests(unittest.TestCase):
    def make_document(self, route: str, title: str, count: int) -> crawl.DownloadedDocument:
        ref = crawl.make_source_ref(route)
        markdown = f"## {title}\n\n" + "".join(
            f"### Section {number}\n\nBody\n\n" for number in range(1, count + 1)
        )
        return crawl.DownloadedDocument(
            ref=ref,
            source_url=f"https://example.test/{route}.md.txt",
            title=title,
            markdown=markdown,
        )

    def test_builds_category_indexes_and_root_links_to_chunks(self) -> None:
        documents = [
            self.make_document("stock/stock", "Stock", 11),
            self.make_document("fund/fund_private", "Private Fund", 1),
            self.make_document("fund/fund_public", "Public Fund", 1),
        ]

        files, rendered = crawl.build_output_files(
            documents,
            sections_per_file=10,
            source_index_url="https://example.test/index.rst.txt",
        )

        self.assertIn("stock/stock-001.md", files)
        self.assertIn("stock/stock-002.md", files)
        self.assertIn("fund/fund_private-001.md", files)
        self.assertIn("fund/fund_public-001.md", files)
        self.assertIn("fund/index.md", files)
        self.assertIn("(stock/stock-001.md)", files["index.md"])
        self.assertIn("(fund/fund_private-001.md)", files["index.md"])
        self.assertIn("    - Section 1", files["index.md"])
        self.assertIn("    - Section 10", files["index.md"])
        self.assertIn("  - Section 1", files["stock/index.md"])
        self.assertIn("  - Section 10", files["stock/index.md"])
        self.assertEqual(3, len(rendered))

    def test_manifest_removes_only_stale_generated_files(self) -> None:
        document = self.make_document("stock/stock", "Stock", 1)
        files, rendered = crawl.build_output_files(
            [document],
            sections_per_file=10,
            source_index_url="https://example.test/index.rst.txt",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            manual = output / "manual.md"
            stale = output / "old" / "stale.md"
            manual.write_text("keep", encoding="utf-8")
            stale.parent.mkdir()
            stale.write_text("remove", encoding="utf-8")
            (output / crawl.MANIFEST_FILENAME).write_text(
                json.dumps({"files": ["old/stale.md"]}), encoding="utf-8"
            )

            crawl.write_generated_files(
                output,
                files,
                rendered,
                source_index_url="https://example.test/index.rst.txt",
                sections_per_file=10,
            )

            self.assertTrue(manual.is_file())
            self.assertFalse(stale.exists())
            self.assertTrue((output / "index.md").is_file())


if __name__ == "__main__":
    unittest.main()
