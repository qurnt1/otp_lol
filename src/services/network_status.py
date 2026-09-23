"""Check whether the external asset service required by the UI is reachable."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

import requests

from ..config.constants import URL_DD_VERSIONS
from ..domain.events import EventBroker

LOGGER = logging.getLogger("otp_lol.network")
CHECK_TTL_SECONDS = 5.0
CHECK_TIMEOUT_SECONDS = 3.0

Probe = Callable[[], tuple[bool, str | None]]


class NetworkStatusService:
    """Expose a cached, serialized Internet probe for the local API and UI."""

    def __init__(
        self,
        broker: EventBroker | None = None,
        *,
        probe: Probe | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._broker = broker
        self._probe = probe or self._probe_asset_origin
        self._clock = clock or time.monotonic
        self._lock = threading.RLock()
        self._checking = False
        self._state = "checking"
        self._checked_monotonic: float | None = None
        self._checked_at: float | None = None
        self._last_success_at: float | None = None
        self._reason: str | None = None

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "state": self._state,
                "online": self._state == "online",
                "checked_at": self._checked_at,
                "last_success_at": self._last_success_at,
                "reason": self._reason,
                "source": "ddragon",
            }

    def is_online(self) -> bool:
        with self._lock:
            return self._state == "online"

    def check(self, *, force: bool = False) -> dict[str, Any]:
        """Run one bounded probe unless a recent result is still valid."""
        now = self._clock()
        with self._lock:
            if (
                not force
                and self._checked_monotonic is not None
                and now - self._checked_monotonic < CHECK_TTL_SECONDS
            ):
                return self.status()
            if self._checking:
                return self.status()
            self._checking = True

        try:
            online, reason = self._probe()
        except Exception:
            LOGGER.exception("network_probe_failed")
            online, reason = False, "probe_error"

        with self._lock:
            previous_state = self._state
            self._state = "online" if online else "offline"
            self._checked_monotonic = self._clock()
            self._checked_at = time.time()
            if online:
                self._last_success_at = self._checked_at
            self._reason = reason
            self._checking = False
            result = self.status()

        if previous_state != result["state"]:
            LOGGER.info(
                "network_status before=%s after=%s reason=%s",
                previous_state,
                result["state"],
                reason,
            )
            if self._broker is not None:
                self._broker.publish("network_status", result)
        return result

    @staticmethod
    def _probe_asset_origin() -> tuple[bool, str | None]:
        """Validate the JSON response used to discover the app's asset version."""
        try:
            response = requests.get(
                URL_DD_VERSIONS,
                headers={"User-Agent": "OTP-LOL network check"},
                timeout=CHECK_TIMEOUT_SECONDS,
            )
            if response.status_code != 200:
                return False, f"http_{response.status_code}"
            payload = response.json()
            if not isinstance(payload, list) or not payload:
                return False, "invalid_response"
            return True, None
        except requests.Timeout:
            return False, "timeout"
        except requests.RequestException:
            return False, "request_error"
        except (TypeError, ValueError):
            return False, "invalid_response"


__all__ = ["CHECK_TIMEOUT_SECONDS", "CHECK_TTL_SECONDS", "NetworkStatusService"]
