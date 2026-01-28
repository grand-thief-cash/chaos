from typing import Dict, Any, List

from artemis.core.clients.dept_clients import HTTPDeptServiceClient


class PhoenixAClient(HTTPDeptServiceClient):
    """
    Client for interacting with PhoenixA service.
    Inherits HTTPDeptServiceClient for OTEL traceparent injection + connection pooling.
    """

    def batch_upsert(self, payload: List[Dict[str, Any]], run_id: int) -> bool:
        """
        Call POST /api/v1/zh/stock_list/batch_upsert
        """
        path = "/api/v1/zh/stock_list/batch_upsert"
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

