"""Eastmoney research-report download tasks.

Downloads research-report PDFs from Eastmoney's rolling two-year report tables,
sinks PDFs to MinIO, and records a download-state row to phoenixA
(table ods.research_report_download_record). Crawl state (pending / downloaded
/ no_pdf / detail_error / pdf_error per resource_id) lives in phoenixA — there
is no local sqlite. Each run processes a bounded batch (`download_limit`) and
is resumable: pending/error reports are retried on the next run.

This task is a DOWNLOAD TASK ONLY — it tracks what's downloaded and where the
PDF was stored. It does NOT model research-report business content.

The core crawl logic (page walk, detail/PDF fetch, pacing, block detection,
PDF validation) is adapted from
`app/tools/py/crawler/eastmoney/report/stock/main.py`.

Flow per run:
  1. Resolve one list cursor per report type = MAX(publish_date) for that type
     (any status) from phoenixA, or a configured baseline on first run.
  2. LIST phase: walk eastmoney list pages oldest-first (pages backward, rows
     backward) over [cursor, today], up to `list_page_limit` pages. For each
     report, resolve stock_code → subject_id (security_id for stock) via the
     phoenixA registry. ALL reports are upserted — including those whose stock
     is NOT yet in the registry (subject_id=NULL, subject_source_code=stock_code).
     Reports are never skipped for being unregistered: the list cursor must
     advance past every listed report or unregistered ones would be permanently
     missed once their stock later enters the registry. (Rows with an EMPTY
     subject_source_code — malformed, no stockCode — ARE skipped: they can't be
     pathed and would violate the non-empty CHECK.) subject_id is NOT
     auto-back-filled: the list cursor is MAX(publish_date), so older unresolved
     records are not re-scanned; back-filling subject_id from subject_source_code
     needs a separate reconcile/backfill job.
  3. PROCESS phase: if MinIO is the noop mock (not configured), SKIP the whole
     phase (do NOT hit eastmoney detail/PDF — it would waste anti-bot-limited
     requests and leave rows pending). Otherwise query phoenixA for up to
     `download_limit` pending/error records (oldest first, across all dates),
     and for each: fetch detail page → extract pdf_url → download PDF
     (curl_cffi Chrome TLS impersonation) → put to MinIO (path uses
     subject_source_code) → update the phoenixA row to status='downloaded'.

Object key conventions:
  - stock / new_stock (both filed under the stock folder by symbol):
      "{stock_prefix}/{subject_source_code}/{publish_date}_{title}.pdf"
  - industry (by source + industry classification - eastmoney now, others later):
      "{industry_prefix}/{source}/{industry_name}/{publish_date}_{title}.pdf"
  - macro / strategy / morning_report (subjectless, one folder per day):
      "{type_folder}/{publish_date}/{title}_{org_name}.pdf"
"""
import html
import json
import random
import re
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import requests

from artemis import consts
from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.engines.task_engine.worker_unit import WorkerUnit


# ─────────────────────────────────────────────────────────────────────────────
# Eastmoney API constants (mirrors the original crawler)
# ─────────────────────────────────────────────────────────────────────────────

LIST_API_URL = "https://reportapi.eastmoney.com/report/list2"
REPORT_API_BASE = "https://reportapi.eastmoney.com"
LIST_REFERER = "https://data.eastmoney.com/report/stock.jshtml"
DETAIL_URL_TEMPLATE = "https://data.eastmoney.com/report/info/{info_code}.html"
PDF_URL_RE = re.compile(
    r"https?://pdf\.dfcfw\.com/pdf/[^\"'<>\s]+?\.pdf(?:\?[^\"'<>\s]+)?",
    re.IGNORECASE,
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/149.0.0.0 Safari/537.36"
)

# Eastmoney ratingChange code -> human label (mirrors the original crawler).
RATING_CHANGE_NAMES = {
    1: "调高",
    2: "首次",
    3: "维持",
    4: "调低",
}

# Conservative pacing (mandated by eastmoney anti-bot). All overridable via
# task.yaml variant config.
DEFAULT_PAGE_SIZE = 50
DEFAULT_LIST_PAGE_SLEEP = (3.0, 6.0)
DEFAULT_DETAIL_PAGE_SLEEP = (7.0, 15.0)
DEFAULT_PDF_DOWNLOAD_SLEEP = (9.0, 18.0)
DEFAULT_RETRY_SLEEP = (45.0, 120.0)
REQUEST_TIMEOUT_SECONDS = (10, 60)
MAX_REQUEST_RETRIES = 3

