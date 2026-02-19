from typing import Dict, Any, List, Optional

from artemis.core.clients.dept_clients import HTTPDeptServiceClient


class PhoenixAClient(HTTPDeptServiceClient):
    """
    Client for interacting with PhoenixA service.
    Inherits HTTPDeptServiceClient for OTEL traceparent injection + connection pooling.
    """

    def batch_upsert(self, payload: List[Dict[str, Any]], run_id: Optional[int] = None) -> bool:
        """
        Call POST /api/v1/stock/list/batch_upsert
        """
        path = "/api/v1/stock/list/batch_upsert"
        # router_all.go: r.Post("/batch_upsert", stockZhAListCtrl.BatchUpsert) under /api/v1/stock/list

        try:
            resp = self.post(path, payload)
            ok = 200 <= resp.status_code < 300
            if not ok and self.logger:
                 self.logger.warning({
                    'event': 'phoenixA_batch_upsert_failure',
                    'run_id': run_id,
                    'path': path,
                    'status': resp.status_code,
                    'body_snippet': resp.text[:120]
                })
            return ok
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_batch_upsert_exception',
                    'run_id': run_id,
                    'path': path,
                    'error': str(e)
                })
            raise e

    def get_stock_last_updates(self, frequency: str, adjust: str, codes: Optional[List[str]] = None) -> Dict[str, str]:
        """
        Call GET /api/v1/stock/hist/last_update
        Returns a map of code -> last_update_date (YYYY-MM-DD or empty)

        Optional:
            codes: list of raw_code (6-digit) to filter.
        """
        path = "/api/v1/stock/hist/last_update"
        params: Dict[str, Any] = {"frequency": frequency, "adjust": adjust}
        if codes:
            # Change: send comma separated string for code_list
            params["code_list"] = ",".join([str(c) for c in codes if str(c).strip()])

        try:
            resp = self.get(path, params)
            if 200 <= resp.status_code < 300:
                # Expecting Dict[str, str] from Go Controller
                data = resp.json()
                if isinstance(data, dict):
                    return data
            return {}
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_get_last_updates_failed',
                    'frequency': frequency,
                    'adjust': adjust,
                    'code_list_size': len(codes) if codes else 0,
                    'error': str(e)
                })
            return {}

    def save_stock_hist_data(self, data: List[Dict[str, Any]], frequency: str, adjust: str, run_id: Optional[int] = None) -> bool:
        """
        Call POST /api/v1/stock/hist/data
        """
        path = "/api/v1/stock/hist/data"
        payload = {"frequency": frequency, "adjust": adjust, "data": data}
        try:
            resp = self.post(path, payload)
            ok = 200 <= resp.status_code < 300
            if not ok and self.logger:
                 self.logger.error({
                    'event': 'phoenixA_save_hist_data_failed',
                    'run_id': run_id,
                    'frequency': frequency,
                    'adjust': adjust,
                    'status': resp.status_code,
                    'body_snippet': resp.text[:120]
                })
            return ok
        except Exception as e:
            if self.logger:
                self.logger.error({
                    'event': 'phoenixA_save_hist_data_exception',
                    'run_id': run_id,
                    'frequency': frequency,
                    'adjust': adjust,
                    'error': str(e)
                })
            raise e

    def get_all_stock_codes(self, codes: Optional[List[str]] = None) -> List[Dict[str, str]]:
        path = "/api/v1/stock/list/listFiltered"
        params: Dict[str, Any] = {"limit": "20000"}
        if codes:
            # Change: send comma separated string for code_list
            params["code_list"] = ",".join([str(c) for c in codes if str(c).strip()])
        try:
            resp = self.get(path, params)
            if 200 <= resp.status_code < 300:
                data = resp.json()
                rows = []
                if isinstance(data, list):
                    rows = data
                elif isinstance(data, dict):
                    rows = data.get("data") or data.get("list") or []

                result = []
                for item in rows:
                    if isinstance(item, dict) and "code" in item:
                        result.append({
                            "code": str(item["code"]),
                            "exchange": str(item.get("exchange", "")).upper()
                        })
                return result
            return []
        except Exception as e:
            if self.logger:
                self.logger.error({'event': 'phoenixA_get_all_codes_failed', 'error': str(e)})
            return []
