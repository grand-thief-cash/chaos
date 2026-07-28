from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import crawl


class MenuTests(unittest.TestCase):
    def test_parses_documents_in_order_and_skips_non_document_stats(self) -> None:
        payload = [
            {"menuTitle": "平台介绍", "markdownFileName": "home.md"},
            {"menuTitle": "--A股K线数据", "markdownFileName": "stockKData.md"},
            {"menuTitle": "访问统计", "markdownFileName": "default.md"},
            {"menuTitle": "重复项", "markdownFileName": "stockKData.md"},
        ]

        self.assertEqual(
            [
                crawl.MenuItem("平台介绍", "home.md"),
                crawl.MenuItem("A股K线数据", "stockKData.md"),
            ],
            crawl.parse_menu(payload),
        )

    def test_rejects_unsafe_filename(self) -> None:
        with self.assertRaises(ValueError):
            crawl.parse_menu(
                [{"menuTitle": "Bad", "markdownFileName": "../secret.md"}]
            )


class MarkdownTransformTests(unittest.TestCase):
    def test_demotes_headings_and_absolutizes_resources_outside_fences(self) -> None:
        source = """## Section

![Image](helpdocs/img/example.png)
[![Linked image](helpdocs/img/linked.png)](helpdocs/img/large.png)
[Download](/helpdocs/csv/example.csv)
<img src="helpdocs/img/html.png">
[Anchor](#local)
[External](https://example.com/x)

```markdown
## Do not demote
![Do not rewrite](relative.png)
```
"""

        transformed = crawl.transform_source_markdown(source)

        self.assertIn("#### Section", transformed)
        self.assertIn(
            "![Image](https://baostock.com/helpdocs/img/example.png)", transformed
        )
        self.assertIn(
            "[![Linked image](https://baostock.com/helpdocs/img/linked.png)]"
            "(https://baostock.com/helpdocs/img/large.png)",
            transformed,
        )
        self.assertIn(
            "[Download](https://baostock.com/helpdocs/csv/example.csv)", transformed
        )
        self.assertIn(
            '<img src="https://baostock.com/helpdocs/img/html.png">', transformed
        )
        self.assertIn("[Anchor](#local)", transformed)
        self.assertIn("[External](https://example.com/x)", transformed)
        self.assertIn("## Do not demote", transformed)
        self.assertIn("![Do not rewrite](relative.png)", transformed)


class RenderTests(unittest.TestCase):
    def make_documents(self, count: int) -> list[crawl.DownloadedDocument]:
        return [
            crawl.DownloadedDocument(
                crawl.MenuItem(f"文档 {number}", f"doc{number}.md"),
                f"## Section {number}\n\nBody {number}\n",
            )
            for number in range(1, count + 1)
        ]

    def test_builds_index_and_splits_every_ten_documents(self) -> None:
        files, chunks = crawl.build_output_files(self.make_documents(21), 10)

        self.assertEqual(3, len(chunks))
        self.assertEqual([10, 10, 1], [len(chunk.documents) for chunk in chunks])
        self.assertIn("index.md", files)
        self.assertIn("baostock-001.md", files)
        self.assertIn("baostock-003.md", files)
        self.assertIn(
            "[1. 文档 1](baostock-001.md#baostock-document-001)",
            files["index.md"],
        )
        self.assertIn(
            "[21. 文档 21](baostock-003.md#baostock-document-021)",
            files["index.md"],
        )
        self.assertIn('<a id="baostock-document-001"></a>', files["baostock-001.md"])
        self.assertIn("## 1. 文档 1", files["baostock-001.md"])
        self.assertIn("#### Section 1", files["baostock-001.md"])

    def test_atomic_write_replaces_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "baostock.md"
            target.write_text("old", encoding="utf-8")

            crawl.atomic_write_text(target, "new")

            self.assertEqual("new\n", target.read_text(encoding="utf-8"))

    def test_manifest_removes_stale_generated_file(self) -> None:
        documents = self.make_documents(2)
        files, chunks = crawl.build_output_files(documents, 10)

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            stale = output / "baostock-999.md"
            stale.write_text("stale", encoding="utf-8")
            (output / crawl.MANIFEST_FILENAME).write_text(
                json.dumps({"files": ["baostock-999.md"]}),
                encoding="utf-8",
            )

            crawl.write_generated_files(
                output,
                files,
                chunks,
                document_count=2,
            )

            self.assertFalse(stale.exists())
            self.assertTrue((output / "index.md").is_file())


if __name__ == "__main__":
    unittest.main()
