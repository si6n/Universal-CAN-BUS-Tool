"""Dual-Confirmation TX Safety Gateway enforcing CORE_SAFETY_FLOOR and Speed Interlocks.

Matches MASTER_PLAN.md Section 7, ISO 26262 ASIL-B/D, and Saha Risk Kataloğu v1.2 Sections 4, 19, 20.
Enforces strict 6-stage policy evaluation order:
1. Frame Sanity & Range Validation
2. Safety State & E-Stop Status
3. Whitelist Authorization (Fail-Closed)
4. Speed Interlock (Stationary & Freshness)
5. Dual Confirmation Check
6. Rate Budget (Sliding Window in monotonic nanoseconds)
"""

from __future__ import annotations

import asyncio
import collections
import math
import threading
import time
from typing import TYPE_CHECKING, ClassVar

from src.core.errors import SafetyError
from src.core.logging import get_logger
from src.core.models.can_frame import CanFrame
from src.safety.estop import EmergencyStopSystem, EStopTriggerSource
from src.safety.exceptions import (
    DualConfirmationRequiredError,
    FrameSanityError,
    RateLimitExceededError,
    SpeedDataStaleError,
    SpeedInterlockError,
    WhitelistFailClosedError,
    WhitelistViolationError,
)

if TYPE_CHECKING:
    from src.hal.base import AbstractBus
    from src.safety.state_machine import SafetySupervisor
    from src.safety.watchdog import TxWatchdogSupervisor

logger = get_logger("safety.gateway")