REPORT_TYPE_CONFIGS: Dict[str, Dict[str, Any]] = {
    "stock": {
        "referer": LIST_REFERER,
        "endpoint": "/report/list2",
        "q_type": 0,
        "subject_field": "stockCode",
        "detail_kind": "info",
    },
    "industry": {
        "referer": "https://data.eastmoney.com/report/industry.jshtml",
        "endpoint": "/report/list",
        "q_type": 1,
        "subject_field": "industryCode",
        "detail_kind": "info",
    },
    "macro": {
        "referer": "https://data.eastmoney.com/report/macresearch.jshtml",
        "endpoint": "/report/jg",
        "q_type": 3,
        "subject_field": "",
        "detail_kind": "encoded",
        "detail_path": "zw_macresearch.jshtml",
    },
    "new_stock": {
        "referer": "https://data.eastmoney.com/report/newstock.jshtml",
        "endpoint": "/report/newStockList",
        "q_type": 4,
        "subject_field": "stockCode",
        "detail_kind": "info",
    },
    "strategy": {
        "referer": "https://data.eastmoney.com/report/strategyreport.jshtml",
        "endpoint": "/report/jg",
        "q_type": 2,
        "subject_field": "",
        "detail_kind": "encoded",
        "detail_path": "zw_strategy.jshtml",
    },
    # Eastmoney calls this feed 券商晨报 (broker morning report) and serves it
    # from brokerreport.jshtml; we store it as `morning_report` (MinIO folder
    # + report_type) since "broker_report" is a misnomer for a morning digest.
    "morning_report": {
        "referer": "https://data.eastmoney.com/report/brokerreport.jshtml",
        "endpoint": "/report/jg",
        "q_type": 4,
        "subject_field": "",
        "detail_kind": "encoded",
        "detail_path": "zw_brokerreport.jshtml",
    },
}

REPORT_FOLDERS = {
    "macro": "macro",
    "strategy": "strategy",
    "morning_report": "morning_report",
}
SUBJECT_REQUIRED_REPORT_TYPES = {"stock", "industry", "new_stock"}
SECURITY_REPORT_TYPES = {"stock", "new_stock"}

# Per-run bounds.
DEFAULT_DOWNLOAD_LIMIT = 20        # max reports to fully process (detail+pdf) per run
DEFAULT_LIST_PAGE_LIMIT = 10       # max list pages to walk per run (bounds first-run backfill)
DEFAULT_BASELINE_DATE = "2024-07-01"  # eastmoney rolling ~2y window; first-run list start


class CrawlStopped(RuntimeError):
    """Raised when eastmoney appears to block/captcha us; the run should stop."""


class ReportGone(RuntimeError):
    """Raised when a report's page is permanently gone (HTTP 404) - the report
    has been delisted from Eastmoney's rolling ~2-year list window. This is NOT
    transient: retrying wastes ~2-3 min/record (3x 45-120s backoff) on records
    that will never come back, clogging the pending queue every run and blowing
    the cronjob callback deadline (task 21 strategy / morning_report timeouts).
    The record is marked terminal (no_pdf) so QueryPending stops re-queuing it."""


