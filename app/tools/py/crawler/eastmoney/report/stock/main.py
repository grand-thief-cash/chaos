import csv
import html
import json
import random
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


# =============================================================================
# Runtime configuration
# =============================================================================
#
# Edit this block before running. This script intentionally does not accept
# command-line parameters, so accidental large runs are less likely.

# "since": download reports from EARLIEST_DATE through LATEST_DATE.
# "day": download all reports for ONLY_DATE.
DATE_MODE = "since"

# Used when DATE_MODE = "day".
ONLY_DATE = "2026-07-05"

# Used when DATE_MODE = "since".
# Eastmoney's stock-report table is a rolling two-year window; keep this at the
# oldest date you want, and the script will process from old to new.
EARLIEST_DATE = "2024-07-05"

# None means today's local date at script start.
LATEST_DATE: Optional[str] = None

# Safety default: test with 10 reports first. Set to None only for a full run.
DOWNLOAD_LIMIT: Optional[int] = 10

# Output is created under this script directory.
DATA_DIR = Path(__file__).resolve().parent / "data"
PDF_DIR = DATA_DIR / "pdfs"
DB_PATH = DATA_DIR / "state.sqlite"
CSV_PATH = DATA_DIR / "reports.csv"
JSONL_PATH = DATA_DIR / "reports.jsonl"

# Keep the official page size. Do not raise this to reduce request count.
PAGE_SIZE = 50

# Conservative pacing. The crawler is single-threaded by design.
LIST_PAGE_SLEEP_SECONDS = (3.0, 6.0)
DETAIL_PAGE_SLEEP_SECONDS = (7.0, 15.0)
PDF_DOWNLOAD_SLEEP_SECONDS = (9.0, 18.0)
RETRY_SLEEP_SECONDS = (45.0, 120.0)
BLOCK_SLEEP_SECONDS = (30 * 60.0, 90 * 60.0)

REQUEST_TIMEOUT_SECONDS = (10, 60)
MAX_REQUEST_RETRIES = 3
EXPORT_EVERY_PROCESSED = 10
RETRY_FAILED_REPORTS = True
RETRY_NO_PDF_REPORTS = False

# A stable browser-like user agent is enough. Do not rotate identities.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/149.0.0.0 Safari/537.36"
)


LIST_API_URL = "https://reportapi.eastmoney.com/report/list2"
LIST_REFERER = "https://data.eastmoney.com/report/stock.jshtml"
DETAIL_URL_TEMPLATE = "https://data.eastmoney.com/report/info/{info_code}.html"
PDF_URL_RE = re.compile(
    r"https?://pdf\.dfcfw\.com/pdf/[^\"'<>\s]+?\.pdf(?:\?[^\"'<>\s]+)?",
    re.IGNORECASE,
)

RATING_CHANGE_NAMES = {
    1: "调高",
    2: "首次",
    3: "维持",
    4: "调低",
}

REPORT_STATUSES_TO_RETRY = {"pending", "detail_error", "pdf_error"}
CSV_FIELDS = [
    "info_code",
    "publish_date",
    "current_year",
    "stock_code",
    "stock_name",
    "stock_detail_url",
    "stock_guba_url",
    "title",
    "detail_url",
    "em_rating_name",
    "last_em_rating_name",
    "rating_change",
    "rating_change_name",
    "org_code",
    "org_name",
    "org_short_name",
    "report_count_1m",
    "predict_this_year_eps",
    "predict_this_year_pe",
    "predict_next_year_eps",
    "predict_next_year_pe",
    "industry_code",
    "industry_name",
    "researcher",
    "attach_size_kb",
    "attach_pages",
    "encode_url",
    "source_serial_no",
    "source_page",
    "source_row_index",
    "pdf_url",
    "pdf_path",
    "status",
    "last_error",
    "updated_at",
]


@dataclass(frozen=True)
class DateRange:
    begin: str
    end: str


class CrawlStopped(RuntimeError):
    pass


