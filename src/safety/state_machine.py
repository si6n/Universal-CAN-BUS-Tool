"""Formal Safety State Machine enforcing Fail-Silent and Safe-by-Default Operation.

Complies with Saha Risk Kataloğu v1.2 Sections 4, 5, 6, 37, 38.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from enum import Enum
from typing import ClassVar

from src.core.errors import SafetyError
from src.core.logging import get_logger

logger = get_logger("safety.state_machine")


class SafetyState(str, Enum):
    """Formal Safety Operational States."""

    STARTUP = "STARTUP"  # System booting up, hardware initializing, TX strictly blocked
    SAFE = "SAFE"  # Initialization complete, bus offline or TX disconnected
    PASSIVE = "PASSIVE"  # Default mode: Listen-Only RX, zero transmissions allowed
    ARMED_TX = "ARMED_TX"  # Explicit operator authorization granted, policy checks verified
    ACTIVE = "ACTIVE"  # Active verified transmission in progress with live watchdog lease
    FAULT = "FAULT"  # Safety violation / Watchdog timeout / E-Stop; TX revoked, queue flushed


class SafetySupervisor:
    """Central Safety State Supervisor governing all transmission permissions."""

    ALLOWED_TRANSITIONS: ClassVar[dict[SafetyState, set[SafetyState]]] = {
        SafetyState.STARTUP: {SafetyState.SAFE, SafetyState.FAULT},
        SafetyState.SAFE: {SafetyState.PASSIVE, SafetyState.FAULT},
        SafetyState.PASSIVE: {SafetyState.ARMED_TX, SafetyState.SAFE, SafetyState.FAULT},
        SafetyState.ARMED_TX: {SafetyState.ACTIVE, SafetyState.PASSIVE, SafetyState.FAULT},
        SafetyState.ACTIVE: {SafetyState.ARMED_TX, SafetyState.PASSIVE, SafetyState.FAULT},
        SafetyState.FAULT: {
            SafetyState.PASSIVE,
            SafetyState.SAFE,
        },  # MUST NOT transition directly to ARMED_TX or ACTIVE
    }

    def __init__(self, initial_state: SafetyState = SafetyState.STARTUP) -> None:
        self._state = initial_state
        self._state_change_timestamp_ns = time.time_ns()
        self._lock = threading.RLock()
        self._callbacks: list[Callable[[SafetyState, SafetyState, str], None]] = []
        self._fault_reason: str = ""

    @property
    def current_state(self) -> SafetyState:
        with self._lock:
            return self._state

    @property
    def is_tx_permitted(self) -> bool:
        """TX is strictly prohibited unless in ARMED_TX or ACTIVE state."""
        with self._lock:
            return self._state in {SafetyState.ARMED_TX, SafetyState.ACTIVE}

    @property
    def is_passive(self) -> bool:
        with self._lock:
            return self._state == SafetyState.PASSIVE

    @property
    def is_fault(self) -> bool:
        with self._lock:
            return self._state == SafetyState.FAULT

    @property
    def fault_reason(self) -> str:
        with self._lock:
            return self._fault_reason

    def register_callback(self, callback: Callable[[SafetyState, SafetyState, str], None]) -> None:
        """Register listener for state change events (old_state, new_state, reason)."""
        with self._lock:
            self._callbacks.append(callback)

    def transition_to(self, new_state: SafetyState, reason: str = "") -> None:
        """Execute a formal validated state transition."""
        with self._lock:
            if self._state == new_state:
                return

            allowed = self.ALLOWED_TRANSITIONS.get(self._state, set())
            if new_state not in allowed:
                err_msg = (
                    f"Illegal Safety State transition from '{self._state.value}' to '{new_state.value}'. "
                    f"Reason: {reason or 'N/A'}"
                )
                logger.critical(err_msg)
                # Any illegal transition forces immediate FAULT state
                self._force_fault("ILLEGAL_STATE_TRANSITION: " + err_msg)
                raise SafetyError(err_msg, code="ILLEGAL_SAFETY_TRANSITION")

            old_state = self._state
            self._state = new_state
            self._state_change_timestamp_ns = time.time_ns()

            if new_state == SafetyState.FAULT:
                self._fault_reason = reason
            elif old_state == SafetyState.FAULT and new_state in {SafetyState.PASSIVE, SafetyState.SAFE}:
                self._fault_reason = ""

            callbacks_snapshot = list(self._callbacks)

        logger.info(
            "Safety State Transition",
            extra={"from": old_state.value, "to": new_state.value, "reason": reason},
        )

        for cb in callbacks_snapshot:
            try:
                cb(old_state, new_state, reason)
            except Exception as exc:
                logger.error("Error in Safety State Machine callback", extra={"error": str(exc)})

    def enter_passive_mode(self, reason: str = "Operator entered PASSIVE listen-only mode") -> None:
        """Safely transition to PASSIVE (Listen-Only) mode."""
        self.transition_to(SafetyState.PASSIVE, reason=reason)

    def arm_tx(self, reason: str = "Operator explicitly ARMED TX pipeline") -> None:
        """Explicitly arm the TX pipeline."""
        self.transition_to(SafetyState.ARMED_TX, reason=reason)

    def activate_tx(self, reason: str = "TX active transmission ongoing") -> None:
        """Transition from ARMED_TX to ACTIVE."""
        self.transition_to(SafetyState.ACTIVE, reason=reason)

    def trigger_fault(self, reason: str = "Safety fault detected") -> None:
        """Trigger FAULT state, immediately revoking all TX authorization."""
        self.transition_to(SafetyState.FAULT, reason=reason)

    def _force_fault(self, reason: str) -> None:
        """Internal emergency transition to FAULT bypassing transition table."""
        old_state = self._state
        self._state = SafetyState.FAULT
        self._fault_reason = reason
        self._state_change_timestamp_ns = time.time_ns()
        callbacks_snapshot = list(self._callbacks)

        for cb in callbacks_snapshot:
            try:
                cb(old_state, SafetyState.FAULT, reason)
            except Exception as exc:
                logger.error("Error in Safety State Machine emergency callback", extra={"error": str(exc)})
