"""python-can Hardware Driver Wrapper (PEAK, Kvaser, Vector, GS_USB, Virtual).

Supports Listen-Only bitrate scanning and lossless CanFrame bi-directional translation.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

import can

from src.core.errors import HardwareError, TransportError
from src.core.logging import get_logger
from src.core.models.can_frame import CanFrame, length_to_dlc
from src.hal.base import AbstractBus, BusState

logger = get_logger("hal.drivers")


class PythonCanBus(AbstractBus):
    """Universal python-can abstraction for industrial CAN transceivers."""

    def __init__(
        self,
        interface: str = "virtual",
        channel: str | int = "0",
        bitrate: int = 250000,
        data_bitrate: int | None = None,
        is_fd: bool = False,
        listen_only: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(channel_id=f"{interface}_{channel}", bitrate=bitrate, is_fd=is_fd)
        self.interface = interface
        self.channel = channel
        self.data_bitrate = data_bitrate
        self.listen_only = listen_only
        self.extra_kwargs = kwargs
        self._bus: can.BusABC | None = None

    def connect(self) -> None:
        """Initialize physical transceiver connection via python-can."""
        try:
            bus_kwargs: dict[str, Any] = {
                "interface": self.interface,
                "channel": self.channel,
                "bitrate": self.bitrate,
                "fd": self.is_fd,
                **self.extra_kwargs,
            }

            if self.is_fd and self.data_bitrate:
                bus_kwargs["data_bitrate"] = self.data_bitrate

            if self.listen_only:
                # python-can expects the BusState enum member; BusState is a
                # plain Enum (not a str-Enum), so the string "PASSIVE" fails
                # the driver's membership check and raises ValueError.
                bus_kwargs["state"] = can.BusState.PASSIVE

            self._bus = can.Bus(**bus_kwargs)
            self.is_connected = True
            self.metrics.state = BusState.PASSIVE if self.listen_only else BusState.ACTIVE
            logger.info(
                "Connected CAN hardware interface",
                extra={"interface": self.interface, "channel": str(self.channel), "bitrate": self.bitrate},
            )
        except (can.CanError, OSError, ValueError) as exc:
            self.is_connected = False
            self.metrics.state = BusState.DISCONNECTED
            raise HardwareError(
                f"Failed to connect to CAN interface '{self.interface}:{self.channel}': {exc}",
                code="HARDWARE_CONNECT_FAILED",
                details={"interface": self.interface, "channel": str(self.channel), "bitrate": self.bitrate},
                cause=exc,
            ) from exc

    def disconnect(self) -> None:
        """Shutdown CAN bus and release transceiver handles."""
        if self._bus is not None:
            try:
                self._bus.shutdown()
            except (can.CanError, OSError) as exc:
                logger.warning("Error during CAN bus shutdown", extra={"error": str(exc)})
            finally:
                self._bus = None
                self.is_connected = False
                self.metrics.state = BusState.DISCONNECTED

    def send(self, frame: CanFrame) -> None:
        """Transmit CanFrame on physical bus."""
        if not self.is_connected or self._bus is None:
            raise HardwareError("Cannot send: CAN bus is not connected")

        if self.listen_only:
            raise HardwareError("Cannot send: CAN bus is opened in Listen-Only (passive) mode")

        msg = can.Message(
            arbitration_id=frame.arbitration_id,
            is_extended_id=frame.is_extended,
            data=frame.data,
            is_fd=frame.is_fd,
            bitrate_switch=frame.brs,
            error_state_indicator=frame.esi,
            check=True,
        )

        try:
            self._bus.send(msg)
            self.metrics.tx_frames += 1
        except can.CanError as exc:
            self.metrics.error_frames += 1
            raise TransportError(
                f"Hardware frame transmission failed: {exc}",
                code="TRANSPORT_TX_FAILED",
                cause=exc,
            ) from exc

    def recv(self, timeout_s: float | None = 0.1) -> CanFrame | None:
        """Receive single CAN frame with timeout."""
        if not self.is_connected or self._bus is None:
            raise HardwareError("Cannot receive: CAN bus is not connected")

        try:
            msg = self._bus.recv(timeout=timeout_s)
            if msg is None:
                return None

            if msg.is_error_frame:
                self.metrics.error_frames += 1
                return None

            self.metrics.rx_frames += 1
            ts_ns = int(msg.timestamp * 1_000_000_000) if msg.timestamp else time.time_ns()

            return CanFrame(
                channel_id=self.channel_id,
                arbitration_id=msg.arbitration_id,
                dlc=msg.dlc if msg.dlc is not None else length_to_dlc(len(msg.data)),
                data=bytes(msg.data),
                is_extended=msg.is_extended_id,
                is_fd=msg.is_fd,
                brs=msg.bitrate_switch,
                esi=msg.error_state_indicator,
                direction="rx",
                timestamp_ns=ts_ns,
                source="physical",
            )
        except can.CanError as exc:
            self.metrics.error_frames += 1
            raise HardwareError(
                f"Hardware frame read error: {exc}",
                code="HARDWARE_READ_ERROR",
                cause=exc,
            ) from exc

    @classmethod
    def scan_bitrate(
        cls,
        interface: str,
        channel: str | int,
        candidates: Sequence[int] = (250000, 500000, 125000, 1000000),
        listen_timeout_s: float = 0.5,
    ) -> int | None:
        """Scan CAN line in Listen-Only mode to auto-detect valid bitrate without ACK disturbance."""
        for rate in candidates:
            bus = None
            try:
                bus = cls(interface=interface, channel=channel, bitrate=rate, listen_only=True)
                bus.connect()
                frame = bus.recv(timeout_s=listen_timeout_s)
                if frame is not None:
                    logger.info("Auto-detected active bitrate", extra={"bitrate": rate})
                    return rate
            except (can.CanError, OSError, HardwareError) as exc:
                logger.debug("Bitrate candidate failed", extra={"bitrate": rate, "error": str(exc)})
            finally:
                # F-22: always release the bus, including on exception paths
                if bus is not None:
                    try:
                        bus.disconnect()
                    except (can.CanError, OSError) as exc:
                        logger.debug(
                            "Disconnect after bitrate probe failed",
                            extra={"bitrate": rate, "error": str(exc)},
                        )
        return None
