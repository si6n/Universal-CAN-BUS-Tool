"""ISO 15765-2 DoCAN (ISO-TP) Multi-Frame Transport Protocol Engine.

Supports Standard CAN (8B) and CAN-FD (64B) segmentation/reassembly (Single Frame, First Frame, Consecutive Frame, Flow Control).
Complies with ISO 15765-2:2016 and MASTER_PLAN.md Section 5.1.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import ClassVar

from src.core.logging import get_logger
from src.core.models.can_frame import CanFrame

logger = get_logger("protocols.uds.isotp")

# ISO 15765-2 N_PCI Types (4 bits)
PCI_SINGLE_FRAME: int = 0x0
PCI_FIRST_FRAME: int = 0x1
PCI_CONSECUTIVE_FRAME: int = 0x2
PCI_FLOW_CONTROL: int = 0x3

# Flow Status codes
FS_CTS: int = 0
FS_WAIT: int = 1
FS_OVERFLOW: int = 2


def decode_st_min(st_min_byte: int) -> float:
    """Decode ISO 15765-2 STmin byte to milliseconds/float."""
    if st_min_byte <= 0x7F:
        return float(st_min_byte)
    elif 0xF1 <= st_min_byte <= 0xF9:
        return round((st_min_byte - 0xF0) * 0.1, 2)
    return 127.0


@dataclass(slots=True)
class IsoTpRxSession:
    """Active ISO-TP reception session."""

    rx_id: int
    total_bytes: int
    expected_sequence_number: int = 1
    received_bytes: bytearray = field(default_factory=bytearray)
    block_size: int = 0
    st_min_ms: float = 0.0
    last_activity_time: float = field(default_factory=time.monotonic)
    channel_id: str = "uds_ch0"


class IsoTpTransport:
    """ISO 15765-2 DoCAN Segmentation and Reassembly Engine."""

    TIMEOUT_SEC: ClassVar[float] = 1.0  # N_Cr timeout (1000 ms)

    def __init__(self, tx_id: int = 0x7E0, rx_id: int = 0x7E8, channel_id: str = "uds_ch0") -> None:
        self.tx_id = tx_id
        self.rx_id = rx_id
        self.channel_id = channel_id
        self._rx_session: IsoTpRxSession | None = None

    def segment_message(self, data: bytes, is_fd: bool = False) -> list[CanFrame]:
        """Segment outgoing payload into ISO-TP CAN frames (Single Frame or First Frame + Consecutive Frames)."""
        data_len = len(data)
        if data_len == 0:
            return []

        # 1. CAN-FD Single Frame (up to 62 bytes)
        if is_fd and data_len <= 62:
            payload = bytes([0x00, data_len]) + data + (b"\xCC" * (62 - data_len))
            return [
                CanFrame(
                    channel_id=self.channel_id,
                    arbitration_id=self.tx_id,
                    dlc=15,
                    data=payload,
                    is_extended=False,
                    is_fd=True,
                    direction="tx",
                )
            ]

        # 2. CAN-FD Multi-Frame (FF with 62 payload bytes, CF with 63 payload bytes)
        if is_fd:
            frames: list[CanFrame] = []
            ff_payload = bytes([
                (PCI_FIRST_FRAME << 4) | ((data_len >> 8) & 0x0F),
                data_len & 0xFF,
            ]) + data[:62]
            frames.append(
                CanFrame(
                    channel_id=self.channel_id,
                    arbitration_id=self.tx_id,
                    dlc=15,
                    data=ff_payload,
                    is_extended=False,
                    is_fd=True,
                    direction="tx",
                )
            )

            bytes_sent = 62
            seq_num = 1
            while bytes_sent < data_len:
                chunk = data[bytes_sent : bytes_sent + 63]
                pad_len = 63 - len(chunk)
                cf_payload = bytes([(PCI_CONSECUTIVE_FRAME << 4) | (seq_num & 0x0F)]) + chunk + (b"\xCC" * pad_len)

                frames.append(
                    CanFrame(
                        channel_id=self.channel_id,
                        arbitration_id=self.tx_id,
                        dlc=15,
                        data=cf_payload,
                        is_extended=False,
                        is_fd=True,
                        direction="tx",
                    )
                )
                bytes_sent += len(chunk)
                seq_num = (seq_num + 1) & 0x0F

            return frames

        # 3. Standard CAN Single Frame fits in 1 CAN frame (<= 7 bytes)
        if data_len <= 7:
            payload = bytes([(PCI_SINGLE_FRAME << 4) | (data_len & 0x0F)]) + data + (b"\xCC" * (7 - data_len))
            return [
                CanFrame(
                    channel_id=self.channel_id,
                    arbitration_id=self.tx_id,
                    dlc=8,
                    data=payload,
                    is_extended=False,
                    direction="tx",
                )
            ]

        # 4. Standard CAN Multi-Frame (FF + CFs)
        frames = []
        ff_payload = bytes([
            (PCI_FIRST_FRAME << 4) | ((data_len >> 8) & 0x0F),
            data_len & 0xFF,
        ]) + data[:6]
        frames.append(
            CanFrame(
                channel_id=self.channel_id,
                arbitration_id=self.tx_id,
                dlc=8,
                data=ff_payload,
                is_extended=False,
                direction="tx",
            )
        )

        bytes_sent = 6
        seq_num = 1

        while bytes_sent < data_len:
            chunk = data[bytes_sent : bytes_sent + 7]
            pad_len = 7 - len(chunk)
            cf_payload = bytes([(PCI_CONSECUTIVE_FRAME << 4) | (seq_num & 0x0F)]) + chunk + (b"\xCC" * pad_len)

            frames.append(
                CanFrame(
                    channel_id=self.channel_id,
                    arbitration_id=self.tx_id,
                    dlc=8,
                    data=cf_payload,
                    is_extended=False,
                    direction="tx",
                )
            )
            bytes_sent += len(chunk)
            seq_num = (seq_num + 1) & 0x0F

        return frames

    def handle_rx_frame(self, frame: CanFrame) -> tuple[bytes | None, CanFrame | None]:
        """Process incoming CAN frame for ISO-TP reassembly.

        Returns: (CompletedPayload, ResponseFrame)
        """
        if frame.arbitration_id != self.rx_id or len(frame.data) < 2:
            return None, None

        pci_type = (frame.data[0] >> 4) & 0x0F
        now = time.monotonic()

        # 1. Single Frame (SF)
        if pci_type == PCI_SINGLE_FRAME:
            if (frame.data[0] & 0x0F) == 0:
                # CAN-FD Extended Single Frame (SF_DL > 7, up to 62 bytes)
                if len(frame.data) < 2:
                    return None, None
                sf_len = frame.data[1]
                if 1 <= sf_len <= (len(frame.data) - 2):
                    return bytes(frame.data[2 : 2 + sf_len]), None
            else:
                # Classical CAN Single Frame (SF_DL <= 7)
                sf_len = frame.data[0] & 0x0F
                if 1 <= sf_len <= (len(frame.data) - 1):
                    return bytes(frame.data[1 : 1 + sf_len]), None
            return None, None

        # 2. First Frame (FF)
        if pci_type == PCI_FIRST_FRAME:
            total_len = ((frame.data[0] & 0x0F) << 8) | frame.data[1]
            first_chunk = frame.data[2:8]

            self._rx_session = IsoTpRxSession(
                rx_id=frame.arbitration_id,
                total_bytes=total_len,
                expected_sequence_number=1,
                received_bytes=bytearray(first_chunk),
                last_activity_time=now,
                channel_id=frame.channel_id,
            )

            # Generate Flow Control (CTS, BS=0, STmin=0)
            fc_data = bytearray(8)
            fc_data[0] = (PCI_FLOW_CONTROL << 4) | FS_CTS
            fc_data[1] = 0x00  # Block size = 0 (send all)
            fc_data[2] = 0x00  # STmin = 0 ms
            for i in range(3, 8):
                fc_data[i] = 0xCC

            fc_frame = CanFrame.create(
                channel_id=frame.channel_id,
                arbitration_id=self.tx_id,
                data=bytes(fc_data),
                is_extended=frame.is_extended,
                direction="tx",
            )
            return None, fc_frame

        # 3. Consecutive Frame (CF)
        if pci_type == PCI_CONSECUTIVE_FRAME:
            if self._rx_session is None:
                return None, None

            session = self._rx_session

            # Check timeout
            if (now - session.last_activity_time) > self.TIMEOUT_SEC:
                logger.warning("ISO-TP Consecutive Frame timeout", extra={"rx_id": hex(self.rx_id)})
                self._rx_session = None
                return None, None

            seq_num = frame.data[0] & 0x0F
            if seq_num != session.expected_sequence_number:
                logger.warning(
                    "ISO-TP Sequence mismatch",
                    extra={"expected": session.expected_sequence_number, "got": seq_num},
                )
                self._rx_session = None
                return None, None

            needed = session.total_bytes - len(session.received_bytes)
            chunk = frame.data[1 : 1 + min(7, needed)]
            session.received_bytes.extend(chunk)
            session.expected_sequence_number = (session.expected_sequence_number + 1) & 0x0F
            session.last_activity_time = now

            if len(session.received_bytes) >= session.total_bytes:
                completed = bytes(session.received_bytes[:session.total_bytes])
                self._rx_session = None
                return completed, None

            return None, None

        return None, None
