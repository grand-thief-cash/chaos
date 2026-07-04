from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from artemis.consts import DeptServices
from artemis.core import TaskContext


def convert_to_baostock_params(param_name, param_val):
    if param_name == "frequency":
        mapping = {
            "daily": "d",
            "weekly": "w",
            "monthly": "m",
            "5min": "5",
            "15min": "15",
            "30min": "30",
            "60min": "60",
        }
        return mapping.get(param_val)
    elif param_name == "adjustflag":
        mapping = {
            "hfq":"1",
            "qfq":"2",
            "nf":"3"
        }
        return mapping.get(param_val)
    return None


# ─────────── Shared Download Helpers ───────────


def get_symbols_from_params(ctx: TaskContext) -> Optional[List[str]]:
    """Build AmazingData code_list from ctx.params['symbols'] + ctx.params['exchange'].

    In task.yaml / params, symbols and exchange are configured separately:
        symbols: ["000001", "600519"]
        exchange: "SZ"
    This function combines them into AmazingData format: ["000001.SZ", "600519.SZ"]

    Rules:
      - If 'symbols' is absent/empty → returns None (caller uses full code list)
      - If 'symbols' is present, 'exchange' is REQUIRED
      - exchange is a single value, e.g. "SZ" or "SH"

    Returns: list in AmazingData format, or None for full-download mode.
    """
    params = ctx.params or {}
    raw = params.get('symbols')
    if not raw:
        return None

    if isinstance(raw, str):
        raw = [s.strip() for s in raw.split(',') if s.strip()]
    if not isinstance(raw, list) or not raw:
        return None

    exchange = str(params.get('exchange', '')).strip().upper()
    if not exchange:
        raise ValueError("exchange is required when symbols is specified. "
                         f"Got symbols={raw}, but exchange is empty. "
                         "Example: symbols=['000001'] + exchange='SZ'")

    symbols = [str(s).strip() for s in raw if str(s).strip()]
    code_list = [f"{sym}.{exchange}" for sym in symbols]
    return code_list


def get_sdk_date_kwargs(ctx: TaskContext) -> Dict[str, int]:
    """Convert our unified start_date/end_date (YYYY-MM-DD str) to SDK begin_date/end_date (int).

    Our project convention:
      - Dates in params are always 'YYYY-MM-DD' strings (e.g. '2024-01-01')
      - AmazingData SDK expects int (e.g. 20240101) as begin_date/end_date

    Returns dict with only present entries, e.g. {'begin_date': 20240101}.
    """
    params = ctx.params or {}
    result: Dict[str, int] = {}
    mapping = {'start_date': 'begin_date', 'end_date': 'end_date'}
    for our_key, sdk_key in mapping.items():
        val = params.get(our_key)
        if val is None or val == '' or val == 'null':
            continue
        date_str = str(val).strip()
        try:
            int_val = int(date_str.replace('-', ''))
            result[sdk_key] = int_val
        except (ValueError, TypeError):
            ctx.logger.warning({
                'event': 'invalid_date_param',
                'param': our_key,
                'value': val,
                'expected_format': 'YYYY-MM-DD',
            })
    return result


# ─────────── Data Normalization Helpers ───────────


def normalize_date_yyyymmdd(date_str: str) -> str:
    """Convert YYYYMMDD string to YYYY-MM-DD.

    "20260425"   → "2026-04-25"
    "2026-04-25" → "2026-04-25"  (pass through)
    ""           → ""
    None/NaN     → ""
    """
    if not date_str:
        return ''
    s = str(date_str).strip()
    if not s:
        return ''
    if len(s) == 10 and s[4] == '-' and s[7] == '-':
        return s  # already YYYY-MM-DD
    digits = s.replace('.', '').replace('-', '')
    if len(digits) == 8 and digits.isdigit():
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return s  # return as-is if unrecognizable


