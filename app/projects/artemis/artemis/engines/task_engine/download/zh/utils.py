from typing import Dict, List, Optional

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


def split_market_code(market_code: str) -> tuple:
    """Split AmazingData MARKET_CODE into (symbol, market).

    "000001.SZ" → ("000001", "zh_a")
    "600519.SH" → ("600519", "zh_a")
    "000001"     → ("000001", "zh_a")

    All A-share stocks map to market='zh_a'.
    """
    code = str(market_code).strip()
    if '.' in code:
        return code.split('.', 1)[0], 'zh_a'
    return code, 'zh_a'


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


def get_code_list_from_phoenixa(ctx: TaskContext, asset_type: str = "stock", market: str = "zh_a") -> List[str]:
    """Fetch all security codes from PhoenixA and convert to SDK format.

    Returns code_list in AmazingData format: ["000001.SZ", "600519.SH"]
    Falls back to empty list on failure.
    """
    phoenixA_client = ctx.dept_http.get(DeptServices.PHOENIXA)
    if phoenixA_client is None or not hasattr(phoenixA_client, 'get_securities'):
        ctx.logger.warning({
            'event': 'phoenixa_client_unavailable',
            'run_id': ctx.run_id,
            'reason': 'client is None or missing get_securities method',
        })
        return []
    try:
        securities = phoenixA_client.get_securities(
            asset_type=asset_type,
            market=market,
        )
    except Exception as e:
        ctx.logger.warning({
            'event': 'get_code_list_from_phoenixa_failed',
            'error': str(e),
            'run_id': ctx.run_id,
        })
        return []
    code_list = []
    for sym, info in securities.items():
        exchange = info.get('exchange', '').upper()
        if sym and exchange:
            code_list.append(f"{sym}.{exchange}")
    if not code_list:
        ctx.logger.warning({
            'event': 'phoenixa_securities_empty',
            'run_id': ctx.run_id,
            'hint': 'PhoenixA registry may be empty or API returned no data',
        })
    return code_list


