"""Independent TX Watchdog and Heartbeat Lease Supervisor.

Complies with Saha Risk Kataloğu v1.2 Sections 20, 36.5, 38.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, ClassVar

from src.core.logging import get_logger
from src.safety.estop import EStopTriggerSource

if TYPE_CHECKING:
    from src.safety.estop import EmergencyStopSystem
    from src.safety.state_machine import SafetySupervisor

logger = get_logger("safety.watchdog")


class TxWatchdogSupervisor:
    """Independent supervisor thread enforcing monotonic heartbeat leases for transmission."""

    DEFAULT_TIMEOUT_MS: ClassVar[float] = 800.0  # 800ms lease duration (B8: README-documented value)
    CHECK_INTERVAL_SEC: ClassVar[float] = 0.050  # 50ms check loop resolution

    def __init__(
        self,
        supervisor: SafetySupervisor,
        estop: EmergencyStopSystem | None = None,
        timeout_ms: float = DEFAULT_TIMEOUT_MS,
    ) -> None:
        self.supervisor = supervisor
        self.estop = estop
        self.timeout_sec = max(0.050, timeout_ms / 1000.0)

        self._last_heartbeat_time = time.monotonic()
        self._is_running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def heartbeat(self) -> None:
        """Refresh transmission authorization lease."""
        with self._lock:
            self._last_heartbeat_time = time.monotonic()

    @property
    def remaining_lease_sec(self) -> float:
        """Returns time in seconds until current lease expires."""
        with self._lock:
            elapsed = time.monotonic() - self._last_heartbeat_time
            return max(0.0, self.timeout_sec - elapsed)

    @property
    def is_lease_valid(self) -> bool:
        with self._lock:
            return (time.monotonic() - self._last_heartbeat_time) <= self.timeout_sec

    def start(self) -> None:
        """Start the watchdog monitor background thread."""
        with self._lock:
            if self._is_running:
                return
            self._is_running = True
            self._last_heartbeat_time = time.monotonic()
            self._thread = threading.Thread(
                target=self._monitor_loop,
                name="tx_watchdog_supervisor",
                daemon=True,
            )
            self._thread.start()
            logger.info(
                "TX Watchdog Supervisor started",
                extra={"timeout_ms": self.timeout_sec * 1000.0},
            )

    def stop(self) -> None:
        """Stop the watchdog monitor."""
        with self._lock:
            self._is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        logger.info("TX Watchdog Supervisor stopped")

    def _monitor_loop(self) -> None:
        """Continuous background check enforcing lease bounds."""
        while True:
            with self._lock:
                if not self._is_running:
                    break
                now = time.monotonic()
                elapsed = now - self._last_heartbeat_time

            # Only enforce watchdog if transmission is armed or active
            if self.supervisor.is_tx_permitted and elapsed > self.timeout_sec:
                logger.critical(
                    "TX Watchdog Lease Expired! Revoking all TX authorization.",
                    extra={"elapsed_ms": elapsed * 1000.0, "timeout_ms": self.timeout_sec * 1000.0},
                )
                # Revoke TX in state machine
                self.supervisor.trigger_fault(
                    f"WATCHDOG_TIMEOUT: Lease expired after {elapsed * 1000.0:.1f} ms without heartbeat",
                )
                # Engage hardware/software E-Stop if available
                if self.estop:
                    self.estop.trigger(
                        EStopTriggerSource.KEEPALIVE_TIMEOUT,
                        f"Watchdog lease expired ({elapsed * 1000.0:.1f}ms > {self.timeout_sec * 1000.0:.1f}ms)",
                    )

            time.sleep(self.CHECK_INTERVAL_SEC)
