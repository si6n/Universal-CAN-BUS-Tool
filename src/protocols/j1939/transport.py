"""SAE J1939-21 Transport Protocol (BAM & RTS/CTS CMDT) Engine.

Complies with SAE J1939-21 and MASTER_PLAN.md Section 4.1.
Uses PGN 60416 (0xEC00) for TP.CM and PGN 60160 (0xEB00) for TP.DT.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import ClassVar

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
    T1_TIMEOUT_SEC: ClassVar[float] = 0.750  # 750 ms
    T2_TIMEOUT_SEC: ClassVar[float] = 1.250  # 1250 ms
    T3_TIMEOUT_SEC: ClassVar[float] = 1.250  # 1250 ms
    MAX_CONCURRENT_SESSIONS: ClassVar[int] = 512

    def __init__(self, my_address: int = 0xF9, channel_id: str = "j1939_ch0") -> None:
        self.my_address = my_address
        self.channel_id = channel_id
        self._rx_sessions: dict[tuple[int, int, int], ReassemblySession] = {}

    def _reap_stale_sessions(self, now: float | None = None) -> None:
        """Reap inactive reassembly sessions exceeding T1 timeout."""
        curr_time = now if now is not None else time.monotonic()
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

    def _handle_tp_cm(self, frame: CanFrame, sa: int, da: int) -> tuple[CompletedMessage | None, CanFrame | None]:
        ctrl_byte = frame.data[0]
        total_bytes = int.from_bytes(frame.data[1:3], byteorder="little")
        total_packets = frame.data[3]
        target_pgn = int.from_bytes(frame.data[5:8], byteorder="little")

        # Session key: (SA, Target_PGN, DA)
        session_key = (sa, target_pgn, da)

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
        if len(self._rx_sessions) >= self.MAX_CONCURRENT_SESSIONS and session_key not in self._rx_sessions:
            oldest_key = min(self._rx_sessions.keys(), key=lambda k: self._rx_sessions[k].last_activity_time)
            self._rx_sessions.pop(oldest_key, None)

        if ctrl_byte == TP_CTRL_BAM:
            # Broadcast Announce Message
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
                channel_id=frame.channel_id,
            )
            return None, None

        if ctrl_byte == TP_CTRL_RTS:
            # Request To Send (Point-to-Point CMDT)
            if da != self.my_address and da != 255:
                return None, None

            logger.debug(
                "Received J1939 TP.CM_RTS",
                extra={"sa": sa, "target_pgn": hex(target_pgn), "bytes": total_bytes, "packets": total_packets},
            )
            self._rx_sessions[session_key] = ReassemblySession(
                source_address=sa,
                destination_address=da,
                target_pgn=target_pgn,
                total_bytes=total_bytes,
                total_packets=total_packets,
                is_bam=False,
                channel_id=frame.channel_id,
            )

            # Send TP.CM_CTS (Clear To Send for all packets)
            cts_data = bytearray(8)
            cts_data[0] = TP_CTRL_CTS
            cts_data[1] = total_packets  # Number of packets allowed
            cts_data[2] = 1  # Next sequence number expected
            cts_data[3] = 0xFF
            cts_data[4] = 0xFF
            cts_data[5:8] = target_pgn.to_bytes(3, byteorder="little")

            can_id = 0x18EC0000 | (sa << 8) | (self.my_address & 0xFF)
            cts_frame = CanFrame.create(
                channel_id=frame.channel_id,
                arbitration_id=can_id,
                data=bytes(cts_data),
                is_extended=True,
                direction="tx",
            )
            return None, cts_frame

        if ctrl_byte == TP_CTRL_ABORT:
            # Connection Abort
            logger.warning("Received J1939 TP.Conn_Abort", extra={"sa": sa, "target_pgn": hex(target_pgn)})
            self._rx_sessions.pop(session_key, None)
            return None, None

        return None, None

    def _handle_tp_dt(self, frame: CanFrame, sa: int, da: int) -> tuple[CompletedMessage | None, CanFrame | None]:
        seq_num = frame.data[0]
        payload = frame.data[1:8]

        # Find matching session for this SA and DA
        matching_key = None
        for key, sess in self._rx_sessions.items():
            if sess.source_address == sa and (sess.destination_address == da or sess.is_bam):
                matching_key = key
                break

        if not matching_key:
            return None, None

        session = self._rx_sessions[matching_key]
        now = time.monotonic()

        # Check T1 timeout
        if (now - session.last_activity_time) > self.T1_TIMEOUT_SEC:
            logger.warning(
                "J1939 TP.DT session timeout (T1 exceeded)",
                extra={"sa": sa, "target_pgn": hex(session.target_pgn)},
            )
            self._rx_sessions.pop(matching_key, None)
            abort_frame = self._create_abort_frame(session, reason=0x01)
            return None, abort_frame

        # Check sequence order
        if seq_num != session.expected_sequence:
            logger.warning(
                "J1939 TP.DT Out of order sequence",
                extra={"expected": session.expected_sequence, "got": seq_num},
            )
            self._rx_sessions.pop(matching_key, None)
            abort_frame = self._create_abort_frame(session, reason=0x04)
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

            self._rx_sessions.pop(matching_key, None)
            return completed_msg, resp_frame

        return None, None

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
