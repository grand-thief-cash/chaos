from typing import Any

import AmazingData as ad

from artemis.core.sdk.base import StatefulSDK
from artemis.log.logger import get_logger

logger = get_logger("sdk.amazing_data")

class AmazingDataSDK(StatefulSDK):
    def __init__(self, config):
        super().__init__(config)
        self.base_data = None

    def _login(self):
        host = self.config.get("host")
        port = self.config.get("port")
        user = self.config.get("username")
        password = self.config.get("password")
        
        try:
            # Step 1: Login using module level function
            ad.login(username=user, password=password, host=host, port=port)

            # Step 2: Instantiate data query class
            self.base_data = ad.BaseData()

            logger.info(f"AmazingData login successful for user: {user}")
        except Exception as e:
            logger.error(f"AmazingData login failed: {e}")
            raise

    def _logout(self):
        # AmazingData example doesn't show explicit logout, but we clear our instance
        self.base_data = None
        ad.logout(self.config.get("username"))

    def get_client(self) -> Any:
        # Returns the BaseData object ready for queries
        self.connect()
        return self.base_data
