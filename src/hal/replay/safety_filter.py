"""Replay Safety Filter protecting live CAN networks from malicious or invalid playback frames.

Complies with Saha Risk Kataloğu v1.2 Sections 21, 41, Risk R-17.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from src.core.logging import get_logger
from src.core.models.can_frame import CanFrame

logger = get_logger("hal.replay.safety_filter")


class ReplaySafetyFilter:
    """Filters unsafe commands (Address Claim, ECU Reset, Diagnostics) from replay streams."""

    # Critical J1939 / NMEA2000 PGNs to block in replay
    BLOCKED_PGNS: ClassVar[set[int]] = {
        0x0EE00,  # 60928: Address Claimed / Cannot Claim
        0x0FED8,  # 65240: Commanded Address
        0x0EA00,  # 59904: Request PGN
        0x0FED3,  # 65235: Diagnostic Message 4 (DM4 - Freeze Frame Clear)
        0x0FED2,  # 65234: Diagnostic Message 5 (DM5 - Diagnostic Readiness)
    }

    # Standard Diagnostic Request Arbitration IDs (11-bit)
    DIAGNOSTIC_11BIT_IDS: ClassVar[set[int]] = {
        0x7DF,  # Functional Broadcast Request
        0x7E0,
        0x7E1,
        0x7E2,
        0x7E3,
        0x7E4,
        0x7E5,
        0x7E6,
        0x7E7,  # Physical Request
    }

    # Prohibited Diagnostic Service Identifiers (UDS SIDs)
    PROHIBITED_UDS_SIDS: ClassVar[set[int]] = {
        0x10,  # Diagnostic Session Control (switching to programming/extended)
        0x11,  # ECU Reset
        0x14,  # Clear Diagnostic Information
        0x27,  # Security Access
        0x28,  # Communication Control
        0x2E,  # Write Data By Identifier
        0x31,  # Routine Control (actuator testing)
        0x34,  # Request Download
        0x36,  # Transfer Data
        0x37,  # Request Transfer Exit
        0x85,  # Control DTC Setting
    }

    def __init__(
        self,
        block_address_claim: bool = True,
        block_diagnostic_write: bool = True,
        block_actuator_routines: bool = True,
        custom_blocked_ids: set[int] | None = None,
    ) -> None:
        self.block_address_claim = block_address_claim
        self.block_diagnostic_write = block_diagnostic_write
        self.block_actuator_routines = block_actuator_routines
        self.custom_blocked_ids = custom_blocked_ids or set()

        self.total_evaluated: int = 0
        self.total_passed: int = 0
        self.total_blocked: int = 0
        self.blocked_reasons: dict[str, int] = {}

    def is_frame_safe(self, frame: CanFrame) -> tuple[bool, str]:
        """Evaluate if a frame is safe to be transmitted onto a CAN bus during replay."""
        self.total_evaluated += 1

        # Check custom blocked IDs
        if frame.arbitration_id in self.custom_blocked_ids:
            return False, f"CUSTOM_BLOCKED_ID: 0x{frame.arbitration_id:08X}"

        # 29-bit Extended Frame Evaluation (J1939 / N2K)
        if frame.is_extended:
            pgn = (frame.arbitration_id >> 8) & 0x3FFFF
            pdu_format = (pgn >> 8) & 0xFF
            masked_pgn = (pgn & 0x3FF00) if pdu_format < 240 else pgn

            if self.block_address_claim and (pgn in self.BLOCKED_PGNS or masked_pgn in self.BLOCKED_PGNS):
                return False, f"BLOCKED_J1939_PGN: {pgn} (0x{pgn:05X})"

            # ISO-TP / UDS over 29-bit (e.g. 0x18DAxxF1)
            if pdu_format in {0xDA, 0xDB} and len(frame.data) >= 2:
                # Single Frame (SF) or First Frame (FF) inspection
                pci_type = (frame.data[0] >> 4) & 0x0F
                sid = (
                    frame.data[1]
                    if pci_type == 0x0
                    else (frame.data[2] if pci_type == 0x1 and len(frame.data) >= 3 else None)
                )
                if sid is not None and sid in self.PROHIBITED_UDS_SIDS:
                    return False, f"PROHIBITED_29BIT_UDS_SID: 0x{sid:02X}"

        # 11-bit Standard Frame Evaluation (OBD-II / UDS)
        else:
            if self.block_diagnostic_write and frame.arbitration_id in self.DIAGNOSTIC_11BIT_IDS:
                if len(frame.data) >= 2:
                    pci_type = (frame.data[0] >> 4) & 0x0F
                    sid = (
                        frame.data[1]
                        if pci_type == 0x0
                        else (frame.data[2] if pci_type == 0x1 and len(frame.data) >= 3 else None)
                    )
                    if sid is not None and sid in self.PROHIBITED_UDS_SIDS:
                        return False, f"PROHIBITED_11BIT_UDS_SID: 0x{sid:02X}"

        return True, ""

    def filter_frame(self, frame: CanFrame) -> CanFrame | None:
        """Return frame if safe, or None if blocked by safety policy."""
        is_safe, reason = self.is_frame_safe(frame)
        if not is_safe:
            self.total_blocked += 1
            self.blocked_reasons[reason] = self.blocked_reasons.get(reason, 0) + 1
            logger.warning(
                "Replay Safety Filter BLOCKED unsafe frame",
                extra={
                    "arbitration_id": hex(frame.arbitration_id),
                    "reason": reason,
                    "data": frame.data.hex(),
                },
            )
            return None

        self.total_passed += 1
        return frame

    def filter_sequence(self, frames: Sequence[CanFrame]) -> list[CanFrame]:
        """Filter an entire sequence of frames, removing unsafe entries."""
        safe_frames: list[CanFrame] = []
        for frame in frames:
            filtered = self.filter_frame(frame)
            if filtered is not None:
                safe_frames.append(filtered)
        return safe_frames
