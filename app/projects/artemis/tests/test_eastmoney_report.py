"""Minimal end-to-end test for the Eastmoney research-report download task.

Mocks PhoenixA + MinIO + the eastmoney HTTP layer, then asserts:
  1. load_dynamic_parameters writes the cursor back into ctx.params (the base
     class discards its return value).
  2. LIST upserts ALL reports — including unregistered subjects (subject_id
     NULL, subject_source_code set) — so the cursor advances past them (no
     permanent miss).
  3. When MinIO is the noop mock, PROCESS is skipped entirely (no eastmoney
     detail/PDF requests, no 'downloaded' status — no DB pollution).
  4. When MinIO is real, the row is marked 'downloaded' with object key
     stock/{subject_source_code}/{date}_{title}.pdf.
"""
from typing import cast

from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.core.clients.minio_client import NoopMinioClient
from artemis.engines.task_engine.download.zh.stock_zh_a_eastmoney_report import (
    StockZhAEastmoneyReport,
    build_object_key,
)


# ── fakes ────────────────────────────────────────────────────────────────────

class _FakeLogger:
    def _log(self, msg):
        pass

    info = warning = debug = error = _log


class _FakePhoenix:
    """Mock PhoenixAClient. get_securities returns symbol→sid so the task's
    subject_id cache populates during LIST."""

    def __init__(self, max_pub="", pending=None):
        self._max_pub = max_pub
        self._pending = pending or []
        self.upserted = []          # list of (reports, source)
        self.status_updates = []    # list of dict
        self.pending_called = False

    def get_research_report_max_publish_date(self, *, source="eastmoney"):
        return self._max_pub

    def get_securities(self, *, asset_type="stock", market="zh_a",
                       symbols=None, exchanges=None, status=None, limit=20000):
        # symbol "000001" → sid 1.
        out = {}
        for sym in (symbols or ["000001"]):
            out[1] = {"security_id": 1, "symbol": sym, "exchange": "SZ"}
        return out

    def upsert_research_report(self, reports, source, run_id=None):
        self.upserted.append((list(reports), source))
        return True

    def query_research_report_pending(self, *, source="eastmoney", start_date="", end_date="", limit=50):
        self.pending_called = True
        return list(self._pending)

    def update_research_report_status(self, *, source, resource_id, status,
                                      pdf_object_key="", pdf_url="", last_error="", run_id=None):
        self.status_updates.append({
            "source": source, "resource_id": resource_id, "status": status,
            "pdf_object_key": pdf_object_key, "pdf_url": pdf_url, "last_error": last_error,
        })
        return True


class _FakeMinioReal:
    """A MinIO client mock that claims to be real (is_noop=False)."""
    def __init__(self):
        self.puts = []
        self.stock_prefix = "stock"
        self.industry_prefix = "industry"

    def put_pdf(self, object_key, data, content_type="application/pdf"):
        self.puts.append(object_key)
        return object_key

    def is_noop(self):
        return False


class _FakeCronjob:
    def progress(self, ctx, current, total, message=None):
        pass


class _FakeCtx:
    def __init__(self, params, dept_http):
        self.params = params
        self.dept_http = dept_http
        self.logger = _FakeLogger()
        self.run_id = "test-run-eastmoney"
        self.stats = {}
        self.error = None
        self.failed_phase = None

    def fail(self, msg, phase=None):
        self.error = str(msg)
        self.failed_phase = phase


def _as_task_context(ctx: _FakeCtx) -> TaskContext:
    return cast(TaskContext, cast(object, ctx))


# ── canned eastmoney data ────────────────────────────────────────────────────

RAW_REPORT = {
    "infoCode": "AP202607070001",
    "stockCode": "000001",
    "stockName": "平安银行",
    "publishDate": "2026-07-07 00:00:00",
    "title": "平安银行2026年半年报点评",
    "orgName": "中信证券",
}

# A pending row as phoenixA returns it (subject_source_code always present).
PENDING_REPORT = {
    "resource_id": "AP202607070001",
    "report_type": "stock",
    "subject_id": 1,
    "subject_source_code": "000001",
    "publish_date": "2026-07-07",
    "title": "平安银行2026年半年报点评",
    "detail_url": "https://data.eastmoney.com/report/info/AP202607070001.html",
}

LIST_PAYLOAD = {"TotalPage": 1, "hits": 1, "currentYear": 2026, "data": [RAW_REPORT]}
DETAIL_HTML = '<html><a href="https://pdf.dfcfw.com/pdf/H3_AP202607070001_1.pdf">pdf</a></html>'
PDF_BYTES = b"%PDF-1.5" + b"0" * 2000  # > 1024 bytes, %PDF- magic


def _make_task_with_http_mocked():
    task = StockZhAEastmoneyReport()
    task._security_id_cache = {}
    task._session = None  # not used (HTTP methods are monkeypatched below)
    task._fetch_list_page = lambda ctx, begin, end, page_size, page_no: LIST_PAYLOAD
    task._fetch_detail_html = lambda ctx, url: DETAIL_HTML
    task._download_pdf = lambda ctx, url: PDF_BYTES
    task._sleep = lambda ctx, secs, reason: None  # no real sleeps in tests
    return task


def _base_params():
    return {
        "source": "eastmoney", "list_begin": "2026-06-15", "end_date": "2026-07-07",
        "download_limit": 5, "list_page_limit": 3, "page_size": 50,
    }


