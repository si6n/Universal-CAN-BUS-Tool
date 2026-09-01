"""ISO 15765-2:2016 DoCAN (ISO-TP) Multi-Frame Transport Protocol Engine.

Supports Classic CAN (8B) and CAN-FD (up to 64B) segmentation and reassembly:
- Discrete DLC normalization (0..8, 12, 16, 20, 24, 32, 48, 64) with configurable padding.
- Classic Single Frame (len <= 7) and CAN-FD Extended Single Frame (len <= 62).
- Standard 12-bit First Frame (len <= 4095) and Extended 32-bit First Frame (len > 4095).
- Consecutive Frames with 0..15 sequence number wrapping.
- Flow Control (CTS, WAIT with WFTmax=16, OVERFLOW, Block Size, STmin pacing).
- Asynchronous IsoTpSender & IsoTpReceiver state machines with N_Bs / N_Cr timers.
- Backward-compatible synchronous IsoTpTransport helper.

Complies with ISO 15765-2:2016, ISO 11898-1:2015, and Phase 1 Architecture.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import ClassVar

from src.core.contracts.ports import ClockProvider, RxSubscription, SystemClockProvider, TxPort
from src.core.exceptions import (
    IsoTpBufferOverflowError,
    IsoTpError,
    IsoTpFlowControlError,
    IsoTpInvalidPduError,
    IsoTpSequenceError,
    IsoTpTimeoutError,
)
from src.core.logging import get_logger
from src.core.models.can_frame import (
    CanFrame,
    dlc_to_length,
    length_to_dlc,
    pad_payload,
)

logger = get_logger("protocols.uds.isotp")

__all__ = [
    "FS_CTS",
    "FS_OVERFLOW",
    "FS_WAIT",
    "PCI_CONSECUTIVE_FRAME",
    "PCI_FIRST_FRAME",
    "PCI_FLOW_CONTROL",
    "PCI_SINGLE_FRAME",
    "IsoTpError",
    "IsoTpReceiver",
    "IsoTpRxSession",
    "IsoTpSender",
    "IsoTpTransport",
    "decode_st_min",
    "normalize_can_payload",
]

# ISO 15765-2 N_PCI Types (4 bits)
PCI_SINGLE_FRAME: int = 0x0
PCI_FIRST_FRAME: int = 0x1
PCI_CONSECUTIVE_FRAME: int = 0x2
PCI_FLOW_CONTROL: int = 0x3

# Flow Status codes (4 bits)
FS_CTS: int = 0
FS_WAIT: int = 1
FS_OVERFLOW: int = 2


def decode_st_min(st_min_byte: int) -> float:
    """Decode ISO 15765-2 STmin byte to milliseconds as a float.

    Ranges:
    - 0x00 - 0x7F: 0 .. 127 ms (direct integer milliseconds)
    - 0xF1 - 0xF9: 100 .. 900 us (0.1 .. 0.9 ms in 100us increments)
    - 0x80 - 0xF0: Reserved -> clamped to 127.0 ms
    - 0xFA - 0xFF: Reserved -> clamped to 127.0 ms
    """
    if 0x00 <= st_min_byte <= 0x7F:
        return float(st_min_byte)
    elif 0xF1 <= st_min_byte <= 0xF9:
        return round((st_min_byte - 0xF0) * 0.1, 2)
    return 127.0


def normalize_can_payload(data: bytes, is_fd: bool, pad_byte: int | None = 0xCC) -> bytes:
    """Normalize payload length to standard Classic CAN (8B) or discrete CAN-FD DLCs.

    CAN-FD discrete lengths: 0..8, 12, 16, 20, 24, 32, 48, 64.
    """
    if pad_byte is None:
        return data

    data_len = len(data)
    if is_fd:
        dlc = length_to_dlc(data_len)
        expected_len = dlc_to_length(dlc)
        if data_len < expected_len:
            return data + bytes([pad_byte] * (expected_len - data_len))
        return data
    else:
        if data_len < 8:
            return data + bytes([pad_byte] * (8 - data_len))
        return data


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
    tx_id: int = 0x7E0
    is_fd: bool = False
    max_buffer_size: int = 1048576
    # CFs received since the last Flow Control we emitted (BS windowing)
    block_count: int = 0


# ============================================================================
# Synchronous ISO-TP Transport Helper (Backward Compatibility)
# ============================================================================


class IsoTpTransport:
    """ISO 15765-2 DoCAN Segmentation and Reassembly Engine (Synchronous)."""

    TIMEOUT_SEC: ClassVar[float] = 1.0  # N_Cr timeout (1000 ms)

    def __init__(
        self,
        tx_id: int = 0x7E0,
        rx_id: int = 0x7E8,
        channel_id: str = "uds_ch0",
        pad_byte: int | None = 0xCC,
        rx_block_size: int = 0,
        rx_st_min: int = 0,
    ) -> None:
        self.tx_id = tx_id
        self.rx_id = rx_id
        self.channel_id = channel_id
        self.pad_byte = pad_byte
        # Flow Control advertisement to senders: block size 0 = unlimited
        # (legacy behaviour), non-zero bounds each CTS window and makes the
        # receiver emit a fresh FC after every block. STmin is the raw
        # ISO 15765-2 byte (0..0x7F ms, 0xF1..0xF9 = 100 µs units).
        self.rx_block_size = rx_block_size
        self.rx_st_min = rx_st_min
        self._rx_session: IsoTpRxSession | None = None

    def segment_message(self, data: bytes, is_fd: bool = False) -> list[CanFrame]:
        """Segment outgoing payload into ISO-TP CAN frames (SF, Standard FF, Extended 32-bit FF, CF)."""
        data_len = len(data)
        if data_len == 0:
            return []

        # ------------------------------------------------------------------
        # 1. CAN-FD Extended Single Frame (up to 62 bytes)
        # ------------------------------------------------------------------
        if is_fd and data_len <= 62:
            sf_raw = bytes([0x00, data_len]) + data
            dlc = length_to_dlc(len(sf_raw))
            padded_data = pad_payload(sf_raw, dlc, pad_byte=self.pad_byte if self.pad_byte is not None else 0xCC)
            return [
                CanFrame(
                    channel_id=self.channel_id,
                    arbitration_id=self.tx_id,
                    dlc=dlc,
                    data=padded_data,
                    is_extended=self.tx_id > 0x7FF,
                    is_fd=True,
                    direction="tx",
                )
            ]

        # ------------------------------------------------------------------
        # 2. CAN-FD Multi-Frame (FF + CFs)
        # ------------------------------------------------------------------
        if is_fd:
            frames: list[CanFrame] = []
            if data_len <= 4095:
                # Standard 12-bit First Frame
                ff_raw = (
                    bytes(
                        [
                            (PCI_FIRST_FRAME << 4) | ((data_len >> 8) & 0x0F),
                            data_len & 0xFF,
                        ]
                    )
                    + data[:62]
                )
                ff_padded = pad_payload(ff_raw, 15, pad_byte=self.pad_byte if self.pad_byte is not None else 0xCC)
                frames.append(
                    CanFrame(
                        channel_id=self.channel_id,
                        arbitration_id=self.tx_id,
                        dlc=15,
                        data=ff_padded,
                        is_extended=self.tx_id > 0x7FF,
                        is_fd=True,
                        direction="tx",
                    )
                )
                bytes_sent = 62
            else:
                # Extended 32-bit First Frame
                ff_raw = bytes([0x10, 0x00]) + data_len.to_bytes(4, byteorder="big") + data[:58]
                ff_padded = pad_payload(ff_raw, 15, pad_byte=self.pad_byte if self.pad_byte is not None else 0xCC)
                frames.append(
                    CanFrame(
                        channel_id=self.channel_id,
                        arbitration_id=self.tx_id,
                        dlc=15,
                        data=ff_padded,
                        is_extended=self.tx_id > 0x7FF,
                        is_fd=True,
                        direction="tx",
                    )
                )
                bytes_sent = 58

            seq_num = 1
            while bytes_sent < data_len:
                chunk = data[bytes_sent : bytes_sent + 63]
                cf_raw = bytes([(PCI_CONSECUTIVE_FRAME << 4) | (seq_num & 0x0F)]) + chunk
                cf_padded = pad_payload(cf_raw, 15, pad_byte=self.pad_byte if self.pad_byte is not None else 0xCC)
                frames.append(
                    CanFrame(
                        channel_id=self.channel_id,
                        arbitration_id=self.tx_id,
                        dlc=15,
                        data=cf_padded,
                        is_extended=self.tx_id > 0x7FF,
                        is_fd=True,
                        direction="tx",
                    )
                )
                bytes_sent += len(chunk)
                seq_num = (seq_num + 1) & 0x0F

            return frames

        # ------------------------------------------------------------------
        # 3. Classic CAN Single Frame (<= 7 bytes)
        # ------------------------------------------------------------------
        if data_len <= 7:
            sf_raw = bytes([(PCI_SINGLE_FRAME << 4) | (data_len & 0x0F)]) + data
            padded_data = pad_payload(sf_raw, 8, pad_byte=self.pad_byte if self.pad_byte is not None else 0xCC)
            return [
                CanFrame(
                    channel_id=self.channel_id,
                    arbitration_id=self.tx_id,
                    dlc=8,
                    data=padded_data,
                    is_extended=self.tx_id > 0x7FF,
                    is_fd=False,
                    direction="tx",
                )
            ]

        # ------------------------------------------------------------------
        # 4. Classic CAN Multi-Frame (FF + CFs)
        # ------------------------------------------------------------------
        frames_classic: list[CanFrame] = []
        if data_len <= 4095:
            # Standard 12-bit First Frame
            ff_raw = (
                bytes(
                    [
                        (PCI_FIRST_FRAME << 4) | ((data_len >> 8) & 0x0F),
                        data_len & 0xFF,
                    ]
                )
                + data[:6]
            )
            ff_padded = pad_payload(ff_raw, 8, pad_byte=self.pad_byte if self.pad_byte is not None else 0xCC)
            frames_classic.append(
                CanFrame(
                    channel_id=self.channel_id,
                    arbitration_id=self.tx_id,
                    dlc=8,
                    data=ff_padded,
                    is_extended=self.tx_id > 0x7FF,
                    is_fd=False,
                    direction="tx",
                )
            )
            bytes_sent = 6
        else:
            # Extended 32-bit First Frame
            ff_raw = bytes([0x10, 0x00]) + data_len.to_bytes(4, byteorder="big") + data[:2]
            ff_padded = pad_payload(ff_raw, 8, pad_byte=self.pad_byte if self.pad_byte is not None else 0xCC)
            frames_classic.append(
                CanFrame(
                    channel_id=self.channel_id,
                    arbitration_id=self.tx_id,
                    dlc=8,
                    data=ff_padded,
                    is_extended=self.tx_id > 0x7FF,
                    is_fd=False,
                    direction="tx",
                )
            )
            bytes_sent = 2

        seq_num = 1
        while bytes_sent < data_len:
            chunk = data[bytes_sent : bytes_sent + 7]
            cf_raw = bytes([(PCI_CONSECUTIVE_FRAME << 4) | (seq_num & 0x0F)]) + chunk
            cf_padded = pad_payload(cf_raw, 8, pad_byte=self.pad_byte if self.pad_byte is not None else 0xCC)
            frames_classic.append(
                CanFrame(
                    channel_id=self.channel_id,
                    arbitration_id=self.tx_id,
                    dlc=8,
                    data=cf_padded,
                    is_extended=self.tx_id > 0x7FF,
                    is_fd=False,
                    direction="tx",
                )
            )
            bytes_sent += len(chunk)
            seq_num = (seq_num + 1) & 0x0F

        return frames_classic

    def handle_rx_frame(self, frame: CanFrame) -> tuple[bytes | None, CanFrame | None]:
        """Process incoming CAN frame for ISO-TP reassembly.

        Returns: (CompletedPayload, ResponseFrame)
        """
        if frame.arbitration_id != self.rx_id or len(frame.data) < 2:
            return None, None

        pci_type = (frame.data[0] >> 4) & 0x0F
        now = time.monotonic()

        # ------------------------------------------------------------------
        # 1. Single Frame (SF)
        # ------------------------------------------------------------------
        if pci_type == PCI_SINGLE_FRAME:
            if (frame.data[0] & 0x0F) == 0:
                # If frame is not CAN-FD, SF_DL == 0 is malformed Classic CAN frame
                if not frame.is_fd:
                    return None, None

                # CAN-FD Extended Single Frame (SF_DL <= 62)
                if len(frame.data) < 2:
                    return None, None
                sf_len = frame.data[1]
                if sf_len == 0 or sf_len > 62:
                    return None, None
                if sf_len <= (len(frame.data) - 2):
                    self._rx_session = None
                    return bytes(frame.data[2 : 2 + sf_len]), None
            else:
                # Classic CAN Single Frame (SF_DL 1..7)
                sf_len = frame.data[0] & 0x0F
                if 1 <= sf_len <= (len(frame.data) - 1):
                    self._rx_session = None
                    return bytes(frame.data[1 : 1 + sf_len]), None
            return None, None

        # ------------------------------------------------------------------
        # 2. First Frame (FF)
        # ------------------------------------------------------------------
        if pci_type == PCI_FIRST_FRAME:
            if len(frame.data) >= 6 and frame.data[0] == 0x10 and frame.data[1] == 0x00:
                # Extended 32-bit First Frame
                total_len = int.from_bytes(frame.data[2:6], byteorder="big")
                if total_len <= 4095:
                    return None, None
                header_len = 6
            else:
                # Standard 12-bit First Frame
                total_len = ((frame.data[0] & 0x0F) << 8) | frame.data[1]
                header_len = 2

            first_chunk = frame.data[header_len:]
            if len(first_chunk) > total_len:
                first_chunk = first_chunk[:total_len]

            self._rx_session = IsoTpRxSession(
                rx_id=frame.arbitration_id,
                total_bytes=total_len,
                expected_sequence_number=1,
                received_bytes=bytearray(first_chunk),
                last_activity_time=now,
                channel_id=frame.channel_id,
                is_fd=frame.is_fd,
            )

            # If First Frame already satisfied full payload length (e.g. 62B FD)
            if len(self._rx_session.received_bytes) >= total_len:
                completed = bytes(self._rx_session.received_bytes[:total_len])
                self._rx_session = None
                return completed, None

            # Generate Flow Control (CTS with configured BS/STmin)
            fc_data = bytearray(8)
            fc_data[0] = (PCI_FLOW_CONTROL << 4) | FS_CTS
            fc_data[1] = self.rx_block_size & 0xFF  # Block size (0 = send all)
            fc_data[2] = self.rx_st_min & 0xFF  # STmin (raw ISO 15765-2 byte)
            for i in range(3, 8):
                fc_data[i] = 0xCC

            fc_frame = CanFrame.create(
                channel_id=frame.channel_id,
                arbitration_id=self.tx_id,
                data=bytes(fc_data),
                is_extended=frame.is_extended,
                is_fd=frame.is_fd,
                direction="tx",
            )
            return None, fc_frame

        # ------------------------------------------------------------------
        # 3. Consecutive Frame (CF)
        # ------------------------------------------------------------------
        if pci_type == PCI_CONSECUTIVE_FRAME:
            if self._rx_session is None:
                return None, None

            session = self._rx_session

            # F-20: a CF arriving on a different channel must not corrupt an
            # in-flight session opened on another bus.
            if session.channel_id != frame.channel_id:
                logger.warning(
                    "ISO-TP CF channel mismatch — ignoring frame",
                    extra={"session_channel": session.channel_id, "frame_channel": frame.channel_id},
                )
                return None, None

            # Check N_Cr timeout
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
            available_payload = len(frame.data) - 1
            chunk_len = min(needed, available_payload)
            chunk = frame.data[1 : 1 + chunk_len]

            session.received_bytes.extend(chunk)
            session.expected_sequence_number = (session.expected_sequence_number + 1) & 0x0F
            session.last_activity_time = now

            if len(session.received_bytes) >= session.total_bytes:
                completed = bytes(session.received_bytes[: session.total_bytes])
                self._rx_session = None
                return completed, None

            # BS windowing: after rx_block_size consecutive frames the sender
            # needs a fresh FC (CTS) before it may continue transmitting.
            if self.rx_block_size > 0:
                session.block_count += 1
                if session.block_count >= self.rx_block_size:
                    session.block_count = 0
                    fc_data = bytearray(8)
                    fc_data[0] = (PCI_FLOW_CONTROL << 4) | FS_CTS
                    fc_data[1] = self.rx_block_size & 0xFF
                    fc_data[2] = self.rx_st_min & 0xFF
                    for i in range(3, 8):
                        fc_data[i] = 0xCC
                    fc_frame = CanFrame.create(
                        channel_id=frame.channel_id,
                        arbitration_id=self.tx_id,
                        data=bytes(fc_data),
                        is_extended=frame.is_extended,
                        is_fd=frame.is_fd,
                        direction="tx",
                    )
                    return None, fc_frame

            return None, None

        return None, None


# ============================================================================
# Asynchronous ISO-TP Sender State Machine
# ============================================================================


class IsoTpSender:
    """Asynchronous ISO 15765-2 DoCAN Sender State Machine."""

    def __init__(
        self,
        tx_port: TxPort,
        rx_sub: RxSubscription,
        tx_id: int,
        rx_id: int,
        channel_id: str = "uds_ch0",
        is_fd: bool = False,
        pad_byte: int | None = 0xCC,
        clock: ClockProvider | None = None,
        n_as_timeout_s: float = 1.0,
        n_bs_timeout_s: float = 1.0,
        wft_max: int = 16,
    ) -> None:
        self.tx_port = tx_port
        self.rx_sub = rx_sub
        self.tx_id = tx_id
        self.rx_id = rx_id
        self.channel_id = channel_id
        self.is_fd = is_fd
        self.pad_byte = pad_byte
        self.clock: ClockProvider = clock or SystemClockProvider()
        self.n_as_timeout_s = n_as_timeout_s
        self.n_bs_timeout_s = n_bs_timeout_s
        self.wft_max = wft_max

    def _build_frame(self, data: bytes, is_fd: bool) -> CanFrame:
        """Construct normalized and padded CAN frame."""
        if is_fd:
            dlc = length_to_dlc(len(data))
            padded = pad_payload(data, dlc, pad_byte=self.pad_byte if self.pad_byte is not None else 0xCC)
            return CanFrame(
                channel_id=self.channel_id,
                arbitration_id=self.tx_id,
                dlc=dlc,
                data=padded,
                is_extended=self.tx_id > 0x7FF,
                is_fd=True,
                direction="tx",
            )
        else:
            padded = pad_payload(data, 8, pad_byte=self.pad_byte if self.pad_byte is not None else 0xCC)
            return CanFrame(
                channel_id=self.channel_id,
                arbitration_id=self.tx_id,
                dlc=8,
                data=padded,
                is_extended=self.tx_id > 0x7FF,
                is_fd=False,
                direction="tx",
            )

    async def _send_with_n_as(self, frame: CanFrame) -> None:
        """Transmit one frame enforcing the N_As timeout.

        N_As (ISO 15765-2 §4.6.1) bounds the time for the network layer to
        complete a single frame transmission after the request. A TxPort
        that blocks longer than n_as_timeout_s is treated as a timeout.
        """
        send_task: asyncio.Future[None] = asyncio.ensure_future(self.tx_port.send(frame))
        elapsed = 0.0
        start = self.clock.now_monotonic()
        while True:
            remaining = self.n_as_timeout_s - (self.clock.now_monotonic() - start)
            if remaining <= 0:
                if not send_task.done():
                    send_task.cancel()
                raise IsoTpTimeoutError(
                    f"N_As timeout ({self.n_as_timeout_s * 1000:.0f}ms) transmitting ISO-TP frame",
                    timeout_type="N_As",
                    elapsed_ms=elapsed * 1000.0,
                    limit_ms=self.n_as_timeout_s * 1000.0,
                )
            try:
                await asyncio.wait_for(asyncio.shield(send_task), timeout=remaining)
                return
            except asyncio.TimeoutError:
                elapsed = self.clock.now_monotonic() - start
                if elapsed >= self.n_as_timeout_s:
                    send_task.cancel()
                    raise IsoTpTimeoutError(
                        f"N_As timeout ({self.n_as_timeout_s * 1000:.0f}ms) transmitting ISO-TP frame",
                        timeout_type="N_As",
                        elapsed_ms=elapsed * 1000.0,
                        limit_ms=self.n_as_timeout_s * 1000.0,
                    ) from None
                # Shield raced with completion; re-check
                if send_task.done() and not send_task.cancelled() and send_task.exception() is None:
                    return

    async def _apply_st_min(self, st_min_byte: int) -> None:
        """Execute STmin pacing delay via sleep or high-precision spin-wait."""
        if st_min_byte == 0x00:
            return
        elif 0x01 <= st_min_byte <= 0x7F:
            delay_s = st_min_byte / 1000.0
            await asyncio.sleep(delay_s)
        elif 0xF1 <= st_min_byte <= 0xF9:
            # 100..900 us high-precision spin wait
            delay_ns = (st_min_byte - 0xF0) * 100_000
            start_ns = time.perf_counter_ns()
            while (time.perf_counter_ns() - start_ns) < delay_ns:
                pass
        else:
            # Reserved range clamped to 127 ms
            await asyncio.sleep(0.127)

    async def _await_flow_control(self) -> CanFrame:
        """Await incoming Flow Control frame enforcing N_Bs timeout."""
        start_time = self.clock.now_monotonic()
        while True:
            elapsed = self.clock.now_monotonic() - start_time
            remaining = self.n_bs_timeout_s - elapsed
            if remaining <= 0:
                raise IsoTpTimeoutError(
                    f"N_Bs timeout ({self.n_bs_timeout_s * 1000:.0f}ms) awaiting Flow Control",
                    timeout_type="N_Bs",
                    elapsed_ms=elapsed * 1000.0,
                    limit_ms=self.n_bs_timeout_s * 1000.0,
                )

            frame = await self.rx_sub.recv(timeout_s=max(0.001, remaining))
            if frame is None:
                raise IsoTpTimeoutError(
                    f"N_Bs timeout ({self.n_bs_timeout_s * 1000:.0f}ms) awaiting Flow Control",
                    timeout_type="N_Bs",
                    elapsed_ms=self.n_bs_timeout_s * 1000.0,
                    limit_ms=self.n_bs_timeout_s * 1000.0,
                )

            if frame.arbitration_id != self.rx_id or len(frame.data) < 3:
                continue

            pci_type = frame.data[0] >> 4
            if pci_type == PCI_FLOW_CONTROL:
                return frame

    async def send(self, payload: bytes) -> None:
        """Transmit payload over ISO-TP asynchronously."""
        data_len = len(payload)
        if data_len == 0:
            return

        # 1. Single Frame Check
        if not self.is_fd and data_len <= 7:
            sf_raw = bytes([(PCI_SINGLE_FRAME << 4) | (data_len & 0x0F)]) + payload
            frame = self._build_frame(sf_raw, is_fd=False)
            await self._send_with_n_as(frame)
            return

        if self.is_fd and data_len <= 62:
            sf_raw = bytes([0x00, data_len]) + payload
            frame = self._build_frame(sf_raw, is_fd=True)
            await self._send_with_n_as(frame)
            return

        # 2. Multi-Frame First Frame
        if data_len <= 4095:
            ff_header = bytes([(PCI_FIRST_FRAME << 4) | ((data_len >> 8) & 0x0F), data_len & 0xFF])
            ff_payload_size = 62 if self.is_fd else 6
        else:
            ff_header = bytes([0x10, 0x00]) + data_len.to_bytes(4, byteorder="big")
            ff_payload_size = 58 if self.is_fd else 2

        ff_chunk = payload[:ff_payload_size]
        ff_frame = self._build_frame(ff_header + ff_chunk, is_fd=self.is_fd)
        await self._send_with_n_as(ff_frame)

        bytes_sent = len(ff_chunk)
        seq_num = 1
        wft_count = 0
        max_cf_chunk = 63 if self.is_fd else 7

        # 3. Consecutive Frames Loop
        while bytes_sent < data_len:
            fc_frame = await self._await_flow_control()
            fs = fc_frame.data[0] & 0x0F

            if fs == FS_OVERFLOW:
                raise IsoTpBufferOverflowError(
                    "Receiver reported buffer overflow (FlowStatus.OVERFLOW)",
                    requested_length=data_len,
                )
            elif fs == FS_WAIT:
                wft_count += 1
                if wft_count > self.wft_max:
                    raise IsoTpTimeoutError(
                        f"WFTmax limit exceeded: received {wft_count} consecutive WAIT frames (limit={self.wft_max})",
                        timeout_type="N_Bs",
                        elapsed_ms=float(wft_count * 1000.0),
                        limit_ms=float(self.wft_max * 1000.0),
                        details={"wft_count": wft_count, "wft_max": self.wft_max},
                    )
                continue
            elif fs == FS_CTS:
                wft_count = 0
                bs = fc_frame.data[1]
                st_min = fc_frame.data[2]

                block_count = 0
                while bytes_sent < data_len:
                    await self._apply_st_min(st_min)

                    chunk = payload[bytes_sent : bytes_sent + max_cf_chunk]
                    cf_raw = bytes([(PCI_CONSECUTIVE_FRAME << 4) | (seq_num & 0x0F)]) + chunk
                    cf_frame = self._build_frame(cf_raw, is_fd=self.is_fd)
                    await self._send_with_n_as(cf_frame)

                    bytes_sent += len(chunk)
                    seq_num = (seq_num + 1) & 0x0F
                    block_count += 1

                    if bs > 0 and block_count >= bs and bytes_sent < data_len:
                        break
            else:
                raise IsoTpFlowControlError(
                    f"Invalid FlowStatus code received: 0x{fs:X}",
                    flow_status=fs,
                    reason="INVALID_FLOW_STATUS",
                    details={"raw_byte": fc_frame.data[0]},
                )


# ============================================================================
# Asynchronous ISO-TP Receiver State Machine
# ============================================================================


class IsoTpReceiver:
    """Asynchronous ISO 15765-2 DoCAN Receiver State Machine."""

    def __init__(
        self,
        tx_port: TxPort,
        rx_sub: RxSubscription,
        tx_id: int,
        rx_id: int,
        channel_id: str = "uds_ch0",
        is_fd: bool = False,
        block_size: int = 0,
        st_min: int = 0,
        pad_byte: int | None = 0xCC,
        clock: ClockProvider | None = None,
        max_buffer_size: int = 1048576,
        n_cr_timeout_s: float = 1.0,
    ) -> None:
        self.tx_port = tx_port
        self.rx_sub = rx_sub
        self.tx_id = tx_id
        self.rx_id = rx_id
        self.channel_id = channel_id
        self.is_fd = is_fd
        self.block_size = block_size
        self.st_min = st_min
        self.pad_byte = pad_byte
        self.clock: ClockProvider = clock or SystemClockProvider()
        self.max_buffer_size = max_buffer_size
        self.n_cr_timeout_s = n_cr_timeout_s

    def _build_fc_frame(self, flow_status: int) -> CanFrame:
        """Construct Flow Control frame."""
        fc_payload = bytearray(8)
        fc_payload[0] = (PCI_FLOW_CONTROL << 4) | (flow_status & 0x0F)
        fc_payload[1] = self.block_size & 0xFF
        fc_payload[2] = self.st_min & 0xFF
        pad = self.pad_byte if self.pad_byte is not None else 0xCC
        for i in range(3, 8):
            fc_payload[i] = pad

        return CanFrame.create(
            channel_id=self.channel_id,
            arbitration_id=self.tx_id,
            data=bytes(fc_payload),
            is_extended=self.tx_id > 0x7FF,
            is_fd=self.is_fd,
            direction="tx",
        )

    async def receive(self, timeout_s: float | None = None) -> bytes:
        """Receive a complete ISO-TP message (Single Frame or reassembled Multi-Frame)."""
        start_time = self.clock.now_monotonic()
        frame: CanFrame | None = None

        while True:
            if frame is None:
                if timeout_s is not None:
                    elapsed = self.clock.now_monotonic() - start_time
                    remaining = timeout_s - elapsed
                    if remaining <= 0:
                        raise TimeoutError(f"Timeout ({timeout_s:.2f}s) waiting for ISO-TP message")
                    frame = await self.rx_sub.recv(timeout_s=remaining)
                else:
                    frame = await self.rx_sub.recv(timeout_s=None)

            if frame is None:
                raise TimeoutError("Timeout waiting for ISO-TP message")

            if frame.arbitration_id != self.rx_id or len(frame.data) < 2:
                frame = None
                continue

            pci_type = frame.data[0] >> 4

            # --------------------------------------------------------------
            # 1. Single Frame (SF)
            # --------------------------------------------------------------
            if pci_type == PCI_SINGLE_FRAME:
                if (frame.data[0] & 0x0F) == 0:
                    if not self.is_fd and not frame.is_fd:
                        raise IsoTpInvalidPduError(
                            "Classic CAN Single Frame with SF_DL=0 is rejected",
                            pci_type=PCI_SINGLE_FRAME,
                            raw_data=frame.data,
                        )
                    # CAN-FD Extended SF
                    if len(frame.data) < 2:
                        raise IsoTpInvalidPduError(
                            "Malformed CAN-FD Extended SF header",
                            pci_type=PCI_SINGLE_FRAME,
                            raw_data=frame.data,
                        )
                    sf_len = frame.data[1]
                    if sf_len == 0 or sf_len > 62 or sf_len > (len(frame.data) - 2):
                        raise IsoTpInvalidPduError(
                            f"Invalid CAN-FD SF length {sf_len}",
                            pci_type=PCI_SINGLE_FRAME,
                            raw_data=frame.data,
                        )
                    return bytes(frame.data[2 : 2 + sf_len])
                else:
                    # Classic SF
                    sf_len = frame.data[0] & 0x0F
                    if sf_len > 7 or sf_len > (len(frame.data) - 1):
                        raise IsoTpInvalidPduError(
                            f"Invalid Classic SF length {sf_len}",
                            pci_type=PCI_SINGLE_FRAME,
                            raw_data=frame.data,
                        )
                    return bytes(frame.data[1 : 1 + sf_len])

            # --------------------------------------------------------------
            # 2. First Frame (FF)
            # --------------------------------------------------------------
            if pci_type == PCI_FIRST_FRAME:
                if len(frame.data) >= 6 and frame.data[0] == 0x10 and frame.data[1] == 0x00:
                    # Extended 32-bit First Frame
                    total_len = int.from_bytes(frame.data[2:6], byteorder="big")
                    if total_len <= 4095:
                        raise IsoTpInvalidPduError(
                            f"Extended First Frame length ({total_len}) must be > 4095",
                            pci_type=PCI_FIRST_FRAME,
                            raw_data=frame.data,
                        )
                    header_len = 6
                else:
                    total_len = ((frame.data[0] & 0x0F) << 8) | frame.data[1]
                    if total_len < 8 and not self.is_fd and not frame.is_fd:
                        raise IsoTpInvalidPduError(
                            f"Standard First Frame length ({total_len}) must be >= 8",
                            pci_type=PCI_FIRST_FRAME,
                            raw_data=frame.data,
                        )
                    header_len = 2

                # Buffer Overflow check
                if total_len > self.max_buffer_size:
                    fc_ovfl = self._build_fc_frame(FS_OVERFLOW)
                    await self.tx_port.send(fc_ovfl)
                    raise IsoTpBufferOverflowError(
                        f"Requested payload length {total_len} exceeds max buffer capacity {self.max_buffer_size}",
                        requested_length=total_len,
                        max_buffer_size=self.max_buffer_size,
                    )

                first_chunk = frame.data[header_len:]
                if len(first_chunk) > total_len:
                    first_chunk = first_chunk[:total_len]

                buffer = bytearray(first_chunk)

                # If First Frame carries full payload (e.g. 62B FD)
                if len(buffer) >= total_len:
                    return bytes(buffer[:total_len])

                # Emit Flow Control CTS
                fc_cts = self._build_fc_frame(FS_CTS)
                await self.tx_port.send(fc_cts)

                expected_sn = 1
                block_count = 0

                # Consecutive Frames loop
                while len(buffer) < total_len:
                    cf_frame = await self.rx_sub.recv(timeout_s=self.n_cr_timeout_s)
                    if cf_frame is None:
                        raise IsoTpTimeoutError(
                            f"N_Cr timeout ({self.n_cr_timeout_s * 1000:.0f}ms) awaiting Consecutive Frame",
                            timeout_type="N_Cr",
                            elapsed_ms=self.n_cr_timeout_s * 1000.0,
                            limit_ms=self.n_cr_timeout_s * 1000.0,
                        )

                    if cf_frame.arbitration_id != self.rx_id or len(cf_frame.data) < 1:
                        continue

                    cf_pci = cf_frame.data[0] >> 4

                    # Handle unexpected session reset frames
                    if cf_pci in (PCI_SINGLE_FRAME, PCI_FIRST_FRAME):
                        # Reset session to the new Single Frame or First Frame
                        frame = cf_frame
                        break  # Break out to re-process in outer loop

                    if cf_pci != PCI_CONSECUTIVE_FRAME:
                        continue

                    sn = cf_frame.data[0] & 0x0F
                    if sn != expected_sn:
                        raise IsoTpSequenceError(expected_sn=expected_sn, actual_sn=sn)

                    needed = total_len - len(buffer)
                    avail = len(cf_frame.data) - 1
                    c_len = min(needed, avail)
                    buffer.extend(cf_frame.data[1 : 1 + c_len])

                    expected_sn = (expected_sn + 1) & 0x0F
                    block_count += 1

                    if len(buffer) >= total_len:
                        return bytes(buffer[:total_len])

                    if self.block_size > 0 and block_count >= self.block_size:
                        fc_cts = self._build_fc_frame(FS_CTS)
                        await self.tx_port.send(fc_cts)
                        block_count = 0

                continue

            # Frame was neither SF nor FF (e.g. orphaned CF or FC)
            frame = None
