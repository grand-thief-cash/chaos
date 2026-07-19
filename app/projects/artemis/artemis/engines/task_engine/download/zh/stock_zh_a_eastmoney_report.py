"""Eastmoney stock research-report download task.

Downloads stock research-report PDFs from Eastmoney's rolling two-year report
table, sinks PDFs to MinIO, and records a download-state row to phoenixA
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
  1. Resolve the list cursor = MAX(publish_date) across all download records
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

Object key convention (subject_source_code is the raw symbol; no resource_id):
    "{stock_prefix}/{subject_source_code}/{publish_date}_{title}.pdf"
report_type=stock uses stock_prefix; industry (future) would use industry_prefix.
"""
import html
import random
import re
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

from artemis import consts
from artemis.consts import DeptServices
from artemis.core import TaskContext
from artemis.engines.task_engine.worker_unit import WorkerUnit


# ─────────────────────────────────────────────────────────────────────────────
# Eastmoney API constants (mirrors the original crawler)
# ─────────────────────────────────────────────────────────────────────────────

LIST_API_URL = "https://reportapi.eastmoney.com/report/list2"
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

# Conservative pacing (mandated by eastmoney anti-bot). All overridable via
# task.yaml variant config.
DEFAULT_PAGE_SIZE = 50
DEFAULT_LIST_PAGE_SLEEP = (3.0, 6.0)
DEFAULT_DETAIL_PAGE_SLEEP = (7.0, 15.0)
DEFAULT_PDF_DOWNLOAD_SLEEP = (9.0, 18.0)
DEFAULT_RETRY_SLEEP = (45.0, 120.0)
REQUEST_TIMEOUT_SECONDS = (10, 60)
MAX_REQUEST_RETRIES = 3

# Per-run bounds.
DEFAULT_DOWNLOAD_LIMIT = 20        # max reports to fully process (detail+pdf) per run
DEFAULT_LIST_PAGE_LIMIT = 10       # max list pages to walk per run (bounds first-run backfill)
DEFAULT_BASELINE_DATE = "2024-07-01"  # eastmoney rolling ~2y window; first-run list start