def get_security_map_from_phoenixa(
    ctx: TaskContext,
    asset_type: str = "stock",
    market: str = "zh_a",
    symbols: Optional[List[str]] = None,
    exchanges: Optional[List[str]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Fetch securities from PhoenixA and return a map keyed by AmazingData
    code ("SYMBOL.EXCHANGE") → {symbol, exchange, security_id}.

    Phase 3: download tasks use this both to iterate SDK codes and to resolve
    each SDK response row's MARKET_CODE → security_id for the upsert payload
    (the data-table APIs are security_id-only). Returns {} on failure or if
    the registry is empty.
    """
    phoenixA_client = ctx.dept_http.get(DeptServices.PHOENIXA)
    if phoenixA_client is None or not hasattr(phoenixA_client, 'get_securities'):
        ctx.logger.warning({
            'event': 'phoenixa_client_unavailable',
            'run_id': ctx.run_id,
            'reason': 'client is None or missing get_securities method',
        })
        return {}
    try:
        securities = phoenixA_client.get_securities(
            asset_type=asset_type,
            market=market,
            symbols=symbols,
            exchanges=exchanges,
        )
    except Exception as e:
        ctx.logger.warning({
            'event': 'get_security_map_from_phoenixa_failed',
            'error': str(e),
            'run_id': ctx.run_id,
        })
        return {}
    security_map: Dict[str, Dict[str, Any]] = {}
    for sym, info in securities.items():
        exchange = (info.get('exchange') or '').upper()
        sid = info.get('security_id', 0)
        if sym and exchange and sid:
            security_map[f"{sym}.{exchange}"] = {
                "symbol": sym,
                "exchange": exchange,
                "security_id": int(sid),
            }
    if not security_map:
        ctx.logger.warning({
            'event': 'phoenixa_securities_empty',
            'run_id': ctx.run_id,
            'hint': 'PhoenixA registry may be empty or API returned no data',
        })
    return security_map


def get_security_map_for_task(
    ctx: TaskContext, asset_type: str = "stock", market: str = "zh_a"
) -> Dict[str, Dict[str, Any]]:
    """Resolve the security map for a download task.

    Uses explicit symbols+exchange from ctx.params (resolved to security_id via
    the registry) when present, otherwise the full registry. Securities not in
    the registry are dropped — Phase 3 requires a security_id (refactor §10.c:
    registry is the only source; a symbol not yet upserted by STOCK_ZH_A_LIST
    cannot be written and must fail rather than produce an orphan).
    """
    explicit_codes = get_symbols_from_params(ctx)  # None or ["SYMBOL.EXCHANGE", ...]
    if explicit_codes is None:
        return get_security_map_from_phoenixa(ctx, asset_type, market)
    # Explicit path: split codes into symbols + exchanges for the resolve.
    syms: List[str] = []
    exs: set = set()
    for c in explicit_codes:
        if '.' in c:
            s, e = c.split('.', 1)
            syms.append(s.strip())
            exs.add(e.strip().upper())
    full = get_security_map_from_phoenixa(
        ctx, asset_type, market,
        symbols=syms or None,
        exchanges=sorted(exs) or None,
    )
    # Keep only the explicitly-requested codes that resolved to a security_id.
    return {c: full[c] for c in explicit_codes if c in full}


# ─────────── Baostock Helpers ───────────


def date_range_to_year_quarters(start_date: str, end_date: str) -> List[Tuple[int, int]]:
    """Convert a YYYY-MM-DD date range into a list of (year, quarter) tuples.

    e.g. ("2024-06-01", "2025-03-31") → [(2024,2), (2024,3), (2024,4), (2025,1)]
    Quarters are 1-indexed: Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec.
    """
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        return []

    result: List[Tuple[int, int]] = []
    y, q = start.year, (start.month - 1) // 3 + 1
    end_y, end_q = end.year, (end.month - 1) // 3 + 1

    while (y, q) <= (end_y, end_q):
        result.append((y, q))
        q += 1
        if q > 4:
            q = 1
            y += 1
    return result


def symbol_exchange_to_bs_code(symbol: str, exchange: str) -> Optional[str]:
    """Convert (symbol, exchange) to baostock code format.

    ("600000", "SH") → "sh.600000"
    ("000001", "SZ") → "sz.000001"
    Returns None if exchange is not SH/SZ/BJ.
    """
    ex = exchange.upper()
    if ex in ("SH", "SZ", "BJ"):
        return f"{ex.lower()}.{symbol}"
    return None
