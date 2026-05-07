from typing import Dict, List, Optional

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
        ctx.logger.error({
            'event': 'missing_exchange',
            'reason': 'exchange is required when symbols is specified',
        })
        return None

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


