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


def test_dm4_dm5_correct_pgn_values_blocked() -> None:
    """D4: DM4=65229 / DM5=65230 must be blocked (old table blocked the wrong
    PGNs — 65235/65234 — and so never stopped the freeze-frame clear path)."""
    f = ReplaySafetyFilter()

    dm4 = CanFrame.create(channel_id="can0", arbitration_id=0x18FED500, data=b"\x00" * 8, is_extended=True)
    dm5 = CanFrame.create(channel_id="can0", arbitration_id=0x18FED600, data=b"\x00" * 8, is_extended=True)
    dm11 = CanFrame.create(channel_id="can0", arbitration_id=0x18FEDA00, data=b"\x00" * 8, is_extended=True)

    ok4, r4 = f.is_frame_safe(dm4)
    ok5, r5 = f.is_frame_safe(dm5)
    ok11, r11 = f.is_frame_safe(dm11)
    assert not ok4 and "BLOCKED_J1939_PGN" in r4
    assert not ok5 and "BLOCKED_J1939_PGN" in r5
    assert not ok11 and "BLOCKED_J1939_PGN" in r11


def test_transport_tunnel_pgn_blocked_by_default() -> None:
    """D5: TP.CM/TP.DT replay can tunnel any blocked payload in 7-byte slices —
    blocked unless explicitly opted out."""
    f = ReplaySafetyFilter()

    tp_cm = CanFrame.create(channel_id="can0", arbitration_id=0x18ECFF00, data=b"\x20\x0e\x00\x02\xff\xec\xfe\x00", is_extended=True)
    tp_dt = CanFrame.create(channel_id="can0", arbitration_id=0x18EBFF00, data=b"\x01" + b"\x00" * 7, is_extended=True)

    ok_cm, r_cm = f.is_frame_safe(tp_cm)
    ok_dt, r_dt = f.is_frame_safe(tp_dt)
    assert not ok_cm and "BLOCKED_TP_TUNNEL" in r_cm
    assert not ok_dt and "BLOCKED_TP_TUNNEL" in r_dt

    # Explicit opt-out is honoured (analysis-only replay pipelines)
    f_opt = ReplaySafetyFilter(block_transport_tunneling=False)
    assert f_opt.is_frame_safe(tp_cm)[0] is True
    assert f_opt.is_frame_safe(tp_dt)[0] is True
