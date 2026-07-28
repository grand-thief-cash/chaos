from io import BytesIO

import pikepdf

from atlas.core.clients import MinIOPDFReader
from atlas.knowledge_production.pdf_preprocessor import PikePDFUnlocker


def test_pikepdf_unlocker_removes_owner_restrictions_in_memory():
    source = BytesIO()
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page()
    pdf.save(
        source,
        encryption=pikepdf.Encryption(
            owner="owner-password",
            user="",
            allow=pikepdf.Permissions(extract=False, modify_other=False),
        ),
    )
    result = PikePDFUnlocker().unlock(source.getvalue())
    assert result.page_count == 1
    assert result.status == "UNLOCKED_IN_MEMORY"
    with pikepdf.Pdf.open(BytesIO(result.content)) as unlocked:
        assert not unlocked.is_encrypted


def test_minio_reader_resolves_configured_and_s3_keys_without_network():
    reader = object.__new__(MinIOPDFReader)
    reader.bucket = "research-report"
    assert reader._resolve("stock/a.pdf") == ("research-report", "stock/a.pdf")
    assert reader._resolve("s3://other/path/a.pdf") == ("other", "path/a.pdf")
