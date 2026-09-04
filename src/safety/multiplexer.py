"""Thread-Safe Multiplexed Bus Adapter enforcing Centralized Safety and Single RX Ownership.

Matches NO-GO Remediation Plan (v1.0 Release Blockers).
"""

from __future__ import annotations

import queue
from typing import TYPE_CHECKING, ClassVar

from src.hal.base import AbstractBus

if TYPE_CHECKING:
    from src.core.models.can_frame import CanFrame
    from src.engine.router import FrameRouter
    from src.safety.gateway import TxSafetyGateway


class SafeMultiplexedBus(AbstractBus):
    """Adapter that routes physical TX through TxSafetyGateway and RX through FrameRouter.

    Resolves K-01: Removes physical TX capability from application layer.
    Resolves K-02: Prevents Frame Stealing by acting as an asynchronous Queue subscriber.
    """

    def __init__(
        self,
        physical_bus: AbstractBus,
        gateway: TxSafetyGateway,
        router: FrameRouter,
    ) -> None:
        super().__init__(channel_id=physical_bus.channel_id, bitrate=physical_bus.bitrate, is_fd=physical_bus.is_fd)
        self.physical_bus = physical_bus
        self.gateway = gateway
        self.router = router

        # Subscribe to FrameRouter for RX without stealing frames from hardware
        self.sub_id, self.rx_queue = self.router.subscribe(use_queue=True)
        if self.rx_queue is None:
            raise RuntimeError("SafeMultiplexedBus failed to obtain an RX queue from FrameRouter")

    @property
    def is_connected(self) -> bool:
        """Live connection state reflected directly from the underlying physical bus."""
        return bool(self.physical_bus and self.physical_bus.is_connected)

    @is_connected.setter
    def is_connected(self, value: bool) -> None:
        """S-2 (3FABLE): the old setter wrote a dead `_is_connected` field the
        getter never read. The base class assigns `is_connected = False`
        during __init__; the only meaningful delegation is to the physical
        bus's own flag (the router subscription is managed by
        connect/disconnect lifecycle methods)."""
        if self.physical_bus is not None:
            try:
                self.physical_bus.is_connected = value
            except AttributeError:
                # read-only property on the driver — nothing to sync
                pass

    def connect(self) -> None:
        """Physical bus connection is managed externally (e.g. by main UI)."""
        if not self.physical_bus.is_connected:
            self.physical_bus.connect()

    def disconnect(self) -> None:
        """Unsubscribe from router upon teardown."""
        self.router.unsubscribe(self.sub_id)

    def send(
        self,
        frame: CanFrame,
        *,
        is_critical_command: bool = False,
        user_confirmed: bool = False,
    ) -> None:
        """Enforce CORE_SAFETY_FLOOR on every transmission."""
        self.gateway.validate_and_transmit(
            frame,
            is_critical_command=is_critical_command,
            user_confirmed=user_confirmed,
        )

    def send_sync(self, frame: CanFrame) -> None:
        """Synchronously transmit frame conforming to TxPort protocol."""
        self.gateway.validate_and_transmit(frame, is_critical_command=False, user_confirmed=False)

    async def send_async(self, frame: CanFrame) -> None:
        """Asynchronously transmit frame conforming to TxPort protocol."""
        await self.gateway.send(frame)

    DEFAULT_RECV_TIMEOUT_S: ClassVar[float] = 1.0

    def recv(self, timeout_s: float | None = None) -> CanFrame | None:
        """Asynchronously read from the dedicated subscription queue, avoiding hardware race conditions.

        A `None` timeout falls back to the bounded default (F-23) — the queue
        never blocks forever, so callers stay responsive.
        """
        if self.rx_queue is None:
            return None

        effective_timeout = timeout_s if timeout_s is not None else self.DEFAULT_RECV_TIMEOUT_S
        try:
            # Block until frame available or timeout
            return self.rx_queue.get(timeout=effective_timeout)
        except queue.Empty:
            return None
