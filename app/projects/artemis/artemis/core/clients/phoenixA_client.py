from typing import Dict, Any, Iterator, List, Optional

from artemis.consts.task_params import ADJUST_NONE
from artemis.core.clients.dept_clients import HTTPDeptServiceClient


# Unified field name constants (matching PhoenixA v2)
_V2_BARS_FIELDS = [
    "trade_date",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
]


def _normalize_bars_v2_to_cache(bars: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rename v2 fields to CacheEngine-compatible names: trade_date→date, symbol→code."""
    out = []
    for bar in bars:
        row = dict(bar)
        if "trade_date" in row and "date" not in row:
            row["date"] = row.pop("trade_date")
        if "symbol" in row and "code" not in row:
            row["code"] = row.pop("symbol")
        out.append(row)
    return out


class PhoenixAClient(HTTPDeptServiceClient):
    """
    Client for interacting with PhoenixA service.
    Inherits HTTPDeptServiceClient for OTEL traceparent injection + connection pooling.

    All methods use PhoenixA v2 API with unified field naming:
      - symbol (not code)
      - trade_date (not date)
      - period (not timeframe/freq)
    """

    # ──────────── Securities (v2) ────────────

    def upsert_securities(self, payload: List[Dict[str, Any]], run_id: Optional[int | str] = None) -> bool:
        """Batch upsert securities via v2 API."""
        path = "/api/v2/securities/upsert"
        try:
            resp = self.post(path, payload)
            ok = 200 <= resp.status_code < 300
            if not ok and self.logger:
                self.logger.warning({
                    'event': 'phoenixA_upsert_securities_failure',
                    'run_id': run_id,
                    'path': path,
                    'status': resp.status_code,
                    'body_snippet': resp.text[:120],
                })
            return ok
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_upsert_securities_exception',
                    'run_id': run_id,
                    'error': str(e),
                })
            raise

    def get_securities(
        self,
        *,
        symbols: Optional[List[str]] = None,
        asset_type: str = "stock",
        market: str = "zh_a",
        exchanges: Optional[List[str]] = None,
        status: Optional[str] = None,
        limit: int = 20000,
    ) -> Dict[str, Dict[str, Any]]:
        """Query securities from v2 API."""
        path = "/api/v2/securities"
        params: Dict[str, Any] = {
            "limit": str(limit),
            "asset_type": asset_type,
            "market": market,
        }
        if symbols:
            params["symbol_list"] = ",".join([str(s) for s in symbols if str(s).strip()])
        if exchanges:
            params["exchange"] = ",".join([str(e).strip().upper() for e in exchanges if str(e).strip()])
        if status:
            params["status"] = status

        result: Dict[str, Dict[str, Any]] = {}
        try:
            resp = self.get(path, params)
            if 200 <= resp.status_code < 300:
                data = resp.json()
                rows = data.get("data") or data.get("list") or []
                for item in rows:
                    if isinstance(item, dict) and "symbol" in item:
                        sym = str(item["symbol"])
                        result[sym] = {
                            "symbol": sym,
                            "name": str(item.get("name", "")),
                            "full_name": str(item.get("full_name", "")) if item.get("full_name") is not None else "",
                            "exchange": str(item.get("exchange", "")).upper(),
                            "asset_type": str(item.get("asset_type", asset_type)),
                            "market": str(item.get("market", market)),
                            "status": str(item.get("status", "")),
                            "list_date": str(item.get("list_date", "")) if item.get("list_date") is not None else "",
                            "delist_date": str(item.get("delist_date", "")) if item.get("delist_date") is not None else "",
                        }
            return result
        except Exception as e:
            if self.logger:
                self.logger.error({'event': 'phoenixA_get_securities_failed', 'error': str(e)})
            return {}

    # ──────────── Bars (v2) ────────────

    def upsert_bars(
        self,
        *,
        asset_type: str = "stock",
        market: str = "zh_a",
        period: str,
        adjust: str,
        source: str = "",
        bars: List[Dict[str, Any]],
        ext: Optional[List[Dict[str, Any]]] = None,
        run_id: Optional[int | str] = None,
    ) -> bool:
        """Upsert bars via v2 API."""
        path = f"/api/v2/bars/{asset_type}/{market}/upsert"
        payload = {
            "meta": {
                "period": period,
                "adjust": adjust,
                "source": source,
            },
            "bars": bars,
        }
        if ext:
            payload["ext"] = ext
        try:
            resp = self.post(path, payload)
            ok = 200 <= resp.status_code < 300
            if not ok and self.logger:
                self.logger.error({
                    'event': 'phoenixA_upsert_bars_failed',
                    'run_id': run_id,
                    'status': resp.status_code,
                    'asset_type': asset_type,
                    'market': market,
                    'bars_count': len(bars),
                    'body_snippet': resp.text[:120],
                })
            return ok
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_upsert_bars_exception',
                    'run_id': run_id,
                    'error': str(e),
                })
            raise

    def get_bars(
        self,
        *,
        asset_type: str = "stock",
        market: str = "zh_a",
        symbol: str,
        start_date: str,
        end_date: str,
        period: str = "daily",
        adjust: str = ADJUST_NONE,
        fields: Optional[List[str]] = None,
        source: str | None = None,
        limit: int = 5000,
        normalize_for_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """Unified bars query via v2 API with pagination.

        If normalize_for_cache=True, renames trade_date→date and symbol→code
        for CacheEngine compatibility.
        """
        return list(self.iter_bars(
            asset_type=asset_type,
            market=market,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            period=period,
            adjust=adjust,
            fields=fields,
            source=source,
            limit=limit,
            normalize_for_cache=normalize_for_cache,
        ))

    def iter_bars(
        self,
        *,
        asset_type: str = "stock",
        market: str = "zh_a",
        symbol: str,
        start_date: str,
        end_date: str,
        period: str = "daily",
        adjust: str = ADJUST_NONE,
        fields: Optional[List[str]] = None,
        source: str | None = None,
        limit: int = 5000,
        normalize_for_cache: bool = True,
    ) -> Iterator[Dict[str, Any]]:
        """Paginated bars iterator via v2 API."""
        path = f"/api/v2/bars/{asset_type}/{market}"
        request_fields = fields or _V2_BARS_FIELDS
        page_size = max(int(limit or 0), 1)
        offset = 0

        try:
            while True:
                params: Dict[str, Any] = {
                    "symbol": symbol,
                    "start_date": start_date,
                    "end_date": end_date,
                    "period": period,
                    "adjust": adjust,
                    "fields": ",".join(request_fields),
                    "limit": page_size,
                    "offset": offset,
                }
                if source:
                    params["source"] = source

                resp = self.get(path, params=params)
                if not (200 <= resp.status_code < 300):
                    if self.logger:
                        self.logger.error({
                            'event': 'phoenixA_get_bars_failed',
                            'path': path,
                            'status': resp.status_code,
                            'symbol': symbol,
                            'period': period,
                            'offset': offset,
                            'body_snippet': resp.text[:120],
                        })
                    return

                batch = self._coerce_hist_rows(resp.json())
                if not batch:
                    return

                if normalize_for_cache:
                    batch = _normalize_bars_v2_to_cache(batch)

                for row in batch:
                    yield row

                if len(batch) < page_size:
                    return

                offset += len(batch)
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_get_bars_exception',
                    'symbol': symbol,
                    'period': period,
                    'error': str(e),
                })
            raise

    def get_bars_last_update(
        self,
        *,
        asset_type: str = "stock",
        market: str = "zh_a",
        period: str,
        adjust: str,
        symbols: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """Query last update dates for symbols via v2 API."""
        path = f"/api/v2/bars/{asset_type}/{market}/last_update"
        params: Dict[str, Any] = {"period": period, "adjust": adjust}
        if symbols:
            params["symbols"] = ",".join([str(s) for s in symbols if str(s).strip()])

        try:
            resp = self.get(path, params)
            if 200 <= resp.status_code < 300:
                data = resp.json()
                if isinstance(data, dict):
                    return data
            return {}
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_get_bars_last_update_failed',
                    'period': period,
                    'adjust': adjust,
                    'error': str(e),
                })
            return {}

    # ──────────── Taxonomy (v2) ────────────

    def sync_mappings_from_constituents(
        self,
        source: str,
        taxonomy: str = "",
        market: str = "zh_a",
        run_id: Optional[int | str] = None,
    ) -> bool:
        """Sync taxonomy_security_map from industry_constituent + taxonomy_category JOIN."""
        path = f"/api/v2/taxonomy/{source}/{taxonomy}/{market}/mapping/sync_from_constituents"
        try:
            resp = self.post(path, {})
            ok = 200 <= resp.status_code < 300
            if not ok and self.logger:
                self.logger.warning({
                    'event': 'phoenixA_sync_mappings_failure',
                    'run_id': run_id,
                    'source': source,
                    'status': resp.status_code,
                    'body_snippet': resp.text[:120],
                })
            return ok
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_sync_mappings_exception',
                    'run_id': run_id,
                    'source': source,
                    'error': str(e),
                })
            return False

    def upsert_taxonomy_categories(
        self,
        categories: List[Dict[str, Any]],
        source: str,
        taxonomy: str = "",
        market: str = "zh_a",
        run_id: Optional[int | str] = None,
    ) -> bool:
        """Upsert taxonomy categories via v2 API."""
        path = f"/api/v2/taxonomy/{source}/{taxonomy}/{market}/categories/upsert"
        try:
            resp = self.post(path, categories)
            ok = 200 <= resp.status_code < 300
            if not ok and self.logger:
                self.logger.warning({
                    'event': 'phoenixA_upsert_taxonomy_failure',
                    'run_id': run_id,
                    'source': source,
                    'status': resp.status_code,
                    'body_snippet': resp.text[:120],
                    'count': len(categories) if categories else 0,
                })
            return ok
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_upsert_taxonomy_exception',
                    'run_id': run_id,
                    'source': source,
                    'error': str(e),
                })
            raise

    # ──────────── Strategy Run (unchanged path) ────────────

    def save_strategy_run_summary(self, payload: Dict[str, Any], run_id: Optional[int | str] = None) -> bool:
        path = "/api/v1/strategy/run/summary/upsert"
        try:
            resp = self.post(path, payload)
            ok = 200 <= resp.status_code < 300
            if not ok and self.logger:
                self.logger.error({
                    'event': 'phoenixA_save_strategy_run_summary_failed',
                    'run_id': run_id,
                    'path': path,
                    'status': resp.status_code,
                    'body_snippet': resp.text[:120],
                })
            return ok
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_save_strategy_run_summary_exception',
                    'run_id': run_id,
                    'error': str(e),
                })
            raise

    def save_strategy_run_artifacts(self, payload: List[Dict[str, Any]], run_id: Optional[int | str] = None) -> bool:
        path = "/api/v1/strategy/run/artifact/upsert"
        try:
            resp = self.post(path, payload)
            ok = 200 <= resp.status_code < 300
            if not ok and self.logger:
                self.logger.error({
                    'event': 'phoenixA_save_strategy_run_artifacts_failed',
                    'run_id': run_id,
                    'artifact_count': len(payload),
                    'body_snippet': resp.text[:120],
                })
            return ok
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_save_strategy_run_artifacts_exception',
                    'run_id': run_id,
                    'artifact_count': len(payload),
                    'error': str(e),
                })
            raise

    # ──────────── Internal helpers ────────────

    def _coerce_hist_rows(self, payload: Any) -> List[Dict[str, Any]]:
        rows = payload.get("data") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)]

    # ──────────── Backward-compatible aliases ────────────

    def stock_zh_a_list_batch_upsert(self, payload: List[Dict[str, Any]], run_id: Optional[int | str] = None) -> bool:
        """Legacy alias → upsert_securities. Converts code/company to symbol/name."""
        converted = []
        for item in payload:
            converted.append({
                "symbol": item.get("code", item.get("symbol", "")),
                "name": item.get("company", item.get("name", "")),
                "exchange": item.get("exchange", ""),
                "asset_type": "stock",
                "market": "zh_a",
            })
        return self.upsert_securities(converted, run_id=run_id)

    def get_stock_zh_a_codes(self, codes: Optional[List[str]] = None, exchanges: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        """Legacy alias → get_securities."""
        return self.get_securities(symbols=codes, exchanges=exchanges)

    def get_stock_zh_a_last_updates(self, period: str, adjust: str, codes: Optional[List[str]] = None) -> Dict[str, str]:
        """Legacy alias → get_bars_last_update."""
        return self.get_bars_last_update(period=period, adjust=adjust, symbols=codes)

    def upsert_stock_zh_a_hist(self, data: Dict[str, Any], run_id: Optional[int | str] = None) -> bool:
        """Legacy alias → upsert_bars. Converts old meta format."""
        meta = data.get("meta", {})
        bars_raw = data.get("data", [])
        return self.upsert_bars(
            period=meta.get("period", "daily"),
            adjust=meta.get("adjust", ADJUST_NONE),
            source=meta.get("source", ""),
            bars=bars_raw,
            run_id=run_id,
        )

    def upsert_market_categories(self, categories: List[Dict[str, Any]], data_source: str, taxonomy: str = "", market: str = "zh_a", run_id: Optional[int | str] = None) -> bool:
        """Legacy alias → upsert_taxonomy_categories."""
        return self.upsert_taxonomy_categories(categories, source=data_source, taxonomy=taxonomy, market=market, run_id=run_id)

    def upsert_industry_constituents(self, constituents: List[Dict[str, Any]], data_source: str, taxonomy: str = "", market: str = "zh_a", run_id: Optional[int | str] = None) -> bool:
        """Upsert industry index constituents via v2 API."""
        path = f"/api/v2/taxonomy/{data_source}/{taxonomy}/{market}/industry-constituents/upsert"
        try:
            resp = self.post(path, constituents)
            ok = 200 <= resp.status_code < 300
            if not ok and self.logger:
                self.logger.warning({
                    'event': 'phoenixA_upsert_industry_constituents_failure',
                    'run_id': run_id,
                    'source': data_source,
                    'status': resp.status_code,
                    'body_snippet': resp.text[:120],
                    'count': len(constituents) if constituents else 0,
                })
            return ok
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_upsert_industry_constituents_exception',
                    'run_id': run_id,
                    'source': data_source,
                    'error': str(e),
                })
            raise

    def upsert_industry_weights(self, weights: List[Dict[str, Any]], data_source: str, taxonomy: str = "", market: str = "zh_a", run_id: Optional[int | str] = None) -> bool:
        """Upsert industry index constituent daily weights via v2 API."""
        path = f"/api/v2/taxonomy/{data_source}/{taxonomy}/{market}/industry-weights/upsert"
        try:
            resp = self.post(path, weights)
            ok = 200 <= resp.status_code < 300
            if not ok and self.logger:
                self.logger.warning({
                    'event': 'phoenixA_upsert_industry_weights_failure',
                    'run_id': run_id,
                    'source': data_source,
                    'status': resp.status_code,
                    'body_snippet': resp.text[:120],
                    'count': len(weights) if weights else 0,
                })
            return ok
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_upsert_industry_weights_exception',
                    'run_id': run_id,
                    'source': data_source,
                    'error': str(e),
                })
            raise

    def upsert_industry_daily(self, bars: List[Dict[str, Any]], data_source: str, taxonomy: str = "", market: str = "zh_a", run_id: Optional[int | str] = None) -> bool:
        """Upsert industry index daily bars via v2 API."""
        path = f"/api/v2/taxonomy/{data_source}/{taxonomy}/{market}/industry-daily/upsert"
        try:
            resp = self.post(path, bars)
            ok = 200 <= resp.status_code < 300
            if not ok and self.logger:
                self.logger.warning({
                    'event': 'phoenixA_upsert_industry_daily_failure',
                    'run_id': run_id,
                    'source': data_source,
                    'status': resp.status_code,
                    'body_snippet': resp.text[:120],
                    'count': len(bars) if bars else 0,
                })
            return ok
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_upsert_industry_daily_exception',
                    'run_id': run_id,
                    'source': data_source,
                    'error': str(e),
                })
            raise

    # ──────────── Financial Statements (v2) ────────────

    def upsert_financial_statements(
        self,
        statements: List[Dict[str, Any]],
        data_source: str,
        statement_type: str,
        run_id: Optional[int | str] = None,
    ) -> bool:
        """Upsert financial statements via v2 API."""
        path = f"/api/v2/financial/{data_source}/{statement_type}/upsert"
        try:
            resp = self.post(path, statements)
            ok = 200 <= resp.status_code < 300
            if not ok and self.logger:
                self.logger.warning({
                    'event': 'phoenixA_upsert_financial_statements_failure',
                    'run_id': run_id,
                    'source': data_source,
                    'statement_type': statement_type,
                    'status': resp.status_code,
                    'body_snippet': resp.text[:120],
                    'count': len(statements) if statements else 0,
                })
            return ok
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_upsert_financial_statements_exception',
                    'run_id': run_id,
                    'source': data_source,
                    'statement_type': statement_type,
                    'error': str(e),
                })
            raise

    def query_financial_statements(
        self,
        *,
        source: str,
        statement_type: str,
        symbol: str = "",
        symbols: Optional[List[str]] = None,
        market: str = "",
        period_start: str = "",
        period_end: str = "",
        ann_date_before: str = "",
        reporting_period: str = "",
        reporting_periods: Optional[List[str]] = None,
        report_type: str = "",
        statement_code: str = "",
        comp_type_code: Optional[int] = None,
        fields: Optional[List[str]] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Query financial statements via v2 API.

        Mirrors PhoenixA controller query params:
        `symbol`, `symbols`, `market`, `period_start`, `period_end`, `ann_date_before`,
        `reporting_period`, `reporting_periods`, `report_type`, `statement_code`, `comp_type_code`,
        `fields`, `page`, and `page_size`.
        """
        path = f"/api/v2/financial/{source}/{statement_type}"
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if symbol:
            params["symbol"] = symbol
        if symbols:
            params["symbols"] = ",".join([str(s) for s in symbols if str(s).strip()])
        if market:
            params["market"] = market
        if period_start:
            params["period_start"] = period_start
        if period_end:
            params["period_end"] = period_end
        if ann_date_before:
            params["ann_date_before"] = ann_date_before
        if reporting_period:
            params["reporting_period"] = reporting_period
        if reporting_periods:
            params["reporting_periods"] = ",".join(reporting_periods)
        if report_type:
            params["report_type"] = report_type
        if statement_code:
            params["statement_code"] = statement_code
        if comp_type_code is not None:
            params["comp_type_code"] = str(comp_type_code)
        if fields:
            params["fields"] = ",".join([str(f) for f in fields if str(f).strip()])
        try:
            resp = self.get(path, params)
            if 200 <= resp.status_code < 300:
                return resp.json()
            return {"data": [], "total": 0}
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_query_financial_statements_failed',
                    'source': source,
                    'statement_type': statement_type,
                    'error': str(e),
                })
            return {"data": [], "total": 0}

    # ──────────── Corporate Actions (v2) ────────────

    def upsert_corporate_actions(
        self,
        actions: List[Dict[str, Any]],
        data_source: str,
        action_type: str,
        run_id: Optional[int | str] = None,
    ) -> bool:
        """Upsert corporate actions via v2 API."""
        path = f"/api/v2/corporate-action/{data_source}/{action_type}/upsert"
        try:
            resp = self.post(path, actions)
            ok = 200 <= resp.status_code < 300
            if not ok and self.logger:
                self.logger.warning({
                    'event': 'phoenixA_upsert_corporate_actions_failure',
                    'run_id': run_id,
                    'source': data_source,
                    'action_type': action_type,
                    'status': resp.status_code,
                    'body_snippet': resp.text[:120],
                    'count': len(actions) if actions else 0,
                })
            return ok
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_upsert_corporate_actions_exception',
                    'run_id': run_id,
                    'source': data_source,
                    'action_type': action_type,
                    'error': str(e),
                })
            raise

    def query_corporate_actions(
        self,
        *,
        source: str,
        action_type: str,
        symbol: str = "",
        symbols: Optional[List[str]] = None,
        period_start: str = "",
        period_end: str = "",
        report_period: str = "",
        ann_date_before: str = "",
        progress_code: str = "",
        fields: Optional[List[str]] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Query corporate actions via v2 API."""
        path = f"/api/v2/corporate-action/{source}/{action_type}"
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if symbol:
            params["symbol"] = symbol
        if symbols:
            params["symbols"] = ",".join([str(s) for s in symbols if str(s).strip()])
        if period_start:
            params["period_start"] = period_start
        if period_end:
            params["period_end"] = period_end
        if report_period:
            params["report_period"] = report_period
        if ann_date_before:
            params["ann_date_before"] = ann_date_before
        if progress_code:
            params["progress_code"] = progress_code
        if fields:
            params["fields"] = ",".join([str(f) for f in fields if str(f).strip()])
        try:
            resp = self.get(path, params)
            if 200 <= resp.status_code < 300:
                return resp.json()
            return {"data": [], "total": 0}
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_query_corporate_actions_failed',
                    'source': source,
                    'action_type': action_type,
                    'error': str(e),
                })
            return {"data": [], "total": 0}

    # ──────────── Adjust Factors (v2) ────────────

    def upsert_adjust_factors(
        self,
        factors: List[Dict[str, Any]],
        data_source: str,
        run_id: Optional[int | str] = None,
    ) -> bool:
        """Upsert adjust factor rows via v2 API."""
        path = f"/api/v2/adjust-factors/{data_source}/upsert"
        try:
            resp = self.post(path, factors)
            ok = 200 <= resp.status_code < 300
            if not ok and self.logger:
                self.logger.warning({
                    'event': 'phoenixA_upsert_adjust_factors_failure',
                    'run_id': run_id,
                    'source': data_source,
                    'status': resp.status_code,
                    'body_snippet': resp.text[:120],
                    'count': len(factors) if factors else 0,
                })
            return ok
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_upsert_adjust_factors_exception',
                    'run_id': run_id,
                    'source': data_source,
                    'error': str(e),
                })
            raise

    def query_adjust_factors(
        self,
        *,
        source: str,
        symbol: str = "",
        symbols: Optional[List[str]] = None,
        market: str = "",
        start_date: str = "",
        end_date: str = "",
        fields: Optional[List[str]] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Query adjust factor rows via v2 API."""
        path = f"/api/v2/adjust-factors/{source}"
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if symbol:
            params["symbol"] = symbol
        if symbols:
            params["symbols"] = ",".join([str(s) for s in symbols if str(s).strip()])
        if market:
            params["market"] = market
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if fields:
            params["fields"] = ",".join([str(f) for f in fields if str(f).strip()])
        try:
            resp = self.get(path, params)
            if 200 <= resp.status_code < 300:
                return resp.json()
            return {"data": [], "total": 0}
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_query_adjust_factors_failed',
                    'source': source,
                    'error': str(e),
                })
            return {"data": [], "total": 0}

    # ──────────── Long Hu Bang (v2) ────────────

    def upsert_long_hu_bang(
        self,
        rows: List[Dict[str, Any]],
        data_source: str,
        run_id: Optional[int | str] = None,
    ) -> bool:
        """Upsert long hu bang rows via v2 API."""
        path = f"/api/v2/long-hu-bang/{data_source}/upsert"
        try:
            resp = self.post(path, rows)
            ok = 200 <= resp.status_code < 300
            if not ok and self.logger:
                self.logger.warning({
                    'event': 'phoenixA_upsert_long_hu_bang_failure',
                    'run_id': run_id,
                    'source': data_source,
                    'status': resp.status_code,
                    'body_snippet': resp.text[:120],
                    'count': len(rows) if rows else 0,
                })
            return ok
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_upsert_long_hu_bang_exception',
                    'run_id': run_id,
                    'source': data_source,
                    'error': str(e),
                })
            raise

    def query_long_hu_bang(
        self,
        *,
        source: str,
        symbol: str = "",
        symbols: Optional[List[str]] = None,
        market: str = "",
        trade_date: str = "",
        start_date: str = "",
        end_date: str = "",
        reason_type: str = "",
        trader_name: str = "",
        flow_mark: Optional[int] = None,
        fields: Optional[List[str]] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Query long hu bang rows via v2 API."""
        path = f"/api/v2/long-hu-bang/{source}"
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if symbol:
            params["symbol"] = symbol
        if symbols:
            params["symbols"] = ",".join([str(s) for s in symbols if str(s).strip()])
        if market:
            params["market"] = market
        if trade_date:
            params["trade_date"] = trade_date
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if reason_type:
            params["reason_type"] = reason_type
        if trader_name:
            params["trader_name"] = trader_name
        if flow_mark is not None:
            params["flow_mark"] = str(flow_mark)
        if fields:
            params["fields"] = ",".join([str(f) for f in fields if str(f).strip()])
        try:
            resp = self.get(path, params)
            if 200 <= resp.status_code < 300:
                return resp.json()
            return {"data": [], "total": 0}
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_query_long_hu_bang_failed',
                    'source': source,
                    'error': str(e),
                })
            return {"data": [], "total": 0}

    def query_industry_daily(
        self,
        *,
        source: str,
        taxonomy: str = "",
        market: str = "zh_a",
        index_code: str,
        start_date: str = "",
        end_date: str = "",
        limit: int = 5000,
    ) -> List[Dict[str, Any]]:
        """Query industry index daily bars via v2 API."""
        path = f"/api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-daily"
        params: Dict[str, Any] = {"index_code": index_code}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if limit:
            params["limit"] = limit
        try:
            resp = self.get(path, params)
            if 200 <= resp.status_code < 300:
                data = resp.json()
                return data.get("data", [])
            return []
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_query_industry_daily_failed',
                    'index_code': index_code,
                    'error': str(e),
                })
            return []

    def query_industry_categories(
        self,
        *,
        source: str,
        taxonomy: str = "",
        market: str = "zh_a",
        level: Optional[int] = None,
        parent_code: Optional[str] = None,
        name: Optional[str] = None,
        page: int = 1,
        page_size: int = 500,
    ) -> Dict[str, Any]:
        """Query industry taxonomy categories via v2 API."""
        path = f"/api/v2/taxonomy/{source}/{taxonomy}/{market}/categories"
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if level is not None:
            params["level"] = level
        if parent_code is not None:
            params["parent_code"] = parent_code
        if name:
            params["name"] = name
        try:
            resp = self.get(path, params)
            if 200 <= resp.status_code < 300:
                return resp.json()
            return {"list": [], "total": 0}
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_query_industry_categories_failed',
                    'source': source,
                    'error': str(e),
                })
            return {"list": [], "total": 0}

    def query_industry_constituents_by_index(
        self,
        *,
        source: str,
        taxonomy: str = "",
        market: str = "zh_a",
        index_code: str,
        page: int = 1,
        page_size: int = 500,
    ) -> Dict[str, Any]:
        """Query industry constituents by index code via v2 API."""
        path = f"/api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-constituents/by_index/{index_code}"
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        try:
            resp = self.get(path, params)
            if 200 <= resp.status_code < 300:
                return resp.json()
            return {"list": [], "count": 0}
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_query_constituents_by_index_failed',
                    'index_code': index_code,
                    'error': str(e),
                })
            return {"list": [], "count": 0}

    def query_industry_constituents_by_stock(
        self,
        *,
        source: str,
        taxonomy: str = "",
        market: str = "zh_a",
        con_code: str,
    ) -> List[Dict[str, Any]]:
        """Query industry memberships for a stock via v2 API."""
        path = f"/api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-constituents/by_stock/{con_code}"
        try:
            resp = self.get(path, {})
            if 200 <= resp.status_code < 300:
                return resp.json()
            return []
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_query_constituents_by_stock_failed',
                    'con_code': con_code,
                    'error': str(e),
                })
            return []

    # ──────────── Taxonomy Mappings (for factor engine) ────────────

    def get_taxonomy_by_security(self, symbol: str) -> List[Dict[str, Any]]:
        """Query all taxonomy mappings for a security via v2 API.

        Returns list of TaxonomySecurityMap entries with fields:
        - source, taxonomy, category_code, category_name, level, parent_code, index_code, symbol, asset_type, market
        - Standardized hierarchy fields exposed by PhoenixA:
          canonical_source, canonical_taxonomy, canonical_level,
          canonical_category_code, canonical_category_name, canonical_parent_code,
          canonical_index_code, derived_flags

        Factor engine should consume PhoenixA canonical/derived fields directly.
        """
        path = f"/api/v2/taxonomy/by_security/{symbol}"
        try:
            resp = self.get(path, {})
            if 200 <= resp.status_code < 300:
                data = resp.json()
                if isinstance(data, list):
                    return data
                return []
            return []
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_get_taxonomy_by_security_failed',
                    'symbol': symbol,
                    'error': str(e),
                })
            return []

    def get_catalog_capabilities(self, *, refresh: bool = False) -> Dict[str, Any]:
        """Query PhoenixA catalog capabilities for factor-availability analysis."""
        path = "/api/v2/catalog/capabilities"
        params: Dict[str, Any] = {}
        if refresh:
            params["refresh"] = "true"
        try:
            resp = self.get(path, params)
            if 200 <= resp.status_code < 300:
                data = resp.json()
                if isinstance(data, dict):
                    data.setdefault("_reachable", True)
                    return data
            return {"capabilities": [], "_reachable": False, "_status_code": resp.status_code}
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_get_catalog_capabilities_failed',
                    'error': str(e),
                })
            return {"capabilities": [], "_reachable": False, "_error": str(e)}