# ── tests ────────────────────────────────────────────────────────────────────

class TestLoadDynamicParametersWriteback:
    """P0 regression: the base class discards load_dynamic_parameters' return
    value, so the cursor MUST be written into ctx.params."""

    def test_cursor_written_back_from_max_publish_date(self):
        task = _make_task_with_http_mocked()
        phoenix = _FakePhoenix(max_pub="2026-06-15")
        ctx = _FakeCtx(
            params={"earliest_date": "2024-07-01"},
            dept_http={DeptServices.PHOENIXA: phoenix},
        )
        task.load_dynamic_parameters(_as_task_context(ctx))
        assert ctx.params["source"] == "eastmoney"
        assert ctx.params["list_begin"] == "2026-06-15"
        assert ctx.params["end_date"]  # today's date

    def test_falls_back_to_baseline_when_no_rows(self):
        task = _make_task_with_http_mocked()
        phoenix = _FakePhoenix(max_pub="")  # empty phoenixA
        ctx = _FakeCtx(
            params={"earliest_date": "2024-07-01"},
            dept_http={DeptServices.PHOENIXA: phoenix},
        )
        task.load_dynamic_parameters(_as_task_context(ctx))
        assert ctx.params["list_begin"] == "2024-07-01"


class TestListUpsertsAllSubjectsIncludingUnregistered:
    """P1 regression: unregistered subjects must NOT be skipped — otherwise the
    list cursor advances past them and they're permanently missed once their
    stock later enters the registry."""

    def test_unregistered_subject_upserted_with_null_subject_id(self, monkeypatch):
        task = _make_task_with_http_mocked()
        # Make get_securities return NOTHING → subject_id resolves to None.
        phoenix = _FakePhoenix(max_pub="2026-06-15")
        monkeypatch.setattr(phoenix, "get_securities", lambda **kw: {})
        ctx = _FakeCtx(
            params=_base_params(),
            dept_http={
                DeptServices.PHOENIXA: phoenix,
                DeptServices.MINIO: NoopMinioClient(logger=_FakeLogger()),  # PROCESS skipped
                DeptServices.CRONJOB: _FakeCronjob(),
            },
        )

        task.execute(_as_task_context(ctx))

        # The unregistered report WAS upserted (not skipped), with
        # subject_id=None and subject_source_code set.
        assert len(phoenix.upserted) == 1
        row = phoenix.upserted[0][0][0]
        assert row["resource_id"] == "AP202607070001"
        assert row["subject_id"] is None
        assert row["subject_source_code"] == "000001"


class TestExecuteNoopMinioSkipsProcess:
    """P2 regression: with NoopMinioClient, PROCESS is skipped entirely — no
    eastmoney detail/PDF requests, no 'downloaded' status (no DB pollution)."""

    def test_noop_minio_skips_process(self):
        task = _make_task_with_http_mocked()
        phoenix = _FakePhoenix(pending=[PENDING_REPORT])
        minio = NoopMinioClient(logger=_FakeLogger())
        ctx = _FakeCtx(
            params=_base_params(),
            dept_http={
                DeptServices.PHOENIXA: phoenix,
                DeptServices.MINIO: minio,
                DeptServices.CRONJOB: _FakeCronjob(),
            },
        )

        result = task.execute(_as_task_context(ctx))

        # LIST ran (metadata upserted).
        assert len(phoenix.upserted) == 1
        # PROCESS was skipped: pending never queried, no status updates at all.
        assert phoenix.pending_called is False
        assert phoenix.status_updates == []
        assert "downloaded" not in [u["status"] for u in phoenix.status_updates]
        assert result["skipped_no_storage"] is True


class TestExecuteRealMinioMarksDownloaded:
    """With a real MinIO, the row is marked 'downloaded' and the object key is
    stock/{subject_source_code}/{date}_{title}.pdf."""

    def test_real_minio_marks_downloaded(self):
        task = _make_task_with_http_mocked()
        phoenix = _FakePhoenix(pending=[PENDING_REPORT])
        minio = _FakeMinioReal()
        ctx = _FakeCtx(
            params=_base_params(),
            dept_http={
                DeptServices.PHOENIXA: phoenix,
                DeptServices.MINIO: minio,
                DeptServices.CRONJOB: _FakeCronjob(),
            },
        )

        task.execute(_as_task_context(ctx))

        assert phoenix.pending_called is True
        assert len(phoenix.status_updates) == 1
        upd = phoenix.status_updates[0]
        assert upd["status"] == "downloaded"
        assert upd["resource_id"] == "AP202607070001"
        # path uses subject_source_code (the raw symbol); no resource_id segment
        assert upd["pdf_object_key"] == "stock/000001/2026-07-07_平安银行2026年半年报点评.pdf"
        assert minio.puts == [upd["pdf_object_key"]]


class TestBuildObjectKey:
    def test_stock_uses_symbol_subject(self):
        report = {"report_type": "stock", "publish_date": "2026-07-07", "title": "某研报"}
        minio = _FakeMinioReal()
        assert build_object_key(report, minio, subject="000001") == "stock/000001/2026-07-07_某研报.pdf"

    def test_industry_uses_industry_prefix(self):
        report = {"report_type": "industry", "publish_date": "2026-07-07", "title": "某产业研报"}
        minio = _FakeMinioReal()
        assert build_object_key(report, minio, subject="801010") == "industry/801010/2026-07-07_某产业研报.pdf"
