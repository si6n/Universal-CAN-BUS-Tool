"""SAE J1939-21 Transport Protocol (BAM & RTS/CTS CMDT) Engine.

Complies with SAE J1939-21 and MASTER_PLAN.md Section 4.1.
Uses PGN 60416 (0xEC00) for TP.CM and PGN 60160 (0xEB00) for TP.DT.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import ClassVar

from src.core.contracts.ports import ClockProvider
from src.core.exceptions import (
    J1939SequenceError,
    J1939SessionCollisionError,
    J1939TpAbortError,
    J1939TpError,
    J1939TpTimeoutError,
)
from src.core.logging import get_logger
from src.core.models.can_frame import CanFrame

logger = get_logger("protocols.j1939.transport")

PGN_TP_CM: int = 60416  # 0xEC00 (Connection Management)
PGN_TP_DT: int = 60160  # 0xEB00 (Data Transfer)

# TP.CM Control Bytes
TP_CTRL_RTS: int = 0x10
TP_CTRL_CTS: int = 0x11
TP_CTRL_ACK: int = 0x13
TP_CTRL_BAM: int = 0x20
TP_CTRL_ABORT: int = 0xFF

# TP.Conn_Abort Reason Codes (SAE J1939-21 Section 5.10.3)
ABORT_REASON_SEQUENCE_ERROR: int = 0x01
ABORT_REASON_SESSION_COLLISION: int = 0x02
ABORT_REASON_TIMEOUT: int = 0x03
ABORT_REASON_UNEXPECTED_CONTROL: int = 0x04


@dataclass(slots=True)
class ReassemblySession:
    """Active multi-packet reassembly session."""

    source_address: int
    destination_address: int
    target_pgn: int
    total_bytes: int
    total_packets: int
    is_bam: bool
    expected_sequence: int = 1
    received_bytes: bytearray = field(default_factory=bytearray)
    last_activity_time: float = field(default_factory=time.monotonic)
    channel_id: str = "j1939_ch0"

    @property
    def expected_pgn(self) -> int:
        """Alias for target_pgn to conform with expected_pgn naming."""
        return self.target_pgn


@dataclass(slots=True)
class CompletedMessage:
    """Successfully reassembled multi-packet J1939 message."""

    source_address: int
    destination_address: int
    pgn: int
    data: bytes
    timestamp_ns: int
    channel_id: str


class J1939TransportProtocol:
    """SAE J1939-21 Transport Protocol Engine managing BAM & CMDT sessions."""

    # Timeouts in seconds (SAE J1939-21)
    T1_TIMEOUT_SEC: ClassVar[float] = 0.750  # 750 ms (Time between packets)
    T2_TIMEOUT_SEC: ClassVar[float] = 1.250  # 1250 ms (Time to CTS)
    T3_TIMEOUT_SEC: ClassVar[float] = 1.250  # 1250 ms (Time to EndOfMsgACK)
    T4_TIMEOUT_SEC: ClassVar[float] = 1.050  # 1050 ms (Time to hold connection)
    MAX_CONCURRENT_SESSIONS: ClassVar[int] = 512

    def __init__(
        self,
        my_address: int = 0xF9,
        channel_id: str = "j1939_ch0",
        clock: ClockProvider | None = None,
    ) -> None:
        self.my_address = my_address
        self.channel_id = channel_id
        self.clock = clock
        # Session storage strictly keyed by (source_address, destination_address)
        self._rx_sessions: dict[tuple[int, int], ReassemblySession] = {}

    def _get_now(self) -> float:
        """Return current monotonic time in seconds."""
        if self.clock is not None:
            return self.clock.now_monotonic()
        return time.monotonic()

    def _reap_stale_sessions(self, now: float | None = None) -> None:
        """Reap inactive reassembly sessions exceeding T1 timeout."""
        curr_time = now if now is not None else self._get_now()
        expired = [
            key
            for key, sess in self._rx_sessions.items()
            if (curr_time - sess.last_activity_time) > self.T1_TIMEOUT_SEC
        ]
        for key in expired:
            self._rx_sessions.pop(key, None)

    def handle_rx_frame(self, frame: CanFrame) -> tuple[CompletedMessage | None, CanFrame | None]:
        """Process incoming frame according to SAE J1939-21 PDU format rules."""
        if not frame.is_extended or len(frame.data) < 8:
            return None, None

        # 29-bit CAN ID decomposition
        dp = (frame.arbitration_id >> 24) & 0x01
        pf = (frame.arbitration_id >> 16) & 0xFF
        ps = (frame.arbitration_id >> 8) & 0xFF
        sa = frame.arbitration_id & 0xFF

        if pf < 240:
            # PDU1 format (Point-to-Point): Destination Address is PS
            da = ps
            pgn = (dp << 16) | (pf << 8)
        else:
            # PDU2 format (Broadcast): DA is Global (255)
            da = 255
            pgn = (dp << 16) | (pf << 8) | ps

        # Check for TP.CM (PGN 60416 / 0xEC00)
        if pgn == PGN_TP_CM:
            return self._handle_tp_cm(frame, sa, da)

        # Check for TP.DT (PGN 60160 / 0xEB00)
        if pgn == PGN_TP_DT:
            return self._handle_tp_dt(frame, sa, da)

        return None, None

    def handle_frame(self, frame: CanFrame) -> tuple[CompletedMessage | None, CanFrame | None]:
        """Alias for handle_rx_frame."""
        return self.handle_rx_frame(frame)

    def _handle_tp_cm(
        self, frame: CanFrame, sa: int, da: int
    ) -> tuple[CompletedMessage | None, CanFrame | None]:
        ctrl_byte = frame.data[0]
        total_bytes = int.from_bytes(frame.data[1:3], byteorder="little")
        total_packets = frame.data[3]
        target_pgn = int.from_bytes(frame.data[5:8], byteorder="little")

        # Session key strictly by (source_address, destination_address)
        session_key = (sa, da)

        # Validate SAE J1939-21 TP limits: max 1785 bytes, packets must match declared bytes
        if ctrl_byte in {TP_CTRL_BAM, TP_CTRL_RTS}:
            if not (1 <= total_bytes <= 1785) or total_packets == 0:
                logger.warning(
                    "Rejected malformed J1939 TP.CM length",
                    extra={"total_bytes": total_bytes, "total_packets": total_packets, "sa": sa},
                )
                return None, None
            expected_packets = (total_bytes + 6) // 7
            if total_packets != expected_packets:
                logger.warning(
                    "Rejected J1939 TP.CM packet count mismatch",
                    extra={"declared": total_packets, "expected": expected_packets, "sa": sa},
                )
                return None, None

        self._reap_stale_sessions()

        if ctrl_byte == TP_CTRL_BAM:
            # Broadcast Announce Message (DA == 255)
            if len(self._rx_sessions) >= self.MAX_CONCURRENT_SESSIONS and session_key not in self._rx_sessions:
                oldest_key = min(self._rx_sessions.keys(), key=lambda k: self._rx_sessions[k].last_activity_time)
                self._rx_sessions.pop(oldest_key, None)

            logger.debug(
                "Received J1939 TP.CM_BAM",
                extra={"sa": sa, "target_pgn": hex(target_pgn), "bytes": total_bytes, "packets": total_packets},
            )
            self._rx_sessions[session_key] = ReassemblySession(
                source_address=sa,
                destination_address=da,
                target_pgn=target_pgn,
                total_bytes=total_bytes,
                total_packets=total_packets,
                is_bam=True,
                expected_sequence=1,
                last_activity_time=self._get_now(),
                channel_id=frame.channel_id,
            )
            return None, None

        if ctrl_byte == TP_CTRL_RTS:
            # Request To Send (Point-to-Point CMDT)
            # 1. Reject RTS addressed to global broadcast address DA == 255 (0xFF)
            if da == 255 or da != self.my_address:
                logger.warning(
                    "Rejected J1939 TP.CM_RTS with invalid destination address",
                    extra={"da": da, "my_address": self.my_address, "sa": sa},
                )
                return None, None

            # 2. Check for active session collision on (SA, DA)
            existing_session = self._rx_sessions.get(session_key)
            abort_frame: CanFrame | None = None
            if existing_session is not None:
                logger.warning(
                    "J1939 TP session collision detected on (SA, DA)",
                    extra={
                        "sa": sa,
                        "da": da,
                        "old_pgn": hex(existing_session.target_pgn),
                        "new_pgn": hex(target_pgn),
                    },
                )
                # Abort existing session with reason=2 (Session Collision)
                abort_frame = self._create_abort_frame(
                    existing_session, reason=ABORT_REASON_SESSION_COLLISION
                )
                self._rx_sessions.pop(session_key, None)

            # Capacity management
            if len(self._rx_sessions) >= self.MAX_CONCURRENT_SESSIONS and session_key not in self._rx_sessions:
                oldest_key = min(self._rx_sessions.keys(), key=lambda k: self._rx_sessions[k].last_activity_time)
                self._rx_sessions.pop(oldest_key, None)

            # Establish new session with new expected_pgn
            new_session = ReassemblySession(
                source_address=sa,
                destination_address=da,
                target_pgn=target_pgn,
                total_bytes=total_bytes,
                total_packets=total_packets,
                is_bam=False,
                expected_sequence=1,
                last_activity_time=self._get_now(),
                channel_id=frame.channel_id,
            )
            self._rx_sessions[session_key] = new_session

            # If collision occurred, emit abort frame for the old session
            if abort_frame is not None:
                return None, abort_frame

            # Otherwise emit affirmative TP.CM_CTS for the new session
            cts_frame = self._create_cts_frame(new_session)
            return None, cts_frame

        if ctrl_byte == TP_CTRL_ABORT:
            # Peer Connection Abort
            logger.warning(
                "Received J1939 TP.Conn_Abort",
                extra={"sa": sa, "da": da, "target_pgn": hex(target_pgn), "reason": frame.data[1]},
            )
            self._rx_sessions.pop(session_key, None)
            return None, None

        return None, None

    def _handle_tp_dt(
        self, frame: CanFrame, sa: int, da: int
    ) -> tuple[CompletedMessage | None, CanFrame | None]:
        seq_num = frame.data[0]
        payload = frame.data[1:8]

        # Session lookup strictly keyed by (source_address, destination_address)
        session_key = (sa, da)
        session = self._rx_sessions.get(session_key)

        if session is None:
            return None, None

        now = self._get_now()

        # Check T1 timeout (750 ms)
        if (now - session.last_activity_time) > self.T1_TIMEOUT_SEC:
            logger.warning(
                "J1939 TP.DT session timeout (T1 exceeded)",
                extra={"sa": sa, "da": da, "target_pgn": hex(session.target_pgn)},
            )
            self._rx_sessions.pop(session_key, None)
            abort_frame = self._create_abort_frame(session, reason=ABORT_REASON_TIMEOUT)
            return None, abort_frame

        # Check sequence order
        if seq_num != session.expected_sequence:
            logger.warning(
                "J1939 TP.DT out of order sequence",
                extra={
                    "expected": session.expected_sequence,
                    "got": seq_num,
                    "sa": sa,
                    "da": da,
                    "target_pgn": hex(session.target_pgn),
                },
            )
            self._rx_sessions.pop(session_key, None)
            abort_frame = self._create_abort_frame(session, reason=ABORT_REASON_SEQUENCE_ERROR)
            return None, abort_frame

        # Append payload data
        bytes_needed = session.total_bytes - len(session.received_bytes)
        session.received_bytes.extend(payload[:bytes_needed])
        session.expected_sequence += 1
        session.last_activity_time = now

        # Check if transfer is complete
        if session.expected_sequence > session.total_packets or len(session.received_bytes) >= session.total_bytes:
            completed_data = bytes(session.received_bytes[: session.total_bytes])
            completed_msg = CompletedMessage(
                source_address=session.source_address,
                destination_address=session.destination_address,
                pgn=session.target_pgn,
                data=completed_data,
                timestamp_ns=frame.timestamp_ns,
                channel_id=frame.channel_id,
            )

            resp_frame = None
            if not session.is_bam and session.destination_address == self.my_address:
                # Send TP.CM_EndOfMsgACK
                ack_data = bytearray(8)
                ack_data[0] = TP_CTRL_ACK
                ack_data[1:3] = session.total_bytes.to_bytes(2, byteorder="little")
                ack_data[3] = session.total_packets
                ack_data[4] = 0xFF
                ack_data[5:8] = session.target_pgn.to_bytes(3, byteorder="little")

                can_id = 0x18EC0000 | (session.source_address << 8) | (self.my_address & 0xFF)
                resp_frame = CanFrame.create(
                    channel_id=frame.channel_id,
                    arbitration_id=can_id,
                    data=bytes(ack_data),
                    is_extended=True,
                    direction="tx",
                )

            self._rx_sessions.pop(session_key, None)
            return completed_msg, resp_frame

        return None, None

    def _create_cts_frame(self, session: ReassemblySession) -> CanFrame:
        """Construct standard J1939 TP.CM_CTS frame (PGN 60416 / 0xEC00 with Control Byte 0x11)."""
        cts_data = bytearray(8)
        cts_data[0] = TP_CTRL_CTS
        cts_data[1] = session.total_packets  # Number of packets allowed
        cts_data[2] = session.expected_sequence  # Next sequence number expected (1)
        cts_data[3] = 0xFF
        cts_data[4] = 0xFF
        cts_data[5:8] = session.target_pgn.to_bytes(3, byteorder="little")

        can_id = 0x18EC0000 | (session.source_address << 8) | (self.my_address & 0xFF)
        return CanFrame.create(
            channel_id=session.channel_id,
            arbitration_id=can_id,
            data=bytes(cts_data),
            is_extended=True,
            direction="tx",
        )

    def _create_abort_frame(self, session: ReassemblySession, reason: int = 0x01) -> CanFrame | None:
        """Construct standard J1939 TP.Conn_Abort frame (PGN 60416 / 0xEC00 with Control Byte 0xFF)."""
        if session.is_bam:
            return None  # Do not send abort for global broadcast

        abort_data = bytearray(8)
        abort_data[0] = TP_CTRL_ABORT
        abort_data[1] = reason
        abort_data[2:5] = b"\xff\xff\xff"
        abort_data[5:8] = session.target_pgn.to_bytes(3, byteorder="little")

        can_id = 0x18EC0000 | (session.source_address << 8) | (self.my_address & 0xFF)
        return CanFrame.create(
            channel_id=session.channel_id,
            arbitration_id=can_id,
            data=bytes(abort_data),
            is_extended=True,
            direction="tx",
        )

    def start_tp_bam(self, pgn: int, data: bytes, channel_id: str | None = None) -> list[CanFrame]:
        """Segment data into J1939 BAM broadcast frames (TP.CM_BAM followed by TP.DT packets)."""
        if not (1 <= len(data) <= 1785):
            raise ValueError(f"J1939 TP data length must be 1..1785 bytes, got {len(data)}")

        ch = channel_id or self.channel_id
        total_bytes = len(data)
        total_packets = (total_bytes + 6) // 7

        # 1. TP.CM_BAM frame (DA = 255, SA = my_address)
        bam_data = bytearray(8)
        bam_data[0] = TP_CTRL_BAM
        bam_data[1:3] = total_bytes.to_bytes(2, byteorder="little")
        bam_data[3] = total_packets
        bam_data[4] = 0xFF
        bam_data[5:8] = pgn.to_bytes(3, byteorder="little")

        can_id_cm = 0x18ECFF00 | (self.my_address & 0xFF)
        frames: list[CanFrame] = [
            CanFrame.create(
                channel_id=ch,
                arbitration_id=can_id_cm,
                data=bytes(bam_data),
                is_extended=True,
                direction="tx",
            )
        ]

        # 2. TP.DT packets
        can_id_dt = 0x18EBFF00 | (self.my_address & 0xFF)
        for seq in range(1, total_packets + 1):
            chunk = data[(seq - 1) * 7 : seq * 7]
            dt_data = bytearray(8)
            dt_data[0] = seq
            dt_data[1 : 1 + len(chunk)] = chunk
            for i in range(1 + len(chunk), 8):
                dt_data[i] = 0xFF
            frames.append(
                CanFrame.create(
                    channel_id=ch,
                    arbitration_id=can_id_dt,
                    data=bytes(dt_data),
                    is_extended=True,
                    direction="tx",
                )
            )

        return frames

    def start_tp_cm_dt(
        self, target_address: int, pgn: int, data: bytes, channel_id: str | None = None
    ) -> list[CanFrame]:
        """Segment data into J1939 CMDT peer-to-peer frames (TP.CM_RTS followed by TP.DT packets)."""
        if not (1 <= len(data) <= 1785):
            raise ValueError(f"J1939 TP data length must be 1..1785 bytes, got {len(data)}")

        ch = channel_id or self.channel_id
        total_bytes = len(data)
        total_packets = (total_bytes + 6) // 7

        # 1. TP.CM_RTS frame (DA = target_address, SA = my_address)
        rts_data = bytearray(8)
        rts_data[0] = TP_CTRL_RTS
        rts_data[1:3] = total_bytes.to_bytes(2, byteorder="little")
        rts_data[3] = total_packets
        rts_data[4] = 0xFF
        rts_data[5:8] = pgn.to_bytes(3, byteorder="little")

        can_id_cm = 0x18EC0000 | ((target_address & 0xFF) << 8) | (self.my_address & 0xFF)
        frames: list[CanFrame] = [
            CanFrame.create(
                channel_id=ch,
                arbitration_id=can_id_cm,
                data=bytes(rts_data),
                is_extended=True,
                direction="tx",
            )
        ]

        # 2. TP.DT packets (DA = target_address, SA = my_address)
        can_id_dt = 0x18EB0000 | ((target_address & 0xFF) << 8) | (self.my_address & 0xFF)
        for seq in range(1, total_packets + 1):
            chunk = data[(seq - 1) * 7 : seq * 7]
            dt_data = bytearray(8)
            dt_data[0] = seq
            dt_data[1 : 1 + len(chunk)] = chunk
            for i in range(1 + len(chunk), 8):
                dt_data[i] = 0xFF
            frames.append(
                CanFrame.create(
                    channel_id=ch,
                    arbitration_id=can_id_dt,
                    data=bytes(dt_data),
                    is_extended=True,
                    direction="tx",
                )
            )

        return frames


__all__ = [
    "ABORT_REASON_SEQUENCE_ERROR",
    "ABORT_REASON_SESSION_COLLISION",
    "ABORT_REASON_TIMEOUT",
    "ABORT_REASON_UNEXPECTED_CONTROL",
    "CompletedMessage",
    "J1939SequenceError",
    "J1939SessionCollisionError",
    "J1939TpAbortError",
    "J1939TpError",
    "J1939TpTimeoutError",
    "J1939TransportProtocol",
    "PGN_TP_CM",
    "PGN_TP_DT",
    "ReassemblySession",
    "TP_CTRL_ABORT",
    "TP_CTRL_ACK",
    "TP_CTRL_BAM",
    "TP_CTRL_CTS",
    "TP_CTRL_RTS",
]
