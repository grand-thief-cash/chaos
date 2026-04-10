from typing import Dict, Any, List, Optional

import requests

from artemis.core.clients.dept_clients import HTTPDeptServiceClient


class PhoenixAClient(HTTPDeptServiceClient):
    """
    Client for interacting with PhoenixA service.
    Inherits HTTPDeptServiceClient for OTEL traceparent injection + connection pooling.
    """

    def stock_zh_a_list_batch_upsert(self, payload: List[Dict[str, Any]], run_id: Optional[int | str] = None) -> bool:
        path = "/api/v1/stock/list/batch_upsert"
        try:
            resp = self.post(path, payload)
            ok = 200 <= resp.status_code < 300
            if not ok and self.logger:
                self.logger.warning({
                    'event': 'phoenixA_batch_upsert_failure',
                    'run_id': run_id,
                    'path': path,
                    'status': resp.status_code,
                    'body_snippet': resp.text[:120],
                })
            return ok
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_batch_upsert_exception',
                    'run_id': run_id,
                    'path': path,
                    'error': str(e),
                })
            raise

    def get_stock_zh_a_codes(self, codes: Optional[List[str]] = None, exchanges: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        path = "/api/v1/stock/list/listFiltered"
        params: Dict[str, Any] = {"limit": "20000"}
        result: Dict[str, Dict[str, Any]] = {}
        if codes:
            params["code_list"] = ",".join([str(c) for c in codes if str(c).strip()])
        if exchanges:
            params["exchange"] = ",".join([str(e).strip().upper() for e in exchanges if str(e).strip()])
        try:
            resp = self.get(path, params)
            if 200 <= resp.status_code < 300:
                data = resp.json()
                rows = data.get("data") or data.get("list") or []
                for item in rows:
                    if isinstance(item, dict) and "code" in item:
                        code = str(item["code"])
                        result[code] = {
                            "code": code,
                            "exchange": str(item.get("exchange", "")).upper(),
                        }
                return result
            return result
        except Exception as e:
            if self.logger:
                self.logger.error({'event': 'phoenixA_get_all_codes_failed', 'error': str(e)})
            return {}

    def get_stock_zh_a_last_updates(self, period: str, adjust: str, codes: Optional[List[str]] = None) -> Dict[str, str]:
        path = "/api/v1/stock/hist/last_update"
        params: Dict[str, Any] = {"period": period, "adjust": adjust}
        if codes:
            params["codes"] = ",".join([str(c) for c in codes if str(c).strip()])

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
                    'event': 'phoenixA_get_last_updates_failed',
                    'frequency': period,
                    'adjust': adjust,
                    'code_list_size': len(codes) if codes else 0,
                    'error': str(e),
                })
            return {}

    def upsert_stock_zh_a_hist(self, data: Dict[str, Any], run_id: Optional[int | str] = None) -> bool:
        path = "/api/v1/stock/hist/upsert"
        try:
            resp = self.post(path, data)
            ok = 200 <= resp.status_code < 300
            if not ok and self.logger:
                self.logger.error({
                    'event': 'phoenixA_save_hist_data_failed',
                    'run_id': run_id,
                    'status': resp.status_code,
                    'data_meta': data.get("meta", {}),
                    'data_size': len(data.get("data", [])),
                    'body_snippet': resp.text[:120],
                })
            return ok
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_save_hist_data_exception',
                    'run_id': run_id,
                    'data_meta': data.get("meta", {}),
                    'data_size': len(data.get("data", [])),
                    'error': str(e),
                })
            raise

    def upsert_market_categories(self, categories: List[Dict[str, Any]], data_source: str, run_id: Optional[int | str] = None) -> bool:
        path = f"/api/v1/market_category/upsert/{data_source}"
        try:
            resp = requests.post(self.base_url + path, json=categories)
            ok = 200 <= resp.status_code < 300
            if not ok and self.logger:
                self.logger.warning({
                    'event': 'phoenixA_upsert_market_category_failure',
                    'run_id': run_id,
                    'path': path,
                    'status': resp.status_code,
                    'body_snippet': resp.text[:120],
                    'list_size': len(categories) if categories is not None else 0,
                })
            return ok
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_upsert_market_category_exception',
                    'run_id': run_id,
                    'path': path,
                    'error': str(e),
                    'list_size': len(categories) if categories is not None else 0,
                })
            raise

    def get_strategy_market_bars(
        self,
        *,
        symbol: str,
        start_date: str,
        end_date: str,
        timeframe: str = "daily",
        adjust: str = "nf",
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        path = "/api/v1/stock/hist/get_data"
        request_fields = fields or [
            "date",
            "code",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
        ]
        params = {
            "code": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "period": timeframe,
            "adjust": adjust,
            "fields": ",".join(request_fields),
            "limit": 5000,
            "offset": 0,
        }
        try:
            resp = self.get(path, params=params)
            if not (200 <= resp.status_code < 300):
                if self.logger:
                    self.logger.error({
                        'event': 'phoenixA_get_strategy_market_bars_failed',
                        'path': path,
                        'status': resp.status_code,
                        'symbol': symbol,
                        'timeframe': timeframe,
                        'body_snippet': resp.text[:120],
                    })
                return []
            payload = resp.json()
            rows = payload.get("data") if isinstance(payload, dict) else payload
            if not isinstance(rows, list):
                return []
            return [row for row in rows if isinstance(row, dict)]
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_get_strategy_market_bars_exception',
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'error': str(e),
                })
            raise

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
                    'path': path,
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
                    'path': path,
                    'status': resp.status_code,
                    'artifact_count': len(payload),
                    'body_snippet': resp.text[:120],
                })
            return ok
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_save_strategy_run_artifacts_exception',
                    'run_id': run_id,
                    'path': path,
                    'artifact_count': len(payload),
                    'error': str(e),
                })
            raise