class EastMoneyStockReportCrawler:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "keep-alive",
            }
        )
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        PDF_DIR.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def close(self) -> None:
        self.conn.close()

    def run(self) -> None:
        date_range = resolve_date_range()
        log(
            "run config: "
            f"date_mode={DATE_MODE}, begin={date_range.begin}, end={date_range.end}, "
            f"download_limit={DOWNLOAD_LIMIT}"
        )

        first_page = self.fetch_list_page(date_range, page_no=1)
        total_pages = int(first_page.get("TotalPage") or 0)
        hits = int(first_page.get("hits") or 0)
        log(f"list metadata: hits={hits}, total_pages={total_pages}, page_size={PAGE_SIZE}")
        if total_pages <= 0:
            log("no reports found for this date range")
            return

        processed = 0
        # Eastmoney sorts newest first. Walking pages and rows backward processes
        # the rolling two-year window from oldest to newest.
        for page_no in range(total_pages, 0, -1):
            if DOWNLOAD_LIMIT is not None and processed >= DOWNLOAD_LIMIT:
                break

            if page_no == 1:
                payload = first_page
            else:
                self.sleep_between(LIST_PAGE_SLEEP_SECONDS, f"before list page {page_no}")
                payload = self.fetch_list_page(date_range, page_no=page_no)

            current_year = int(payload.get("currentYear") or date.today().year)
            rows = list(payload.get("data") or [])
            log(f"processing list page {page_no}/{total_pages}, rows={len(rows)}")

            for source_row_index, raw_report in reversed(list(enumerate(rows, start=1))):
                if DOWNLOAD_LIMIT is not None and processed >= DOWNLOAD_LIMIT:
                    break

                report = normalize_report(raw_report, page_no, source_row_index, current_year)
                self.upsert_report(report)

                if not self.should_process_report(report["info_code"]):
                    continue

                processed += 1
                try:
                    self.process_report(report["info_code"])
                except CrawlStopped:
                    raise
                except Exception as exc:
                    self.mark_report_error(report["info_code"], "pdf_error", str(exc))
                    log(f"report failed: {report['info_code']} {exc}")

                if processed % EXPORT_EVERY_PROCESSED == 0:
                    self.export_outputs()

        self.export_outputs()
        log(f"done: newly processed reports={processed}")

    def fetch_list_page(self, date_range: DateRange, page_no: int) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "beginTime": date_range.begin,
            "endTime": date_range.end,
            "industryCode": "*",
            "ratingChange": None,
            "rating": None,
            "orgCode": None,
            "code": "*",
            "rcode": "",
            "pageSize": PAGE_SIZE,
            "p": page_no,
            "pageNo": page_no,
            "pageNum": page_no,
            "pageNumber": page_no,
        }
        response = self.request(
            "POST",
            LIST_API_URL,
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/json",
                "Origin": "https://data.eastmoney.com",
                "Referer": LIST_REFERER,
            },
            json=body,
        )
        payload = response.json()
        if "data" not in payload:
            raise RuntimeError(f"unexpected list response keys: {sorted(payload.keys())}")
        return payload

    def process_report(self, info_code: str) -> None:
        report = self.get_report(info_code)
        if report is None:
            raise RuntimeError(f"report not found in db: {info_code}")

        existing_pdf_path = str(report["pdf_path"] or "")
        if existing_pdf_path and is_valid_pdf(Path(existing_pdf_path)):
            self.mark_report_downloaded(info_code, str(report["pdf_url"] or ""), existing_pdf_path)
            log(f"already downloaded: {info_code}")
            return

        self.sleep_between(DETAIL_PAGE_SLEEP_SECONDS, f"before detail page {info_code}")
        detail_url = str(report["detail_url"])
        try:
            detail_html = self.fetch_detail_html(detail_url)
            pdf_url = extract_pdf_url(detail_html)
        except Exception as exc:
            self.mark_report_error(info_code, "detail_error", str(exc))
            raise

        if not pdf_url:
            self.mark_report_no_pdf(info_code)
            log(f"no pdf link found: {info_code}")
            return

        pdf_path = build_pdf_path(report)
        if is_valid_pdf(pdf_path):
            self.mark_report_downloaded(info_code, pdf_url, str(pdf_path))
            log(f"already downloaded: {info_code} -> {pdf_path}")
            return

        self.sleep_between(PDF_DOWNLOAD_SLEEP_SECONDS, f"before pdf download {info_code}")
        self.download_pdf(pdf_url, pdf_path)
        self.mark_report_downloaded(info_code, pdf_url, str(pdf_path))
        log(f"downloaded: {info_code} -> {pdf_path}")

    def fetch_detail_html(self, detail_url: str) -> str:
        response = self.request(
            "GET",
            detail_url,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": LIST_REFERER,
            },
        )
        response.encoding = response.apparent_encoding or "utf-8"
        text = response.text
        if looks_like_block_page(text):
            self.sleep_between(BLOCK_SLEEP_SECONDS, "block/captcha-like detail response")
            raise CrawlStopped("detail page looked like a block or captcha page")
        return text

    def download_pdf(self, pdf_url: str, pdf_path: Path) -> None:
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        part_path = pdf_path.with_suffix(pdf_path.suffix + ".part")
        response = self.request(
            "GET",
            pdf_url,
            headers={
                "Accept": "application/pdf,*/*;q=0.8",
                "Referer": LIST_REFERER,
            },
            stream=True,
        )
        content_type = response.headers.get("Content-Type", "")
        with part_path.open("wb") as out_file:
            for chunk in response.iter_content(chunk_size=1024 * 128):
                if chunk:
                    out_file.write(chunk)

        if not is_valid_pdf(part_path):
            if "text/html" in content_type.lower():
                self.sleep_between(BLOCK_SLEEP_SECONDS, "html returned instead of pdf")
                raise CrawlStopped(f"pdf request returned html: {pdf_url}")
            raise RuntimeError(f"downloaded file is not a valid pdf: {pdf_url}")

        part_path.replace(pdf_path)

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        last_exc: Optional[BaseException] = None
        for attempt in range(1, MAX_REQUEST_RETRIES + 1):
            try:
                response = self.session.request(
                    method,
                    url,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                    **kwargs,
                )
                if response.status_code in {403, 429, 503}:
                    log(f"rate-limit/block status={response.status_code} url={url}")
                    self.sleep_between(BLOCK_SLEEP_SECONDS, "rate-limit/block response")
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
                log(f"request retry {attempt}/{MAX_REQUEST_RETRIES}: {method} {url} ({exc})")
                self.sleep_between(RETRY_SLEEP_SECONDS, "request retry")
        raise RuntimeError(f"request failed after retries: {method} {url}: {last_exc}")

    def should_process_report(self, info_code: str) -> bool:
        row = self.get_report(info_code)
        if row is None:
            return False
        status = str(row["status"] or "pending")
        pdf_path = str(row["pdf_path"] or "")
        if status == "downloaded" and pdf_path and is_valid_pdf(Path(pdf_path)):
            return False
        if status == "no_pdf" and not RETRY_NO_PDF_REPORTS:
            return False
        if status in REPORT_STATUSES_TO_RETRY:
            return RETRY_FAILED_REPORTS or status == "pending"
        return status in {"pending", "pdf_error", "detail_error"}

    def upsert_report(self, report: Dict[str, Any]) -> None:
        now = now_text()
        existing = self.get_report(report["info_code"])
        if existing is None:
            columns = [
                *CSV_FIELDS,
                "raw_json",
                "created_at",
            ]
            values = {
                **report,
                "pdf_url": "",
                "pdf_path": "",
                "status": "pending",
                "last_error": "",
                "updated_at": now,
                "created_at": now,
            }
            placeholders = ",".join("?" for _ in columns)
            self.conn.execute(
                f"INSERT INTO reports ({','.join(columns)}) VALUES ({placeholders})",
                [values.get(column, "") for column in columns],
            )
        else:
            update_columns = [
                column
                for column in CSV_FIELDS
                if column not in {"pdf_url", "pdf_path", "status", "last_error", "updated_at"}
            ]
            set_clause = ",".join(f"{column}=?" for column in update_columns)
            self.conn.execute(
                f"UPDATE reports SET {set_clause}, raw_json=?, updated_at=? WHERE info_code=?",
                [report.get(column, "") for column in update_columns]
                + [report.get("raw_json", ""), now, report["info_code"]],
            )
        self.conn.commit()

    def get_report(self, info_code: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM reports WHERE info_code = ?",
            (info_code,),
        ).fetchone()

    def mark_report_downloaded(self, info_code: str, pdf_url: str, pdf_path: str) -> None:
        self.conn.execute(
            """
            UPDATE reports
            SET pdf_url = ?, pdf_path = ?, status = 'downloaded',
                last_error = '', updated_at = ?
            WHERE info_code = ?
            """,
            (pdf_url, pdf_path, now_text(), info_code),
        )
        self.conn.commit()

    def mark_report_no_pdf(self, info_code: str) -> None:
        self.conn.execute(
            """
            UPDATE reports
            SET status = 'no_pdf', last_error = '', updated_at = ?
            WHERE info_code = ?
            """,
            (now_text(), info_code),
        )
        self.conn.commit()

    def mark_report_error(self, info_code: str, status: str, error: str) -> None:
        self.conn.execute(
            """
            UPDATE reports
            SET status = ?, last_error = ?, updated_at = ?
            WHERE info_code = ?
            """,
            (status, error[:2000], now_text(), info_code),
        )
        self.conn.commit()

    def export_outputs(self) -> None:
        rows = self.conn.execute(
            """
            SELECT *
            FROM reports
            ORDER BY publish_date ASC, source_page DESC, source_row_index DESC, info_code ASC
            """
        ).fetchall()
        with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row[field] for field in CSV_FIELDS})

        with JSONL_PATH.open("w", encoding="utf-8") as jsonl_file:
            for row in rows:
                item = {field: row[field] for field in CSV_FIELDS}
                raw_json = row["raw_json"]
                if raw_json:
                    item["raw"] = json.loads(raw_json)
                jsonl_file.write(json.dumps(item, ensure_ascii=False) + "\n")

        log(f"exported: {CSV_PATH} and {JSONL_PATH}")

    def sleep_between(self, seconds_range: Tuple[float, float], reason: str) -> None:
        sleep_seconds = random.uniform(*seconds_range)
        log(f"sleep {sleep_seconds:.1f}s: {reason}")
        time.sleep(sleep_seconds)

    def _init_db(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                info_code TEXT PRIMARY KEY,
                publish_date TEXT,
                current_year INTEGER,
                stock_code TEXT,
                stock_name TEXT,
                stock_detail_url TEXT,
                stock_guba_url TEXT,
                title TEXT,
                detail_url TEXT,
                em_rating_name TEXT,
                last_em_rating_name TEXT,
                rating_change INTEGER,
                rating_change_name TEXT,
                org_code TEXT,
                org_name TEXT,
                org_short_name TEXT,
                report_count_1m INTEGER,
                predict_this_year_eps TEXT,
                predict_this_year_pe TEXT,
                predict_next_year_eps TEXT,
                predict_next_year_pe TEXT,
                industry_code TEXT,
                industry_name TEXT,
                researcher TEXT,
                attach_size_kb TEXT,
                attach_pages TEXT,
                encode_url TEXT,
                source_serial_no INTEGER,
                source_page INTEGER,
                source_row_index INTEGER,
                pdf_url TEXT,
                pdf_path TEXT,
                status TEXT,
                last_error TEXT,
                updated_at TEXT,
                raw_json TEXT,
                created_at TEXT
            )
            """
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_reports_publish_date ON reports(publish_date)"
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status)")
        self.conn.commit()


def resolve_date_range() -> DateRange:
    if DATE_MODE not in {"since", "day"}:
        raise ValueError("DATE_MODE must be 'since' or 'day'")
    if DATE_MODE == "day":
        validate_date_text(ONLY_DATE)
        return DateRange(begin=ONLY_DATE, end=ONLY_DATE)

    validate_date_text(EARLIEST_DATE)
    end = LATEST_DATE or date.today().isoformat()
    validate_date_text(end)
    if EARLIEST_DATE > end:
        raise ValueError(f"EARLIEST_DATE must be <= LATEST_DATE: {EARLIEST_DATE} > {end}")
    return DateRange(begin=EARLIEST_DATE, end=end)


def validate_date_text(value: str) -> None:
    datetime.strptime(value, "%Y-%m-%d")


def normalize_report(
    raw_report: Dict[str, Any],
    source_page: int,
    source_row_index: int,
    current_year: int,
) -> Dict[str, Any]:
    info_code = str(raw_report.get("infoCode") or "").strip()
    if not info_code:
        raise ValueError(f"missing infoCode in report: {raw_report}")

    stock_code = str(raw_report.get("stockCode") or "").strip()
    publish_date = normalize_publish_date(str(raw_report.get("publishDate") or ""))
    rating_change = raw_report.get("ratingChange")
    rating_change_int = to_int_or_none(rating_change)

    return {
        "info_code": info_code,
        "publish_date": publish_date,
        "current_year": current_year,
        "stock_code": stock_code,
        "stock_name": text_or_empty(raw_report.get("stockName")),
        "stock_detail_url": f"https://data.eastmoney.com/report/{stock_code}.html"
        if stock_code
        else "",
        "stock_guba_url": f"https://guba.eastmoney.com/list,{stock_code}.html"
        if stock_code
        else "",
        "title": text_or_empty(raw_report.get("title")),
        "detail_url": DETAIL_URL_TEMPLATE.format(info_code=info_code),
        "em_rating_name": text_or_dash(raw_report.get("emRatingName")),
        "last_em_rating_name": text_or_dash(raw_report.get("lastEmRatingName")),
        "rating_change": rating_change_int if rating_change_int is not None else "",
        "rating_change_name": RATING_CHANGE_NAMES.get(rating_change_int, ""),
        "org_code": text_or_empty(raw_report.get("orgCode")),
        "org_name": text_or_empty(raw_report.get("orgName")),
        "org_short_name": text_or_empty(raw_report.get("orgSName")),
        "report_count_1m": to_int_or_empty(raw_report.get("count")),
        "predict_this_year_eps": text_or_empty(raw_report.get("predictThisYearEps")),
        "predict_this_year_pe": text_or_empty(raw_report.get("predictThisYearPe")),
        "predict_next_year_eps": text_or_empty(raw_report.get("predictNextYearEps")),
        "predict_next_year_pe": text_or_empty(raw_report.get("predictNextYearPe")),
        "industry_code": text_or_empty(
            raw_report.get("indvInduCode") or raw_report.get("industryCode")
        ),
        "industry_name": text_or_empty(
            raw_report.get("indvInduName") or raw_report.get("industryName")
        ),
        "researcher": text_or_empty(raw_report.get("researcher")),
        "attach_size_kb": text_or_empty(raw_report.get("attachSize")),
        "attach_pages": text_or_empty(raw_report.get("attachPages")),
        "encode_url": text_or_empty(raw_report.get("encodeUrl")),
        "source_serial_no": (source_page - 1) * PAGE_SIZE + source_row_index,
        "source_page": source_page,
        "source_row_index": source_row_index,
        "raw_json": json.dumps(raw_report, ensure_ascii=False, sort_keys=True),
    }


def extract_pdf_url(detail_html: str) -> str:
    unescaped = html.unescape(detail_html)
    matches = PDF_URL_RE.findall(unescaped)
    if not matches:
        return ""
    return matches[0].replace("&amp;", "&")


def build_pdf_path(report: sqlite3.Row) -> Path:
    publish_date = str(report["publish_date"] or "unknown-date")
    stock_code = str(report["stock_code"] or "unknown")
    stock_name = safe_filename_part(str(report["stock_name"] or "unknown"))
    info_code = safe_filename_part(str(report["info_code"]))
    filename = f"{info_code}_{stock_code}_{stock_name}.pdf"
    return PDF_DIR / publish_date / filename


def is_valid_pdf(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False
    if path.stat().st_size < 1024:
        return False
    with path.open("rb") as file:
        return file.read(5) == b"%PDF-"


def looks_like_block_page(text: str) -> bool:
    sample = text[:5000].lower()
    return any(
        needle in sample
        for needle in [
            "访问过于频繁",
            "安全验证",
            "人机验证",
            "请输入验证码",
            "系统检测到异常访问",
        ]
    )


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


def text_or_dash(value: Any) -> str:
    text = text_or_empty(value)
    return text if text else "-"


def to_int_or_none(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def to_int_or_empty(value: Any) -> Any:
    parsed = to_int_or_none(value)
    return parsed if parsed is not None else ""


def now_text() -> str:
    return datetime.now().isoformat(timespec="seconds")


def log(message: str) -> None:
    print(f"[{now_text()}] {message}", flush=True)


def main() -> None:
    crawler = EastMoneyStockReportCrawler()
    try:
        crawler.run()
    finally:
        crawler.close()


if __name__ == "__main__":
    main()
