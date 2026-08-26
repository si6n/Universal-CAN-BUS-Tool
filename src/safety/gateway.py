"""Dual-Confirmation TX Safety Gateway enforcing CORE_SAFETY_FLOOR and Speed Interlocks.

Matches MASTER_PLAN.md Section 7 and Saha Risk Kataloğu v1.2 Sections 4, 19, 20.
"""

from __future__ import annotations

import collections
import threading
import time
from typing import TYPE_CHECKING, ClassVar

from src.core.errors import SafetyError
from src.core.logging import get_logger
from src.core.models.can_frame import CanFrame
from src.safety.estop import EmergencyStopSystem, EStopTriggerSource

if TYPE_CHECKING:
    from src.hal.base import AbstractBus
    from src.safety.state_machine import SafetySupervisor
    from src.safety.watchdog import TxWatchdogSupervisor

logger = get_logger("safety.gateway")


class TxSafetyGateway:
    """Security and Safety Gateway filtering all outgoing CAN transmissions."""

    MAX_TX_RATE_PER_SEC: ClassVar[int] = 100  # Max 100 msg/s to prevent bus starvation
    SPEED_NOISE_THRESHOLD_KMH: ClassVar[float] = 0.5  # Permitted sensor jitter / noise threshold

    def __init__(
        self,
        bus: AbstractBus,
        estop: EmergencyStopSystem | None = None,
        supervisor: SafetySupervisor | None = None,
        watchdog: TxWatchdogSupervisor | None = None,
        whitelist_ids: set[int] | None = None,
    ) -> None:
        self.bus = bus
        self.estop = estop or EmergencyStopSystem()
        self.supervisor = supervisor
        self.watchdog = watchdog
        self.whitelist_ids = whitelist_ids or set()
        self._tx_timestamps: collections.deque[float] = collections.deque()
        self._current_vehicle_speed_kmh: float = 0.0
        self._lock = threading.RLock()

        # Wire E-stop callback to halt bus TX and trigger fault state
        self.estop.register_callback(self._on_estop_triggered)

        if self.supervisor:
            self.supervisor.register_callback(self._on_safety_state_changed)

    def _on_estop_triggered(self, event: object) -> None:
        logger.warning("TX Gateway notified of E-Stop engagement. All TX halted.")
        if self.supervisor and not self.supervisor.is_fault:
            self.supervisor.trigger_fault("E-Stop engagement triggered from hardware/software event")
        with self._lock:
            self._tx_timestamps.clear()

    def _on_safety_state_changed(self, old_state: object, new_state: object, reason: str) -> None:
        if getattr(new_state, "value", str(new_state)) == "FAULT":
            with self._lock:
                self._tx_timestamps.clear()

    def update_vehicle_speed(self, speed_kmh: float) -> None:
        """Update live vehicle speed for dynamic interlock enforcement."""
        with self._lock:
            self._current_vehicle_speed_kmh = max(0.0, speed_kmh)

    def validate_and_transmit(
        self,
        frame: CanFrame,
        is_critical_command: bool = False,
        user_confirmed: bool = False,
    ) -> bool:
        """Enforce CORE_SAFETY_FLOOR before passing frame to HAL."""
        with self._lock:
            # Rule 0: Safety State Machine Check (if supervisor attached)
            if self.supervisor is not None and not self.supervisor.is_tx_permitted:
                raise SafetyError(
                    f"Transmission blocked: Safety State is '{self.supervisor.current_state.value}' (TX not permitted)",
                    code="SAFETY_STATE_BLOCKED",
                )

            # Rule 0.5: TX Watchdog Lease Check (if watchdog attached)
            if self.watchdog is not None and not self.watchdog.is_lease_valid:
                raise SafetyError(
                    "Transmission blocked: Watchdog lease has expired",
                    code="WATCHDOG_LEASE_EXPIRED",
                )

            # Rule 1: Emergency Stop Check
            if self.estop.is_engaged:
                raise SafetyError(
                    "Transmission blocked: Emergency Stop is currently ENGAGED",
                    code="ESTOP_ACTIVE",
                )

            # Rule 2: Whitelist Filter Check
            if self.whitelist_ids and frame.arbitration_id not in self.whitelist_ids:
                logger.warning(
                    "TX Frame rejected by Whitelist filter",
                    extra={"arbitration_id": hex(frame.arbitration_id)},
                )
                self.estop.trigger(
                    EStopTriggerSource.UNAUTHORIZED_PAYLOAD,
                    f"Attempted TX to non-whitelisted ID: 0x{frame.arbitration_id:08X}",
                )
                raise SafetyError(
                    f"Transmission blocked: ID 0x{frame.arbitration_id:08X} not in whitelist",
                    code="WHITELIST_VIOLATION",
                )

            # Rule 4: Dual Confirmation Check (checked before speed interlock)
            if is_critical_command and not user_confirmed:
                raise SafetyError(
                    "Critical command rejected: Operator dual-confirmation missing",
                    code="CONFIRMATION_REQUIRED",
                )

            # Rule 3: Speed Interlock Check (Speed > SPEED_NOISE_THRESHOLD_KMH blocks critical commands / routines)
            if is_critical_command and self._current_vehicle_speed_kmh > self.SPEED_NOISE_THRESHOLD_KMH:
                logger.critical(
                    "Speed interlock triggered on critical command",
                    extra={"speed": self._current_vehicle_speed_kmh},
                )
                self.estop.trigger(
                    EStopTriggerSource.SPEED_INTERLOCK_BREACH,
                    f"Critical command attempted while moving ({self._current_vehicle_speed_kmh} km/h)",
                    vehicle_speed_kmh=self._current_vehicle_speed_kmh,
                )
                raise SafetyError(
                    f"Safety Interlock: Critical command blocked while vehicle is moving ({self._current_vehicle_speed_kmh} km/h)",
                    code="SPEED_INTERLOCK_ACTIVE",
                )

            # Rule 5: Rate Limiting Enforcement (Sliding Window with deque)
            now = time.monotonic()
            while self._tx_timestamps and (now - self._tx_timestamps[0]) >= 1.0:
                self._tx_timestamps.popleft()

            if len(self._tx_timestamps) >= self.MAX_TX_RATE_PER_SEC:
                logger.error("TX Rate limit exceeded! Triggering E-Stop.")
                self.estop.trigger(
                    EStopTriggerSource.RATE_LIMIT_OVERFLOW,
                    f"Exceeded max TX rate ({self.MAX_TX_RATE_PER_SEC} msg/s)",
                )
                raise SafetyError(
                    "Transmission rate limit exceeded (100 msg/s)",
                    code="RATE_LIMIT_EXCEEDED",
                )

            self._tx_timestamps.append(now)

            # Transmit frame via HAL
            self.bus.send(frame)
            return True