class CrawlStopped(RuntimeError):
    """Raised when eastmoney appears to block/captcha us; the run should stop."""


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
        if explicit_start:
            list_begin = str(explicit_start)
        else:
            list_begin = ""
            if phoenix_client is not None:
                try:
                    list_begin = phoenix_client.get_research_report_max_publish_date(source=source)
                except Exception as e:
                    ctx.logger.warning({"event": "max_publish_date_query_failed", "error": str(e), "run_id": ctx.run_id})
            if not list_begin:
                list_begin = ctx.params.get("earliest_date", DEFAULT_BASELINE_DATE)

        end_date = ctx.params.get("end_date") or date.today().isoformat()

        ctx.params["source"] = source
        ctx.params["list_begin"] = list_begin
        ctx.params["end_date"] = str(end_date)
        ctx.logger.info({
            "event": "eastmoney_report_resolved_range",
            "list_begin": list_begin,
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
        list_begin = params["list_begin"]
        end_date = params["end_date"]
        download_limit = int(params.get("download_limit", DEFAULT_DOWNLOAD_LIMIT))
        list_page_limit = int(params.get("list_page_limit", DEFAULT_LIST_PAGE_LIMIT))
        page_size = int(params.get("page_size", DEFAULT_PAGE_SIZE))

        phoenix_client = ctx.dept_http[DeptServices.PHOENIXA]
        minio_client = ctx.dept_http[DeptServices.MINIO]

        # ── LIST phase: walk pages oldest-first, upsert metadata ──
        listed = 0
        try:
            listed = self._list_and_upsert(
                ctx, phoenix_client, source, list_begin, end_date,
                page_size, list_page_limit,
            )
        except CrawlStopped as e:
            ctx.fail(f"eastmoney block during list: {e}", phase="execute")
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

        pending = phoenix_client.query_research_report_pending(
            source=source, start_date="", end_date="", limit=download_limit,
        )
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
        list_begin: str, end_date: str, page_size: int, list_page_limit: int,
    ) -> int:
        listed = 0
        first_page = self._fetch_list_page(ctx, list_begin, end_date, page_size, page_no=1)
        total_pages = int(first_page.get("TotalPage") or 0)
        if total_pages <= 0:
            ctx.logger.info({"event": "eastmoney_report_list_empty", "run_id": ctx.run_id})
            return 0

        pages_to_walk = min(total_pages, list_page_limit)
        ctx.logger.info({
            "event": "eastmoney_report_list_start",
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
                payload = self._fetch_list_page(ctx, list_begin, end_date, page_size, page_no=page_no)

            rows = list(payload.get("data") or [])
            if not rows:
                continue

            # Resolve subject_id for all stock_codes on this page (batched, cached).
            stock_codes = [str(r.get("stockCode") or "").strip() for r in rows]
            self._resolve_security_ids(ctx, phoenix_client, stock_codes)

            reports: List[Dict[str, Any]] = []
            unresolved = 0
            skipped_empty_subject = 0
            for raw in rows:
                try:
                    rep = normalize_report(raw, self._security_id_cache)
                except Exception as e:
                    ctx.logger.warning({"event": "normalize_report_failed", "error": str(e), "run_id": ctx.run_id})
                    continue
                # subject_source_code is CHECK-constrained non-empty for
                # stock/industry. A stock report with no stockCode is malformed
                # (can't be pathed/stored) — skip it. (Unregistered-but-valid
                # reports — subject_id NULL, subject_source_code present — are
                # NOT skipped; see docstring.)
                if not rep["subject_source_code"]:
                    skipped_empty_subject += 1
                    continue
                if rep["subject_id"] is None:
                    unresolved += 1
                reports.append(rep)

            if skipped_empty_subject:
                ctx.logger.warning({
                    "event": "eastmoney_report_skipped_empty_subject",
                    "page_no": page_no, "count": skipped_empty_subject, "run_id": ctx.run_id,
                })
            if unresolved:
                ctx.logger.info({
                    "event": "eastmoney_report_unresolved_subject",
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
                "page_no": page_no, "rows": len(rows), "upserted": len(reports),
                "unresolved": unresolved, "run_id": ctx.run_id,
            })

        return listed

    def _fetch_list_page(self, ctx: TaskContext, begin: str, end: str, page_size: int, page_no: int) -> Dict[str, Any]:
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
        detail_html = self._fetch_detail_html(ctx, detail_url)
        pdf_url = extract_pdf_url(detail_html)
        if not pdf_url:
            phoenix_client.update_research_report_status(
                source=source, resource_id=resource_id, status="no_pdf", run_id=ctx.run_id,
            )
            ctx.logger.info({"event": "eastmoney_report_no_pdf", "resource_id": resource_id, "run_id": ctx.run_id})
            return

        self._sleep(ctx, self._param_sleep(ctx, "pdf_download_sleep", DEFAULT_PDF_DOWNLOAD_SLEEP),
                     f"before pdf download {resource_id}")
        pdf_bytes = self._download_pdf(ctx, pdf_url)

        # Object path uses subject_source_code (the raw symbol) — always
        # present, even for stocks not yet in the registry (subject_id may be
        # NULL). No runtime symbol resolution needed.
        subject = str(report.get("subject_source_code") or "unknown")
        object_key = build_object_key(report, minio_client, subject)
        minio_client.put_pdf(object_key, pdf_bytes)

        phoenix_client.update_research_report_status(
            source=source, resource_id=resource_id, status="downloaded",
            pdf_object_key=object_key, pdf_url=pdf_url, run_id=ctx.run_id,
        )
        ctx.logger.info({"event": "eastmoney_report_downloaded", "resource_id": resource_id,
                         "object_key": object_key, "size": len(pdf_bytes), "run_id": ctx.run_id})

    def _fetch_detail_html(self, ctx: TaskContext, detail_url: str) -> str:
        response = self._request(ctx, "GET", detail_url, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": LIST_REFERER,
        })
        response.encoding = response.apparent_encoding or "utf-8"
        text = response.text
        if looks_like_block_page(text):
            raise CrawlStopped("detail page looked like a block or captcha page")
        return text

    def _download_pdf(self, ctx: TaskContext, pdf_url: str) -> bytes:
        # curl-cffi with Chrome TLS fingerprint impersonation to bypass anti-bot.
        # Imported lazily so the module loads even when curl_cffi isn't installed
        # (tests monkeypatch this method and don't need the real client).
        from curl_cffi import requests as curl_requests

        session = curl_requests.Session(impersonate="chrome")
        try:
            response = session.get(
                pdf_url,
                headers={"Accept": "application/pdf,*/*;q=0.8", "Referer": LIST_REFERER},
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
                if 500 <= response.status_code < 600:
                    raise RuntimeError(f"server error HTTP {response.status_code}")
                response.raise_for_status()
                return response
            except CrawlStopped:
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


# ─────────────────────────────────────────────────────────────────────────────
# Pure helpers (adapted from the original crawler)
# ─────────────────────────────────────────────────────────────────────────────

def normalize_report(
    raw_report: Dict[str, Any],
    security_id_cache: Dict[str, Optional[int]],
) -> Dict[str, Any]:
    """Normalize a raw eastmoney list row into a phoenixA download-record row.

    Returns DOWNLOAD-TASK metadata only (no status/pdf_object_key/pdf_url/
    last_error — phoenixA sets those). Research-report business content is NOT
    curated — this table is a download tracker, not a report-content table.
    `subject_id` is None when the stock is not yet in the registry; the report
    is still upserted (with subject_source_code set) so it is tracked and the
    list cursor advances past it. subject_id is NOT auto-back-filled (the list
    cursor won't re-scan older records); back-filling needs a separate job.
    """
    info_code = str(raw_report.get("infoCode") or "").strip()
    if not info_code:
        raise ValueError(f"missing infoCode in report: {raw_report}")

    stock_code = str(raw_report.get("stockCode") or "").strip()
    return {
        "resource_id": info_code,                 # source-defined id (eastmoney infoCode)
        "report_type": "stock",
        "subject_id": security_id_cache.get(stock_code),  # security_id for stock; None if unresolvable
        "subject_source_code": stock_code,        # always populated; path + later subject_id backfill
        "publish_date": normalize_publish_date(str(raw_report.get("publishDate") or "")),
        "title": text_or_empty(raw_report.get("title")),
        "org_name": text_or_empty(raw_report.get("orgName")),
        "detail_url": DETAIL_URL_TEMPLATE.format(info_code=info_code),
    }


def extract_pdf_url(detail_html: str) -> str:
    unescaped = html.unescape(detail_html)
    matches = PDF_URL_RE.findall(unescaped)
    if not matches:
        return ""
    return matches[0].replace("&amp;", "&")


def build_object_key(report: Dict[str, Any], minio_client, subject: str = "") -> str:
    """Build the MinIO object key.

    "{prefix}/{subject}/{publish_date}_{title}.pdf"

    prefix: stock_prefix for report_type=stock, industry_prefix for industry.
    subject: subject_source_code (raw symbol for stock, industry code for
    future industry reports) — always present, so no runtime resolution needed.
    No resource_id segment — the user-required filename is {date}_{title}.pdf.
    Same-subject/same-date/same-title collisions are accepted (deemed rare).
    """
    report_type = str(report.get("report_type") or "stock")
    if report_type == "industry":
        prefix = getattr(minio_client, "industry_prefix", "industry") or "industry"
    else:
        prefix = getattr(minio_client, "stock_prefix", "stock") or "stock"
    subject_safe = safe_filename_part(subject or "unknown")
    publish_date = str(report.get("publish_date") or "unknown-date")
    title = safe_filename_part(str(report.get("title") or "untitled"), max_len=120)
    return f"{prefix}/zh/{subject_safe}/{publish_date}_{title}.pdf"


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
