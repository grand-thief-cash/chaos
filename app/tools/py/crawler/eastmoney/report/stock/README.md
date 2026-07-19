# Eastmoney Stock Report Crawler

Edit the configuration block at the top of `main.py`, then run:

```shell
python app/tools/py/crawler/eastmoney/report/stock/main.py
```

There are no command-line parameters by design.

Important settings:

- `DATE_MODE = "day"` downloads all reports for `ONLY_DATE`.
- `DATE_MODE = "since"` downloads reports from `EARLIEST_DATE` through `LATEST_DATE`.
- `LATEST_DATE = None` means today's local date at script start.
- `DOWNLOAD_LIMIT = 10` is the safe test default. Set it to `None` for a full run.

The crawler walks Eastmoney's newest-first pages backward, so downloads happen
from older report dates to newer report dates.

Outputs:

- `data/state.sqlite`: resumable crawl state.
- `data/reports.csv`: table data plus detail/PDF status.
- `data/reports.jsonl`: same data with the raw Eastmoney row included.
- `data/pdfs/YYYY-MM-DD/*.pdf`: downloaded PDFs.

Safety behavior:

- Single-threaded.
- Fixed page size of 50.
- Random sleeps between list, detail, and PDF requests.
- Long pause and stop on likely block, CAPTCHA, or rate-limit responses.
- Existing valid PDFs are skipped on rerun.
