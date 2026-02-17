import abc
import threading
import time
from datetime import datetime
from typing import Any, Dict

from artemis.log.logger import get_logger

logger = get_logger("sdk.base")

class BaseSDK(abc.ABC):
    """
    Abstract base class for all SDKs.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abc.abstractmethod
    def health_check(self) -> bool:
        """Check if the SDK is healthy/usable."""
        pass

    @abc.abstractmethod
    def get_client(self) -> Any:
        """Get the client instance."""
        pass

class StatelessSDK(BaseSDK):
    """
    For SDKs that don't require login/logout or state maintenance (e.g. Akshare).
    """
    def health_check(self) -> bool:
        return True


class StatefulSDK(BaseSDK):
    """
    For SDKs that require login/logout and session management.
    Implements idle timeout and auto-logout.
    """
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._lock = threading.RLock()
        self._last_used_at = datetime.now()
        self._is_connected = False

        # Default 5 minutes
        self._idle_timeout_seconds = config.get("idle_timeout", 300)

        # Start a background thread or relies on lazy checking?
        # A simple daemon thread is better for strictly enforcing timeout.
        self._stop_event = threading.Event()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True, name=f"{self.__class__.__name__}-Monitor")
        self._monitor_thread.start()

    @abc.abstractmethod
    def _login(self):
        """Perform actual login logic."""
        pass

    @abc.abstractmethod
    def _logout(self):
        """Perform actual logout logic."""
        pass

    def connect(self):
        """Ensure connected. Resets idle timer."""
        with self._lock:
            self._last_used_at = datetime.now()
            if not self._is_connected:
                logger.info(f"Connecting {self.__class__.__name__}...")
                try:
                    self._login()
                    self._is_connected = True
                    logger.info(f"{self.__class__.__name__} connected.")
                except Exception as e:
                    logger.error(f"Failed to connect {self.__class__.__name__}: {e}")
                    raise

    def disconnect(self):
        """Force disconnect."""
        with self._lock:
            if self._is_connected:
                logger.info(f"Disconnecting {self.__class__.__name__}...")
                try:
                    self._logout()
                except Exception as e:
                    logger.error(f"Error disconnecting {self.__class__.__name__}: {e}")
                finally:
                    self._is_connected = False

    def get_client(self) -> Any:
        """
        Get the client object.
        Hooks into the lifecycle to ensure connection is active and updates usage time.
        """
        self.connect()
        return self

    def _monitor_loop(self):
        """Background loop to check for idle timeout."""
        while not self._stop_event.is_set():
            time.sleep(10) # Check every 10 seconds
            with self._lock:
                if self._is_connected:
                    idle_duration = (datetime.now() - self._last_used_at).total_seconds()
                    if idle_duration > self._idle_timeout_seconds:
                        logger.info(f"{self.__class__.__name__} idle for {idle_duration}s. Auto disconnecting.")
                        self.disconnect()

    def health_check(self) -> bool:
        with self._lock:
            return self._is_connected