class TxSafetyGateway:
    """Security and Functional Safety Gateway filtering all outgoing CAN transmissions."""

    MAX_TX_RATE_PER_SEC: ClassVar[int] = 100  # Max 100 msg/s to prevent bus starvation
    SPEED_NOISE_THRESHOLD_KMH: ClassVar[float] = 0.5  # Permitted sensor jitter / noise threshold
    SPEED_VALIDITY_TIMEOUT_NS: ClassVar[int] = 1_000_000_000  # 1.0 second speed freshness timeout
    RATE_LIMIT_WINDOW_NS: ClassVar[int] = 1_000_000_000  # 1.0 second sliding window (nanoseconds)

    def __init__(
        self,
        bus: AbstractBus,
        estop: EmergencyStopSystem | None = None,
        supervisor: SafetySupervisor | None = None,
        watchdog: TxWatchdogSupervisor | None = None,
        whitelist_ids: set[int] | None = None,
        allow_all_for_testing: bool = False,
    ) -> None:
        self.bus = bus
        self.estop = estop or EmergencyStopSystem()
        self.supervisor = supervisor
        self.watchdog = watchdog
        self.whitelist_ids: set[int] = set(whitelist_ids) if whitelist_ids is not None else set()
        self.allow_all_for_testing = allow_all_for_testing

        # Rate budget window: monotonic nanosecond integers ONLY (CAN-25).
        self._tx_timestamps: collections.deque[int] = collections.deque()
        self._current_vehicle_speed_kmh: float = 0.0
        # 0 is the fail-closed sentinel: no vehicle speed telemetry has EVER been
        # received. Critical commands MUST be blocked until the first real update;
        # initializing to "now" would let a critical TX pass the freshness gate
        # during the first second after boot with zero telemetry.
        self._last_speed_update_ns: int = 0
        self._lock = threading.RLock()

        if self.supervisor is None and not self.allow_all_for_testing:
            logger.warning(
                "TxSafetyGateway constructed WITHOUT a SafetySupervisor: "
                "Stage 2 state gating (PASSIVE/FAULT enforcement) is disabled. "
                "Production deployments MUST supply a supervisor.",
            )

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

    def update_vehicle_speed(self, speed_kmh: float, timestamp_ns: int | None = None) -> None:
        """Update live vehicle speed for dynamic interlock enforcement.

        Non-finite telemetry (NaN/inf from a corrupted J1939 CCVS decode) is
        REJECTED without refreshing the freshness timestamp: `max(0.0, nan)`
        silently evaluates to 0.0, which would disguise poisoned telemetry as
        a stationary vehicle and open the speed interlock. Dropping the update
        lets the staleness gate fail closed instead.
        """
        if not math.isfinite(speed_kmh):
            logger.error(
                "Rejected non-finite vehicle speed telemetry update",
                extra={"speed_kmh": repr(speed_kmh)},
            )
            return
        with self._lock:
            self._current_vehicle_speed_kmh = max(0.0, speed_kmh)
            self._last_speed_update_ns = timestamp_ns if timestamp_ns is not None else time.monotonic_ns()

    def validate_and_transmit(
        self,
        frame: CanFrame,
        is_critical_command: bool = False,
        user_confirmed: bool = False,
    ) -> bool:
        """Enforce strict 6-stage policy evaluation order before transmitting onto HAL."""
        with self._lock:
            now_ns = time.monotonic_ns()

            # -----------------------------------------------------------------
            # Stage 1: Frame Sanity & Range Validation
            # -----------------------------------------------------------------
            if not isinstance(frame, CanFrame):
                raise FrameSanityError("Transmission rejected: Invalid frame object")

            max_id = 0x1FFFFFFF if frame.is_extended else 0x7FF
            if not (0 <= frame.arbitration_id <= max_id):
                raise FrameSanityError(
                    f"Frame sanity violation: ID 0x{frame.arbitration_id:X} out of range (max 0x{max_id:X})",
                    details={"arbitration_id": frame.arbitration_id, "max_id": max_id},
                )

            if not frame.is_fd and len(frame.data) > 8:
                raise FrameSanityError(
                    f"Frame sanity violation: Classic CAN payload > 8 bytes (len={len(frame.data)})",
                    details={"length": len(frame.data)},
                )

            if frame.is_fd and len(frame.data) > 64:
                raise FrameSanityError(
                    f"Frame sanity violation: CAN-FD payload > 64 bytes (len={len(frame.data)})",
                    details={"length": len(frame.data)},
                )

            # -----------------------------------------------------------------
            # Stage 2: Safety State & E-Stop Status
            # -----------------------------------------------------------------
            if self.supervisor is not None and not self.supervisor.is_tx_permitted:
                raise SafetyError(
                    f"Transmission blocked: Safety State is '{self.supervisor.current_state.value}' (TX not permitted)",
                    code="SAFETY_STATE_BLOCKED",
                )

            if self.watchdog is not None and not self.watchdog.is_lease_valid:
                raise SafetyError(
                    "Transmission blocked: Watchdog lease has expired",
                    code="WATCHDOG_LEASE_EXPIRED",
                )

            if self.estop.is_engaged:
                raise SafetyError(
                    "Transmission blocked: Emergency Stop is currently ENGAGED",
                    code="ESTOP_ACTIVE",
                )

            # -----------------------------------------------------------------
            # Stage 3: Whitelist Authorization (Fail-Closed)
            # -----------------------------------------------------------------
            if not self.allow_all_for_testing:
                if not self.whitelist_ids:
                    raise WhitelistFailClosedError(
                        "Transmission blocked: Dynamic whitelist is empty or unconfigured (Fail-Closed)",
                    )
                if frame.arbitration_id not in self.whitelist_ids:
                    logger.warning(
                        "TX Frame rejected by Whitelist filter",
                        extra={"arbitration_id": hex(frame.arbitration_id)},
                    )
                    self.estop.trigger(
                        EStopTriggerSource.UNAUTHORIZED_PAYLOAD,
                        f"Attempted TX to non-whitelisted ID: 0x{frame.arbitration_id:08X}",
                    )
                    raise WhitelistViolationError(
                        f"Transmission blocked: ID 0x{frame.arbitration_id:08X} not in whitelist",
                        details={"arbitration_id": frame.arbitration_id},
                    )

            # -----------------------------------------------------------------
            # Stage 4: Speed Interlock (Evaluated STRICTLY BEFORE Dual Confirmation)
            # -----------------------------------------------------------------
            if is_critical_command:
                # Speed telemetry freshness check
                if self._last_speed_update_ns == 0 or (now_ns - self._last_speed_update_ns) > self.SPEED_VALIDITY_TIMEOUT_NS:
                    self.estop.trigger(
                        EStopTriggerSource.SPEED_INTERLOCK_BREACH,
                        "Critical command attempted with stale or missing vehicle speed telemetry",
                        vehicle_speed_kmh=self._current_vehicle_speed_kmh,
                    )
                    raise SpeedDataStaleError(
                        "Safety Interlock: Critical command blocked due to stale vehicle speed telemetry",
                    )

                # Speed threshold check
                if self._current_vehicle_speed_kmh > self.SPEED_NOISE_THRESHOLD_KMH:
                    logger.critical(
                        "Speed interlock triggered on critical command",
                        extra={"speed": self._current_vehicle_speed_kmh},
                    )
                    self.estop.trigger(
                        EStopTriggerSource.SPEED_INTERLOCK_BREACH,
                        f"Critical command attempted while moving ({self._current_vehicle_speed_kmh} km/h)",
                        vehicle_speed_kmh=self._current_vehicle_speed_kmh,
                    )
                    raise SpeedInterlockError(
                        f"Safety Interlock: Critical command blocked while vehicle is moving ({self._current_vehicle_speed_kmh} km/h)",
                    )

            # -----------------------------------------------------------------
            # Stage 5: Dual Confirmation Check
            # -----------------------------------------------------------------
            if is_critical_command and not user_confirmed:
                raise DualConfirmationRequiredError(
                    "Critical command rejected: Operator dual-confirmation missing",
                )

            # -----------------------------------------------------------------
            # Stage 6: Rate Budget Enforcement (Sliding Window in monotonic nanoseconds)
            # -----------------------------------------------------------------
            # CAN-25: the window holds monotonic_ns integers exclusively. No
            # unit-guessing heuristics: mixed units mis-expire entries and can
            # either starve the budget or wedge the limiter into permanent E-Stop.
            while self._tx_timestamps and (now_ns - self._tx_timestamps[0]) >= self.RATE_LIMIT_WINDOW_NS:
                self._tx_timestamps.popleft()

            if len(self._tx_timestamps) >= self.MAX_TX_RATE_PER_SEC:
                logger.error("TX Rate limit exceeded! Triggering E-Stop.")
                self.estop.trigger(
                    EStopTriggerSource.RATE_LIMIT_OVERFLOW,
                    f"Exceeded max TX rate ({self.MAX_TX_RATE_PER_SEC} msg/s)",
                )
                raise RateLimitExceededError("Transmission rate limit exceeded (100 msg/s)")

            self._tx_timestamps.append(now_ns)

        # ---------------------------------------------------------------------
        # Privileged dispatch: TxSafetyGateway is the SOLE sanctioned caller of
        # the protected HAL primitive. NEVER fall back to the public bus.send():
        # a subclass override of send() would silently bypass this choke-point.
        # Dispatch happens OUTSIDE self._lock so a blocking/wedged HAL write can
        # never stall E-Stop handling, speed telemetry updates, or the FAULT
        # queue flush (fail-silent requirement).
        # ---------------------------------------------------------------------
        self.bus._send_raw(frame)
        return True

    def send_sync(self, frame: CanFrame) -> None:
        """Synchronously transmit frame conforming to TxPort protocol."""
        self.validate_and_transmit(frame, is_critical_command=False, user_confirmed=False)

    async def send(self, frame: CanFrame) -> None:
        """Asynchronously transmit frame conforming to TxPort protocol.

        Runs the blocking validation + HAL dispatch in a worker thread so a
        slow or wedged bus driver cannot stall the event loop (which would
        delay UI E-Stop handling and watchdog petting).
        """
        await asyncio.to_thread(self.send_sync, frame)