class StockZhAEastmoneyReport(WorkerUnit):
    """Download Eastmoney stock research-report PDFs → MinIO + phoenixA state.

    Configurable via task.yaml variant + incoming params:
      - start_date: YYYY-MM-DD  — override the list cursor (else MAX publish_date)
      - end_date:   YYYY-MM-DD  — default today
      - earliest_date: YYYY-MM-DD — baseline when phoenixA has no rows yet
      - download_limit: int     — max reports to process per run
      - list_page_limit: int    — max list pages to walk per run
      - page_size: int          — eastmoney page size (keep 50)
      - sleep ranges: list_page_sleep, detail_page_sleep, pdf_download_sleep, retry_sleep
    """

    REPORT_TYPES = ("stock",)

    # ── lifecycle hooks ──────────────────────────────────────────────────────

    def parameter_check(self, ctx: TaskContext):
        params = ctx.incoming_params
        for key in ("start_date", "end_date", "earliest_date"):
            val = params.get(key)
            if val:
                try:
                    datetime.strptime(str(val), "%Y-%m-%d")
                except ValueError:
                    ctx.fail(f"invalid {key}={val}, expected YYYY-MM-DD", phase="parameter_check")
                    return

    def load_dynamic_parameters(self, ctx: TaskContext) -> Dict[str, Any]:
        """Resolve the list date range and write it back into ctx.params.

        NOTE: BaseTaskUnit._pre_run() calls this but DISCARDS the return value,
        so we must write results into ctx.params directly (mirrors
        StockZhAHistParent.load_dynamic_parameters).
        """
        source = consts.DataSource.DS_EASTMONEY.value
        phoenix_client = ctx.dept_http.get(DeptServices.PHOENIXA)

        explicit_start = ctx.params.get("start_date")
        list_begin_by_type: Dict[str, str] = {}
        for report_type in self.REPORT_TYPES:
            list_begin = str(explicit_start) if explicit_start else ""
            if not list_begin and phoenix_client is not None:
                try:
                    list_begin = phoenix_client.get_research_report_max_publish_date(
                        source=source,
                        report_type=report_type,
                    )
                except Exception as e:
                    ctx.logger.warning({
                        "event": "max_publish_date_query_failed",
                        "report_type": report_type,
                        "error": str(e),
                        "run_id": ctx.run_id,
                    })
            if not list_begin:
                list_begin = str(ctx.params.get("earliest_date") or DEFAULT_BASELINE_DATE)
            list_begin_by_type[report_type] = list_begin

        end_date = ctx.params.get("end_date") or date.today().isoformat()

        ctx.params["source"] = source
        ctx.params["list_begin_by_type"] = list_begin_by_type
        if len(self.REPORT_TYPES) == 1:
            ctx.params["list_begin"] = list_begin_by_type[self.REPORT_TYPES[0]]
        ctx.params["end_date"] = str(end_date)
        ctx.logger.info({
            "event": "eastmoney_report_resolved_range",
            "list_begin_by_type": list_begin_by_type,
            "end_date": end_date,
            "run_id": ctx.run_id,
        })
        return {}

    def before_execute(self, ctx: TaskContext) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        })
        # subject_source_code (raw stock code) → subject_id (security_id for
        # stock). None if the stock is not in the registry. Cached across the run.
        self._security_id_cache: Dict[str, Optional[int]] = {}

    # ── main execute ─────────────────────────────────────────────────────────

    def execute(self, ctx: TaskContext):
        params = ctx.params
        source = params["source"]
        list_begin_by_type = params.get("list_begin_by_type") or {
            self.REPORT_TYPES[0]: params["list_begin"],
        }
        end_date = params["end_date"]
        download_limit = int(params.get("download_limit", DEFAULT_DOWNLOAD_LIMIT))
        list_page_limit = int(params.get("list_page_limit", DEFAULT_LIST_PAGE_LIMIT))
        page_size = int(params.get("page_size", DEFAULT_PAGE_SIZE))

        phoenix_client = ctx.dept_http[DeptServices.PHOENIXA]
        minio_client = ctx.dept_http[DeptServices.MINIO]

        # ── LIST phase: walk pages oldest-first, upsert metadata ──
        listed = 0
        try:
            for report_type in self.REPORT_TYPES:
                listed += self._list_and_upsert(
                    ctx, phoenix_client, source, report_type,
                    str(list_begin_by_type[report_type]), end_date,
                    page_size, list_page_limit,
                )
        except CrawlStopped as e:
            ctx.fail(f"eastmoney block during list: {e}", phase="execute")
            return {"listed": listed, "processed": 0, "pending_count": 0}
        except ReportGone as e:
            # A 404 on the list endpoint itself means the URL moved (code/config
            # bug) - fail loudly so it is noticed, rather than crashing the run.
            ctx.fail(f"eastmoney list endpoint gone (404): {e}", phase="execute")
            return {"listed": listed, "processed": 0, "pending_count": 0}

        # ── PROCESS phase ──
        # If MinIO is the noop mock (no real endpoint configured), SKIP the
        # whole phase. Otherwise we would burn eastmoney detail/PDF requests
        # (anti-bot-limited) on every cron tick and leave every row pending.
        # When real MinIO is configured, PROCESS runs normally.
        if minio_client.is_noop():
            ctx.logger.warning({
                "event": "eastmoney_report_minio_noop_skip_process",
                "run_id": ctx.run_id,
                "reason": "minio not configured; skipping PROCESS (no eastmoney detail/PDF requests)",
            })
            ctx.stats["listed"] = listed
            ctx.stats["processed"] = 0
            ctx.stats["pending_count"] = 0
            ctx.stats["skipped_no_storage"] = True
            return {"listed": listed, "processed": 0, "pending_count": 0, "skipped_no_storage": True}

        pending: List[Dict[str, Any]] = []
        for report_type in self.REPORT_TYPES:
            pending.extend(phoenix_client.query_research_report_pending(
                source=source,
                report_type=report_type,
                start_date="",
                end_date="",
                limit=download_limit,
            ))
        pending.sort(key=lambda row: (
            str(row.get("publish_date") or ""),
            int(row.get("id") or 0),
            str(row.get("report_type") or ""),
        ))
        pending = pending[:download_limit]
        total = len(pending)
        ctx.logger.info({"event": "eastmoney_report_process_start", "pending": total, "run_id": ctx.run_id})
        self._report_progress(ctx, 0, total, "start processing")

        processed = 0
        for report in pending:
            try:
                self._process_one(ctx, phoenix_client, minio_client, source, report)
                processed += 1
            except CrawlStopped as e:
                ctx.fail(f"eastmoney block during process: {e}", phase="execute")
                break
            except ReportGone as e:
                # Detail page 404 -> report delisted from Eastmoney's rolling
                # window. Mark terminal (no_pdf) so QueryPending stops re-queuing
                # it every run; retrying would just burn the callback deadline on
                # gone reports. (Self-healing: existing pdf_error rows that 404
                # are converted to no_pdf on the next run after this ships.)
                resource_id = report.get("resource_id", "?")
                ctx.logger.info({
                    "event": "eastmoney_report_delisted",
                    "resource_id": resource_id, "error": str(e), "run_id": ctx.run_id,
                })
                try:
                    phoenix_client.update_research_report_status(
                        source=source, resource_id=resource_id, status="no_pdf",
                        last_error=str(e)[:2000], run_id=ctx.run_id,
                    )
                except Exception:
                    pass
            except Exception as e:
                resource_id = report.get("resource_id", "?")
                ctx.logger.warning({
                    "event": "eastmoney_report_process_failed",
                    "resource_id": resource_id, "error": str(e), "run_id": ctx.run_id,
                })
                # mark pdf_error so it is retried next run (unless already marked inside)
                try:
                    phoenix_client.update_research_report_status(
                        source=source, resource_id=resource_id, status="pdf_error",
                        last_error=str(e)[:2000], run_id=ctx.run_id,
                    )
                except Exception:
                    pass
            self._report_progress(ctx, processed, total, f"processed {processed}/{total}")

        ctx.stats["listed"] = listed
        ctx.stats["processed"] = processed
        ctx.stats["pending_count"] = total
        ctx.logger.info({
            "event": "eastmoney_report_done",
            "listed": listed, "processed": processed, "pending": total, "run_id": ctx.run_id,
        })
        return {"listed": listed, "processed": processed, "pending_count": total}

    # ── LIST phase ────────────────────────────────────────────────────────────

    def _list_and_upsert(
        self, ctx: TaskContext, phoenix_client, source: str,
        report_type: str,
        list_begin: str, end_date: str, page_size: int, list_page_limit: int,
    ) -> int:
        listed = 0
        first_page = self._fetch_list_page(
            ctx, list_begin, end_date, page_size, page_no=1,
            report_type=report_type,
        )
        total_pages = int(first_page.get("TotalPage") or 0)
        if total_pages <= 0:
            ctx.logger.info({
                "event": "eastmoney_report_list_empty",
                "report_type": report_type,
                "run_id": ctx.run_id,
            })
            return 0

        pages_to_walk = min(total_pages, list_page_limit)
        ctx.logger.info({
            "event": "eastmoney_report_list_start",
            "report_type": report_type,
            "total_pages": total_pages, "pages_to_walk": pages_to_walk, "run_id": ctx.run_id,
        })

        # Walk pages newest-first->oldest (total_pages -> down) so the overall
        # order is oldest -> newest. Cap at pages_to_walk (the oldest N pages of
        # the [list_begin, end_date] range). first_page (page 1, newest) is only
        # reused when the walk actually reaches page 1; otherwise its data is
        # discarded (it was fetched solely to read TotalPage) so the list cursor
        # (MAX publish_date) reflects the oldest-first walk progress, not the
        # newest page.
        for offset in range(pages_to_walk):
            page_no = total_pages - offset
            if page_no < 1:
                break
            if page_no == 1:
                payload = first_page
            else:
                self._sleep(ctx, self._param_sleep(ctx, "list_page_sleep", DEFAULT_LIST_PAGE_SLEEP),
                            f"before list page {page_no}")
                payload = self._fetch_list_page(
                    ctx, list_begin, end_date, page_size, page_no=page_no,
                    report_type=report_type,
                )

            rows = list(payload.get("data") or [])
            if not rows:
                continue

            # currentYear labels the predictThisYear/predictNextYear fields in
            # the extra JSON; capture it per page so the year labels stay right
            # even across a year boundary mid-walk.
            current_year = to_int_or_none(payload.get("currentYear"))

            if report_type in SECURITY_REPORT_TYPES:
                stock_codes = [str(r.get("stockCode") or "").strip() for r in rows]
                self._resolve_security_ids(ctx, phoenix_client, stock_codes)

            reports: List[Dict[str, Any]] = []
            unresolved = 0
            skipped_empty_subject = 0
            for raw in rows:
                try:
                    rep = normalize_report(
                        raw,
                        self._security_id_cache,
                        current_year,
                        report_type=report_type,
                    )
                except Exception as e:
                    ctx.logger.warning({"event": "normalize_report_failed", "error": str(e), "run_id": ctx.run_id})
                    continue
                # subject_source_code is CHECK-constrained non-empty for
                # stock/industry. A stock report with no stockCode is malformed
                # (can't be pathed/stored) — skip it. (Unregistered-but-valid
                # reports — subject_id NULL, subject_source_code present — are
                # NOT skipped; see docstring.)
                if report_type in SUBJECT_REQUIRED_REPORT_TYPES and not rep["subject_source_code"]:
                    skipped_empty_subject += 1
                    continue
                if report_type in SECURITY_REPORT_TYPES and rep["subject_id"] is None:
                    unresolved += 1
                reports.append(rep)

            if skipped_empty_subject:
                ctx.logger.warning({
                    "event": "eastmoney_report_skipped_empty_subject",
                    "report_type": report_type,
                    "page_no": page_no, "count": skipped_empty_subject, "run_id": ctx.run_id,
                })
            if unresolved:
                ctx.logger.info({
                    "event": "eastmoney_report_unresolved_subject",
                    "report_type": report_type,
                    "page_no": page_no, "count": unresolved, "run_id": ctx.run_id,
                })

            if reports:
                ok = phoenix_client.upsert_research_report(reports, source=source, run_id=ctx.run_id)
                if ok is False:
                    ctx.fail(f"failed to upsert {len(reports)} reports to phoenixA", phase="execute")
                    break
                listed += len(reports)

            ctx.logger.info({
                "event": "eastmoney_report_list_page_done",
                "report_type": report_type,
                "page_no": page_no, "rows": len(rows), "upserted": len(reports),
                "unresolved": unresolved, "run_id": ctx.run_id,
            })

        return listed

    def _fetch_list_page(
        self,
        ctx: TaskContext,
        begin: str,
        end: str,
        page_size: int,
        page_no: int,
        report_type: str = "stock",
    ) -> Dict[str, Any]:
        if report_type != "stock":
            config = REPORT_TYPE_CONFIGS[report_type]
            params: Dict[str, Any] = {
                "pageSize": page_size,
                "beginTime": begin,
                "endTime": end,
                "pageNo": page_no,
                "fields": "",
                "qType": config["q_type"],
            }
            if report_type == "industry":
                params.update({
                    "industryCode": "*",
                    "industry": "*",
                    "rating": "*",
                    "ratingChange": "*",
                })
            response = self._request(
                ctx,
                "GET",
                f"{REPORT_API_BASE}{config['endpoint']}",
                headers={
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Referer": config["referer"],
                },
                params=params,
            )
            payload = response.json()
            if "data" not in payload:
                raise RuntimeError(
                    f"unexpected {report_type} list response keys: {sorted(payload.keys())}"
                )
            return payload

        body: Dict[str, Any] = {
            "beginTime": begin,
            "endTime": end,
            "industryCode": "*",
            "ratingChange": None,
            "rating": None,
            "orgCode": None,
            "code": "*",
            "rcode": "",
            "pageSize": page_size,
            "p": page_no,
            "pageNo": page_no,
            "pageNum": page_no,
            "pageNumber": page_no,
        }
        response = self._request(ctx, "POST", LIST_API_URL, headers={
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/json",
            "Origin": "https://data.eastmoney.com",
            "Referer": LIST_REFERER,
        }, json=body)
        payload = response.json()
        if "data" not in payload:
            raise RuntimeError(f"unexpected list response keys: {sorted(payload.keys())}")
        return payload

    # ── PROCESS phase ─────────────────────────────────────────────────────────

    def _process_one(self, ctx: TaskContext, phoenix_client, minio_client, source: str, report: Dict[str, Any]):
        resource_id = str(report.get("resource_id") or "")
        if not resource_id:
            raise RuntimeError("pending report missing resource_id")

        detail_url = str(report.get("detail_url") or "")
        if not detail_url:
            phoenix_client.update_research_report_status(
                source=source, resource_id=resource_id, status="detail_error",
                last_error="missing detail_url", run_id=ctx.run_id,
            )
            return

        self._sleep(ctx, self._param_sleep(ctx, "detail_page_sleep", DEFAULT_DETAIL_PAGE_SLEEP),
                     f"before detail page {resource_id}")
        report_type = str(report.get("report_type") or "stock")
        referer = str(REPORT_TYPE_CONFIGS.get(report_type, {}).get("referer") or LIST_REFERER)
        detail_html = self._fetch_detail_html(ctx, detail_url, referer)
        pdf_url = extract_pdf_url(detail_html)
        if not pdf_url:
            phoenix_client.update_research_report_status(
                source=source, resource_id=resource_id, status="no_pdf", run_id=ctx.run_id,
            )
            ctx.logger.info({"event": "eastmoney_report_no_pdf", "resource_id": resource_id, "run_id": ctx.run_id})
            return

        self._sleep(ctx, self._param_sleep(ctx, "pdf_download_sleep", DEFAULT_PDF_DOWNLOAD_SLEEP),
                     f"before pdf download {resource_id}")
        pdf_bytes = self._download_pdf(ctx, pdf_url, detail_url)

        # Subject-bearing feeds use their raw source code as a subfolder;
        # subjectless feeds use resource_id in the filename.
        subject = str(report.get("subject_source_code") or "")
        object_key = build_object_key(report, minio_client, subject, source=source)
        minio_client.put_pdf(object_key, pdf_bytes)

        phoenix_client.update_research_report_status(
            source=source, resource_id=resource_id, status="downloaded",
            pdf_object_key=object_key, pdf_url=pdf_url, run_id=ctx.run_id,
        )
        ctx.logger.info({"event": "eastmoney_report_downloaded", "resource_id": resource_id,
                         "object_key": object_key, "size": len(pdf_bytes), "run_id": ctx.run_id})

    def _fetch_detail_html(
        self,
        ctx: TaskContext,
        detail_url: str,
        referer: str = LIST_REFERER,
    ) -> str:
        response = self._request(ctx, "GET", detail_url, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": referer,
        })
        response.encoding = response.apparent_encoding or "utf-8"
        text = response.text
        if looks_like_block_page(text):
            raise CrawlStopped("detail page looked like a block or captcha page")
        return text

    def _download_pdf(
        self,
        ctx: TaskContext,
        pdf_url: str,
        referer: str = LIST_REFERER,
    ) -> bytes:
        # curl-cffi with Chrome TLS fingerprint impersonation to bypass anti-bot.
        # Imported lazily so the module loads even when curl_cffi isn't installed
        # (tests monkeypatch this method and don't need the real client).
        from curl_cffi import requests as curl_requests

        session = curl_requests.Session(impersonate="chrome")
        try:
            response = session.get(
                pdf_url,
                headers={"Accept": "application/pdf,*/*;q=0.8", "Referer": referer},
                timeout=REQUEST_TIMEOUT_SECONDS,
                stream=False,
            )
            content_type = response.headers.get("Content-Type", "")
            data = response.content
        finally:
            session.close()

        if not is_valid_pdf_bytes(data):
            if "text/html" in content_type.lower():
                raise CrawlStopped(f"pdf request returned html: {pdf_url}")
            raise RuntimeError(f"downloaded file is not a valid pdf: {pdf_url}")
        return data

    # ── HTTP with retry + block detection ─────────────────────────────────────

    def _request(self, ctx: TaskContext, method: str, url: str, **kwargs) -> requests.Response:
        last_exc: Optional[BaseException] = None
        for attempt in range(1, MAX_REQUEST_RETRIES + 1):
            try:
                response = self._session.request(method, url, timeout=REQUEST_TIMEOUT_SECONDS, **kwargs)
                if response.status_code in {403, 429, 503}:
                    raise CrawlStopped(f"blocked or rate limited: HTTP {response.status_code}")
                if response.status_code == 404:
                    # Page is gone (report delisted from Eastmoney's rolling
                    # window). Not transient - do NOT retry/backoff. The caller
                    # (PROCESS loop) catches ReportGone and marks the record
                    # terminal (no_pdf) so it stops clogging the pending queue.
                    raise ReportGone(
                        f"HTTP 404 Not Found (report delisted): {method} {url}")
                if 500 <= response.status_code < 600:
                    raise RuntimeError(f"server error HTTP {response.status_code}")
                response.raise_for_status()
                return response
            except (CrawlStopped, ReportGone):
                raise
            except Exception as exc:
                last_exc = exc
                if attempt >= MAX_REQUEST_RETRIES:
                    break
                ctx.logger.warning({"event": "eastmoney_report_request_retry",
                                    "attempt": attempt, "max": MAX_REQUEST_RETRIES,
                                    "method": method, "url": url, "error": str(exc), "run_id": ctx.run_id})
                self._sleep(ctx, self._param_sleep(ctx, "retry_sleep", DEFAULT_RETRY_SLEEP), "request retry")
        raise RuntimeError(f"request failed after retries: {method} {url}: {last_exc}")

    # ── identity resolution ───────────────────────────────────────────────────

    def _resolve_security_ids(self, ctx: TaskContext, phoenix_client, stock_codes: List[str]):
        """Resolve subject_source_code (raw stock code) → subject_id (security_id
        for stock), batched and cached. Unresolvable codes map to None."""
        uncached = [c for c in dict.fromkeys(stock_codes) if c and c not in self._security_id_cache]
        if not uncached:
            return
        try:
            securities = phoenix_client.get_securities(
                asset_type="stock", market="zh_a", symbols=uncached,
            )
        except Exception as e:
            ctx.logger.warning({"event": "resolve_security_ids_failed", "error": str(e), "run_id": ctx.run_id})
            securities = {}
        symbol_to_sid: Dict[str, int] = {}
        for sid, info in securities.items():
            sym = (info.get("symbol") or "").strip()
            if sym and sym not in symbol_to_sid:
                symbol_to_sid[sym] = int(sid)
        for code in uncached:
            self._security_id_cache[code] = symbol_to_sid.get(code)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _param_sleep(self, ctx: TaskContext, key: str, default: Tuple[float, float]) -> Tuple[float, float]:
        val = ctx.params.get(key)
        if isinstance(val, (list, tuple)) and len(val) == 2:
            try:
                return (float(val[0]), float(val[1]))
            except (TypeError, ValueError):
                pass
        return default

    def _sleep(self, ctx: TaskContext, seconds_range: Tuple[float, float], reason: str):
        secs = random.uniform(*seconds_range)
        ctx.logger.debug({"event": "eastmoney_report_sleep", "seconds": round(secs, 1), "reason": reason, "run_id": ctx.run_id})
        time.sleep(secs)

    def _report_progress(self, ctx: TaskContext, current: int, total: int, message: str):
        if total <= 0:
            return
        cronjob_cli = ctx.dept_http.get(DeptServices.CRONJOB)
        if cronjob_cli is None or not hasattr(cronjob_cli, "progress"):
            return
        try:
            cronjob_cli.progress(ctx, current=current, total=total, message=message)
        except Exception as e:
            ctx.logger.debug({"event": "progress_report_failed", "error": str(e), "run_id": ctx.run_id})


