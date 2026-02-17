from typing import Any

import baostock as bs

from artemis.core.sdk.base import StatefulSDK
from artemis.log.logger import get_logger

logger = get_logger("sdk.baostock")

class BaostockSDK(StatefulSDK):
    def __init__(self, config):
        super().__init__(config)

    def _login(self):
        lg = bs.login()
        if lg.error_code != '0':
            msg = f"login failed: {lg.error_msg}"
            logger.error(msg)
            raise RuntimeError(msg)

    def _logout(self):
        bs.logout()

    def get_client(self) -> Any:
        self.connect() # Trigger connect/timer update explicitly or via super().get_client() but we don't need the return value
        return bs
