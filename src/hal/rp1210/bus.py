"""RP1210Bus — AbstractBus adapter for the TMC RP1210 client.

RP1210 wire format (J1708/J1939 raw CAN framing): a 2-byte little-endian
header (bits 0-3: DLC, bits 4-15: 12-bit CAN identifier) followed by the
payload bytes. For 29-bit extended IDs used by J1939 the RP1210 protocol
stack handles PDU1/PDU2 layout natively; the adapter only marshals between
that wire form and the platform CanFrame model.
"""

from __future__ import annotations

import time
from typing import ClassVar

from src.core.errors import HardwareError
from src.core.logging import get_logger
from src.core.models.can_frame import CanFrame
from src.hal.base import AbstractBus, BusMetrics, BusState
from src.hal.rp1210.client import RP1210Client

logger = get_logger("hal.rp1210.bus")


class RP1210Bus(AbstractBus):
    """AbstractBus implementation over a TMC RP1210 vendor adapter (K4-a)."""

    DEFAULT_TX_BUFFER: ClassVar[int] = 8000
    DEFAULT_RX_BUFFER: ClassVar[int] = 8000
    MAX_CLASSIC_PAYLOAD: ClassVar[int] = 8

    def __init__(
        self,
        device_id: int = 1,
        protocol: str = "J1939",
        bitrate: int = 250000,
        dll_name: str = "RP121032.DLL",
        client: RP1210Client | None = None,
    ) -> None:
        super().__init__(channel_id=f"rp1210_dev{device_id}", bitrate=bitrate, is_fd=False)
        self.device_id = device_id
        self.protocol = protocol
        # Client may be injected for testing (a pre-mocked RP1210Client);
        # otherwise the real vendor DLL is loaded from System32 (D7 order).
        self._client = client or RP1210Client(
            dll_name=dll_name, device_id=device_id, protocol=protocol
        )
        self.metrics = BusMetrics(channel_id=self.channel_id, bitrate=bitrate)
        self.metrics.state = BusState.DISCONNECTED

    # ------------------------------------------------------------------
    # AbstractBus contract
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Establish the RP1210 client session and mark the bus ACTIVE."""
        try:
            self._client.connect(
                tx_buffer_size=self.DEFAULT_TX_BUFFER, rx_buffer_size=self.DEFAULT_RX_BUFFER
            )
        except HardwareError:
            raise
        except (OSError, RuntimeError) as exc:
            raise HardwareError(
                f"RP1210 connect failed: {exc}",
                code="HARDWARE_CONNECT_FAILED",
                details={"device_id": self.device_id, "protocol": self.protocol},
                cause=exc,
            ) from exc
        self.is_connected = True
        self.metrics.state = BusState.ACTIVE
        logger.info(
            "RP1210 bus connected",
            extra={"device_id": self.device_id, "protocol": self.protocol, "bitrate": self.bitrate},
        )

    def disconnect(self) -> None:
        """Gracefully close the RP1210 session (idempotent)."""
        try:
            self._client.disconnect()
        except (OSError, RuntimeError) as exc:
            logger.warning("RP1210 disconnect failed", extra={"error": str(exc)})
        finally:
            self.is_connected = False
            self.metrics.state = BusState.DISCONNECTED

    def send(self, frame: CanFrame) -> None:
        """Transmit a frame via the RP1210 adapter (canonical TX, D8)."""
        if not self.is_connected:
            raise HardwareError("Cannot send: RP1210 bus is not connected")
        if frame.is_fd:
            raise HardwareError(
                "RP1210 classic CAN adapters do not support CAN-FD frames",
                code="HARDWARE_FRAME_REJECTED",
            )
        data = bytes(frame.data[: self.MAX_CLASSIC_PAYLOAD])
        header = (frame.arbitration_id & 0x0FFF) << 4 | (len(data) & 0x0F)
        self._client.send_message(
            header.to_bytes(2, "little") + data,
        )
        self.metrics.tx_frames += 1

    def recv(self, timeout_s: float | None = 0.1) -> CanFrame | None:
        """Poll one frame from the RP1210 RX queue within the timeout."""
        if not self.is_connected:
            raise HardwareError("Cannot receive: RP1210 bus is not connected")

        deadline = time.monotonic() + (timeout_s if timeout_s is not None else 0.1)
        while True:
            try:
                raw = self._client.read_message(block=False)
            except HardwareError as exc:
                # Transient RX errors are logged and treated as "no frame":
                # one malformed vendor packet must not kill the ingest loop.
                logger.warning("RP1210 read error; skipping", extra={"error": str(exc)})
                return None

            if raw is not None and len(raw) >= 2:
                frame = self._decode_rp1210_packet(raw)
                if frame is not None:
                    self.metrics.rx_frames += 1
                    return frame

            if time.monotonic() >= deadline:
                return None
            time.sleep(0.001)

    # ------------------------------------------------------------------
    # RP1210 wire format marshalling
    # ------------------------------------------------------------------

    def _decode_rp1210_packet(self, raw: bytes) -> CanFrame | None:
        """Decode a 2-byte-header RP1210 packet into a CanFrame."""
        header = int.from_bytes(raw[:2], "little")
        dlc = header & 0x0F
        arb_id = (header >> 4) & 0x0FFF
        payload = raw[2 : 2 + dlc]

        if len(payload) < dlc:
            logger.warning(
                "RP1210 packet shorter than declared DLC; dropped",
                extra={"declared_dlc": dlc, "actual": len(payload)},
            )
            return None

        return CanFrame(
            channel_id=self.channel_id,
            arbitration_id=arb_id,
            dlc=dlc,
            data=bytes(payload),
            is_extended=arb_id > 0x7FF,
            is_fd=False,
            direction="rx",
            timestamp_ns=time.time_ns(),
        )