class EastmoneyResearchReport(StockZhAEastmoneyReport):
    """Download ONE Eastmoney research-report feed per run.

    The feed is selected by the `type` incoming param, which the task.yaml
    variants match on (stock / industry / macro / new_stock / strategy /
    morning_report). Each variant carries its own phoenixA cursor, pending
    queue, MinIO top-level folder, and pacing budget, so every feed can be
    scheduled and tuned independently - one bounded run per feed per tick.

    This is the ONLY eastmoney research-report task. The legacy
    `STOCK_ZH_A_EASTMONEY_REPORT` task code was removed - stock downloads now
    run through this class with `type=stock` (same code path, same MinIO
    layout). Having two task codes for the one shared download engine was the
    root cause of cronjobs being misrouted to the wrong endpoint.

    `morning_report` is Eastmoney's 券商晨报 feed (served from
    brokerreport.jshtml); only our internal report_type and MinIO folder are
    named `morning_report` - "broker_report" was a misnomer for a morning
    digest.
    """

    # Every feed this task can serve. The per-run type is pinned from
    # ctx.incoming_params['type'] in parameter_check (which runs before
    # merge_parameters, so it reads incoming_params, not ctx.params).
    SUPPORTED_REPORT_TYPES = (
        "stock",
        "industry",
        "macro",
        "new_stock",
        "strategy",
        "morning_report",
    )

    # Default empty so a misconfigured run (no/invalid `type`) is a safe no-op
    # rather than accidentally crawling every feed. parameter_check pins this
    # to a single-element tuple for the matched type.
    REPORT_TYPES = ()

    def parameter_check(self, ctx: TaskContext):
        super().parameter_check(ctx)
        if ctx.has_failed():
            return
        report_type = str(ctx.incoming_params.get("type") or "").strip()
        if report_type not in self.SUPPORTED_REPORT_TYPES:
            ctx.fail(
                f"invalid or missing type={report_type!r}, expected one of "
                f"{list(self.SUPPORTED_REPORT_TYPES)}",
                phase="parameter_check",
            )
            return
        self.REPORT_TYPES = (report_type,)


