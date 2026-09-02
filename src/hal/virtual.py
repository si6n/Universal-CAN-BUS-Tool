"""Virtual CAN Bus implementation for in-memory and simulated testing."""

from __future__ import annotations

import queue
from typing import Any

from src.core.errors import HardwareError
from src.core.models.can_frame import CanFrame
from src.hal.base import AbstractBus, BusState


class VirtualBus(AbstractBus):
    """Thread-safe in-memory virtual CAN bus for unit testing and simulations."""

    def __init__(
        self,
        channel_id: str = "virtual_0",
        bitrate: int = 500000,
        is_fd: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(channel_id=channel_id, bitrate=bitrate, is_fd=is_fd)
        self.sent_frames: list[CanFrame] = []
        self._rx_queue: queue.Queue[CanFrame] = queue.Queue()

    def connect(self) -> None:
        """Connect the virtual CAN bus."""
        self.is_connected = True
        self.metrics.state = BusState.ACTIVE

    def disconnect(self) -> None:
        """Disconnect the virtual CAN bus."""
        self.is_connected = False
        self.metrics.state = BusState.DISCONNECTED

    def send(self, frame: CanFrame) -> None:
        """Transmit frame onto the virtual bus (canonical TX entry point, D8)."""
        if not self.is_connected:
            raise HardwareError("Cannot send: Virtual CAN bus is not connected")
        self.sent_frames.append(frame)
        self.metrics.tx_frames += 1

    def recv(self, timeout_s: float | None = 0.1) -> CanFrame | None:
        """Receive next available CAN frame from the virtual queue."""
        if not self.is_connected:
            raise HardwareError("Cannot receive: Virtual CAN bus is not connected")
        try:
            frame = self._rx_queue.get(timeout=timeout_s if timeout_s is not None else 0.05)
            self.metrics.rx_frames += 1
            return frame
        except queue.Empty:
            return None

    def inject_rx(self, frame: CanFrame) -> None:
        """Inject a CAN frame into the receive queue."""
        self._rx_queue.put(frame)
