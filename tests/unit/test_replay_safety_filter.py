"""Unit tests for Replay Safety Filter enforcing live-bus playback protection."""

from __future__ import annotations

from src.core.models.can_frame import CanFrame
from src.hal.replay.safety_filter import ReplaySafetyFilter


def test_replay_safety_filter_passes_telemetry_frames() -> None:
    filter_engine = ReplaySafetyFilter()

    # Normal Engine Speed broadcast (PGN 61444 / 0xF004) -> 0x0CF00400
    frame_eec1 = CanFrame.create(
        channel_id="ch0",
        arbitration_id=0x0CF00400,
        data=b"\x00\x00\x00\x00\x10\x00\x00\x00",
        is_extended=True,
    )
    is_safe, reason = filter_engine.is_frame_safe(frame_eec1)
    assert is_safe is True
    assert reason == ""
    assert filter_engine.filter_frame(frame_eec1) is not None


def test_replay_safety_filter_blocks_j1939_address_claim() -> None:
    filter_engine = ReplaySafetyFilter()

    # J1939 Address Claimed (PGN 60928 / 0xEE00) -> 0x18EEFF00
    frame_claim = CanFrame.create(
        channel_id="ch0",
        arbitration_id=0x18EEFF00,
        data=b"\x01\x02\x03\x04\x05\x06\x07\x08",
        is_extended=True,
    )
    is_safe, reason = filter_engine.is_frame_safe(frame_claim)
    assert is_safe is False
    assert "BLOCKED_J1939_PGN" in reason
    assert filter_engine.filter_frame(frame_claim) is None
    assert filter_engine.total_blocked == 1


def test_replay_safety_filter_blocks_diagnostic_ecu_reset_and_writes() -> None:
    filter_engine = ReplaySafetyFilter()

    # 11-bit UDS Request (0x7E0) with SID 0x11 (ECU Reset): [0x02, 0x11, 0x01, 0, 0, 0, 0, 0]
    frame_reset = CanFrame.create(
        channel_id="ch0",
        arbitration_id=0x7E0,
        data=b"\x02\x11\x01\x00\x00\x00\x00\x00",
        is_extended=False,
    )
    assert filter_engine.filter_frame(frame_reset) is None

    # 11-bit UDS Request (0x7E0) with SID 0x2E (WriteData): [0x04, 0x2E, 0xF1, 0x90, 0xAA, 0, 0, 0]
    frame_write = CanFrame.create(
        channel_id="ch0",
        arbitration_id=0x7E0,
        data=b"\x04\x2e\xf1\x90\xaa\x00\x00\x00",
        is_extended=False,
    )
    assert filter_engine.filter_frame(frame_write) is None

    # 29-bit UDS Request (0x18DA00F1) with SID 0x31 (RoutineControl / Actuator test)
    frame_routine = CanFrame.create(
        channel_id="ch0",
        arbitration_id=0x18DA00F1,
        data=b"\x04\x31\x01\x02\x03\x00\x00\x00",
        is_extended=True,
    )
    assert filter_engine.filter_frame(frame_routine) is None
    assert filter_engine.total_blocked == 3


def test_replay_safety_filter_sequence() -> None:
    filter_engine = ReplaySafetyFilter()

    frames = [
        CanFrame.create(channel_id="c0", arbitration_id=0x0CF00400, data=b"\x00", is_extended=True),  # Safe
        CanFrame.create(channel_id="c0", arbitration_id=0x18EEFF00, data=b"\x00", is_extended=True),  # Unsafe Claim
        CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"\x02\x11\x01", is_extended=False),  # Unsafe Reset
        CanFrame.create(channel_id="c0", arbitration_id=0x100, data=b"\x12\x34", is_extended=False),  # Safe
    ]

    safe_frames = filter_engine.filter_sequence(frames)
    assert len(safe_frames) == 2
    assert safe_frames[0].arbitration_id == 0x0CF00400
    assert safe_frames[1].arbitration_id == 0x100