# ─────────────────────────────────────────────────────────────────────────────
# Pure helpers (adapted from the original crawler)
# ─────────────────────────────────────────────────────────────────────────────

def normalize_report(
    raw_report: Dict[str, Any],
    security_id_cache: Dict[str, Optional[int]],
    current_year: Optional[int] = None,
    report_type: str = "stock",
) -> Dict[str, Any]:
    """Normalize a raw eastmoney list row into a phoenixA download-record row.

    Returns DOWNLOAD-TASK metadata plus an `extra` JSONB object holding the
    report-content fields the user asked to preserve (rating, rating change,
    last-month report count, current/next-year EPS & PE predictions with
    explicit year labels, industry, researcher, stock name). phoenixA sets
    status/pdf_object_key/pdf_url/last_error. Research-report business content
    beyond `extra` is NOT curated as typed columns — this table is a download
    tracker; `extra` is a convenience capture at list time.
    `subject_id` is None when the stock is not yet in the registry; the report
    is still upserted (with subject_source_code set) so it is tracked and the
    list cursor advances past it. subject_id is NOT auto-back-filled (the list
    cursor won't re-scan older records); back-filling needs a separate job.
    """
    config = REPORT_TYPE_CONFIGS[report_type]
    if config["detail_kind"] == "info":
        resource_id = str(raw_report.get("infoCode") or "").strip()
        if not resource_id:
            raise ValueError(f"missing infoCode in {report_type} report: {raw_report}")
        detail_url = DETAIL_URL_TEMPLATE.format(info_code=resource_id)
    else:
        resource_id = str(raw_report.get("id") or "").strip()
        encode_url = str(raw_report.get("encodeUrl") or "").strip()
        if not resource_id or not encode_url:
            raise ValueError(f"missing id/encodeUrl in {report_type} report: {raw_report}")
        detail_url = (
            f"https://data.eastmoney.com/report/{config['detail_path']}"
            f"?encodeUrl={quote(encode_url, safe='')}"
        )

    subject_field = str(config.get("subject_field") or "")
    subject_source_code = (
        str(raw_report.get(subject_field) or "").strip()
        if subject_field else ""
    )
    subject_id = (
        security_id_cache.get(subject_source_code)
        if report_type in SECURITY_REPORT_TYPES else None
    )
    return {
        "resource_id": resource_id,
        "report_type": report_type,
        "subject_id": subject_id,
        "subject_source_code": subject_source_code,
        "publish_date": normalize_publish_date(str(raw_report.get("publishDate") or "")),
        "title": text_or_empty(raw_report.get("title")),
        "org_name": text_or_empty(raw_report.get("orgName")),
        "detail_url": detail_url,
        "extra": build_extra(raw_report, current_year),
    }


