"""10-Trigger Hardware/Software Emergency Stop (E-Stop) Interlock System."""

from __future__ import annotations

import hashlib
import hmac
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from src.core.errors import SafetyError
from src.core.logging import get_logger

logger = get_logger("safety.estop")


class EStopTriggerSource(Enum):
    """10 Distinct E-Stop Triggers."""

    USER_UI_BUTTON = "USER_UI_BUTTON"
    BUS_OFF_DETECTED = "BUS_OFF_DETECTED"
    KEEPALIVE_TIMEOUT = "KEEPALIVE_TIMEOUT"
    SPEED_INTERLOCK_BREACH = "SPEED_INTERLOCK_BREACH"
    HARDWARE_DISCONNECT = "HARDWARE_DISCONNECT"
    RATE_LIMIT_OVERFLOW = "RATE_LIMIT_OVERFLOW"
    UNAUTHORIZED_PAYLOAD = "UNAUTHORIZED_PAYLOAD"
    TEMPERATURE_OVERHEAT = "TEMPERATURE_OVERHEAT"
    PROCESS_TERMINATION = "PROCESS_TERMINATION"
    COMMUNICATION_TIMEOUT = "COMMUNICATION_TIMEOUT"


@dataclass(slots=True)
class EStopEvent:
    """Recorded E-Stop engagement event."""

    trigger: EStopTriggerSource
    reason: str
    timestamp_ns: int
    system_speed_kmh: float = 0.0


class EmergencyStopSystem:
    """Master Emergency Stop controller ensuring immediate hardware/software TX cutoff."""

    def __init__(self, reset_secret: bytes | None = None) -> None:
        self.reset_secret = reset_secret or b"EMERGENCY_STOP_DEFAULT_HMAC_SECRET_2026"
        self._is_engaged = False
        self._last_event: EStopEvent | None = None
        self._callbacks: list[Callable[[EStopEvent], None]] = []
        self._reset_nonce: bytes = b""
        self._lock = threading.RLock()

    @property
    def is_engaged(self) -> bool:
        with self._lock:
            return self._is_engaged

    @property
    def last_event(self) -> EStopEvent | None:
        with self._lock:
            return self._last_event

    def get_reset_nonce(self) -> bytes:
        """Return the single-use cryptographic challenge nonce for the current E-Stop engagement."""
        with self._lock:
            return self._reset_nonce

    def compute_reset_token(self, nonce: bytes) -> str:
        """Compute expected HMAC-SHA256 token for a given challenge nonce."""
        if not nonce:
            return ""
        return hmac.new(self.reset_secret, nonce, hashlib.sha256).hexdigest()

    def register_callback(self, callback: Callable[[EStopEvent], None]) -> None:
        """Register listener to be invoked immediately upon E-Stop trigger."""
        with self._lock:
            self._callbacks.append(callback)

    def trigger(
        self,
        trigger: EStopTriggerSource,
        reason: str,
        vehicle_speed_kmh: float = 0.0,
    ) -> None:
        """Engage Emergency Stop immediately and cut all transmissions."""
        with self._lock:
            now_ns = time.time_ns()
            self._is_engaged = True
            self._reset_nonce = os.urandom(16)
            self._last_event = EStopEvent(
                trigger=trigger,
                reason=reason,
                timestamp_ns=now_ns,
                system_speed_kmh=vehicle_speed_kmh,
            )
            event_snapshot = self._last_event
            callbacks_snapshot = list(self._callbacks)

        logger.critical(
            "EMERGENCY STOP ENGAGED",
            extra={
                "trigger": trigger.value,
                "reason": reason,
                "speed_kmh": vehicle_speed_kmh,
            },
        )

        # Notify all listeners (hardware buses, UI, timers) outside lock
        for cb in callbacks_snapshot:
            try:
                cb(event_snapshot)
            except Exception as exc:
                logger.error("Error in E-Stop callback", extra={"error": str(exc)})

    def reset(self, authorization_token: str) -> None:
        """Manual reset of E-Stop requires valid challenge-response HMAC token."""
        with self._lock:
            if not self._is_engaged:
                return  # No-op when not engaged

            if not self._reset_nonce:
                return

            expected_token = self.compute_reset_token(self._reset_nonce)
            if not hmac.compare_digest(authorization_token, expected_token):
                raise SafetyError("Invalid E-Stop reset token", code="ESTOP_RESET_DENIED")

            self._is_engaged = False
            self._last_event = None
            self._reset_nonce = b""
            logger.warning("Emergency Stop reset by operator")
