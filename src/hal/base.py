"""Abstract Base CAN Interface (HAL) and Metrics Model."""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass
from types import TracebackType
from typing import Self

from src.core.models.can_frame import CanFrame


class BusState(str, enum.Enum):
    """Bus operational state enum."""

    ACTIVE = "active"
    PASSIVE = "passive"
    BUS_OFF = "bus_off"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    STOPPED = "stopped"

    def __str__(self) -> str:
        return self.value


@dataclass(slots=True)
class BusMetrics:
    """Real-time bus operational metrics and statistics."""

    channel_id: str
    rx_frames: int = 0
    tx_frames: int = 0
    error_frames: int = 0
    bus_load_percent: float = 0.0
    bitrate: int = 250000
    data_bitrate: int | None = None
    state: BusState | str = BusState.ACTIVE


class AbstractBus(ABC):
    """Abstract Base Class for all CAN hardware and virtual interfaces."""

    def __init__(self, channel_id: str, bitrate: int = 250000, is_fd: bool = False) -> None:
        self.channel_id = channel_id
        self.bitrate = bitrate
        self.is_fd = is_fd
        self.is_connected = False
        self.metrics = BusMetrics(channel_id=channel_id, bitrate=bitrate)

    @abstractmethod
    def connect(self) -> None:
        """Initialize and connect to the physical or virtual CAN channel."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection and release hardware resources."""
        ...

    @abstractmethod
    def _send_raw(self, frame: CanFrame) -> None:
        """Protected hardware transmission routine implemented by concrete drivers.

        SAFETY INVARIANT (CAN-02): TxSafetyGateway is the ONLY sanctioned caller.
        Upper application and protocol layers MUST NOT call this directly;
        transmissions must be routed through TxPort / TxSafetyGateway.

        NOTE: The legacy public ``send()`` method has been REMOVED deliberately.
        It allowed any caller (UDS, demo, UI, replay) to transmit around the
        6-stage safety pipeline, and its ``_send_raw -> send()`` re-entry
        fallback let subclasses override ``send()`` to silently bypass the
        choke-point. Buses that cannot transmit fail at construction time
        (abstract method) instead of failing open at first TX.
        """
        ...

    @abstractmethod
    def recv(self, timeout_s: float | None = 0.1) -> CanFrame | None:
        """Receive a single CanFrame within timeout. Returns None on timeout."""
        ...

    def get_metrics(self) -> BusMetrics:
        """Return current bus performance metrics."""
        return self.metrics

    def __enter__(self) -> Self:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.disconnect()