def build_extra(raw_report: Dict[str, Any], current_year: Optional[int]) -> Dict[str, Any]:
    """Build the `extra` JSONB object from an eastmoney list row.

    Captures: em_rating_name (东财评级), last_em_rating_name (上次评级),
    rating_change + rating_change_name (评级变动), report_count_1m (近一月个股研报数),
    predict_this_year / predict_next_year ({year, eps, pe} - 盈利预测),
    industry_code / industry_name (行业), researcher (研究员), stock_name (股票名称).
    `current_year` comes from the list payload's currentYear; when present it
    labels predict_this_year=current_year, predict_next_year=current_year+1 so
    the JSON is self-describing. Missing values degrade to "" / None, never
    absent keys, so downstream `extra->>'key'` queries are stable.
    """
    rating_change = to_int_or_none(raw_report.get("ratingChange"))
    this_year = current_year
    next_year = current_year + 1 if current_year is not None else None
    return {
        "em_rating_name": text_or_empty(raw_report.get("emRatingName")),
        "last_em_rating_name": text_or_empty(raw_report.get("lastEmRatingName")),
        "rating_change": rating_change,
        "rating_change_name": RATING_CHANGE_NAMES.get(rating_change, "") if rating_change is not None else "",
        "report_count_1m": to_int_or_none(raw_report.get("count")),
        "predict_this_year": {
            "year": this_year,
            "eps": text_or_empty(raw_report.get("predictThisYearEps")),
            "pe": text_or_empty(raw_report.get("predictThisYearPe")),
        },
        "predict_next_year": {
            "year": next_year,
            "eps": text_or_empty(raw_report.get("predictNextYearEps")),
            "pe": text_or_empty(raw_report.get("predictNextYearPe")),
        },
        "industry_code": text_or_empty(
            raw_report.get("indvInduCode") or raw_report.get("industryCode")
        ),
        "industry_name": text_or_empty(
            raw_report.get("indvInduName") or raw_report.get("industryName")
        ),
        "researcher": text_or_empty(raw_report.get("researcher")),
        "stock_name": text_or_empty(raw_report.get("stockName")),
    }


def to_int_or_none(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def extract_pdf_url(detail_html: str) -> str:
    unescaped = html.unescape(detail_html)
    matches = PDF_URL_RE.findall(unescaped)
    if not matches:
        return ""
    return matches[0].replace("&amp;", "&")


def build_object_key(report: Dict[str, Any], minio_client, subject: str = "", source: str = "") -> str:
    """Build the MinIO object key.

    Layout per feed:
      - stock / new_stock (both filed under the stock folder by symbol):
          "{stock_prefix}/{subject_source_code}/{publish_date}_{title}.pdf"
      - industry (separated by source + industry classification - eastmoney now,
        other classifications may come later):
          "{industry_prefix}/{source}/{industry}/{publish_date}_{title}.pdf"
        where {industry} is the human-readable industry name from extra, falling
        back to the raw industry code (subject_source_code).
      - macro / strategy / morning_report (subjectless, one folder per day):
          "{type_folder}/{publish_date}/{title}_{org_name}.pdf"
        A missing org degrades to {title}.pdf (no trailing underscore).
    """
    report_type = str(report.get("report_type") or "stock")
    publish_date = str(report.get("publish_date") or "unknown-date")
    title = safe_filename_part(str(report.get("title") or "untitled"), max_len=120)

    # stock and new_stock share the stock folder, filed under the raw symbol.
    if report_type in ("stock", "new_stock"):
        prefix = getattr(minio_client, "stock_prefix", "stock") or "stock"
        sym = safe_filename_part(subject or str(report.get("subject_source_code") or "unknown"))
        return f"{prefix}/{sym}/{publish_date}_{title}.pdf"

    # industry: by source + industry classification. The {source} segment keeps
    # different classification systems apart (eastmoney industry now; another
    # source's classification later lands under its own source folder).
    if report_type == "industry":
        prefix = getattr(minio_client, "industry_prefix", "industry") or "industry"
        src = safe_filename_part(source or "unknown-source", max_len=32)
        industry = safe_filename_part(
            _extra_industry_name(report) or str(report.get("subject_source_code") or "unknown-industry"),
            max_len=80,
        )
        return f"{prefix}/{src}/{industry}/{publish_date}_{title}.pdf"

    # macro / strategy / morning_report: subjectless, one folder per day.
    prefix = REPORT_FOLDERS.get(report_type, safe_filename_part(report_type))
    raw_org = str(report.get("org_name") or "").strip()
    if raw_org:
        org = safe_filename_part(raw_org, max_len=80)
        return f"{prefix}/{publish_date}/{title}_{org}.pdf"
    return f"{prefix}/{publish_date}/{title}.pdf"


def _extra_industry_name(report: Dict[str, Any]) -> str:
    """Extract industry_name from the report's extra JSONB.

    extra arrives from phoenixA's pending query as a dict (json.RawMessage
    marshals as a JSON object); defensively handle a JSON string or missing
    payload. Empty string when absent so the caller can fall back to the code.
    """
    extra = report.get("extra")
    if isinstance(extra, str):
        try:
            extra = json.loads(extra)
        except (ValueError, TypeError):
            return ""
    if isinstance(extra, dict):
        return str(extra.get("industry_name") or "").strip()
    return ""


def is_valid_pdf_bytes(data: bytes) -> bool:
    if not data or len(data) < 1024:
        return False
    return data[:5] == b"%PDF-"


def looks_like_block_page(text: str) -> bool:
    sample = text[:5000].lower()
    return any(needle in sample for needle in [
        "访问过于频繁", "安全验证", "人机验证", "请输入验证码", "系统检测到异常访问",
    ])


def normalize_publish_date(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    return value[:10]


def safe_filename_part(value: str, max_len: int = 80) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value.strip())
    value = re.sub(r"\s+", "_", value)
    value = value.strip("._ ")
    return (value or "unknown")[:max_len]


def text_or_empty(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
