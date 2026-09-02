"""Unit tests for Volvo Penta EDC and EVC decoder."""

from src.core.models.can_frame import CanFrame
from src.protocols.volvo.volvo_decoder import VolvoPentaDecoder


def test_volvo_edc_fault_payload_parsing() -> None:
    # 2 faults:
    # 1. Type: PID (0), ID: 100 (Oil Pressure), FMI: 1 (Low Critical), Active=1 -> 0x00, 0x64, 0x81 (0x80 | 1)
    # 2. Type: SID (1), ID: 21 (Crank Sensor), FMI: 2 (Erratic), Active=1 -> 0x01, 0x15, 0x82
    raw_faults = b"\x00\x64\x81\x01\x15\x82"

    dtcs = VolvoPentaDecoder.parse_edc_fault_payload(raw_faults)
    assert len(dtcs) == 2

    assert dtcs[0].code_type == "PID"
    assert dtcs[0].code_id == 100
    assert dtcs[0].fmi == 1
    assert dtcs[0].is_active is True
    assert "Oil Pressure" in dtcs[0].description

    assert dtcs[1].code_type == "SID"
    assert dtcs[1].code_id == 21
    assert dtcs[1].fmi == 2
    assert dtcs[1].is_active is True
    assert "Crankshaft" in dtcs[1].description


def test_volvo_evc_helm_telemetry() -> None:
    # Lever: 50% Ahead -> Raw = 50 + 125 = 175 = 0xAF
    # Gear: Ahead (1) -> 0x01
    # Station Active (1) -> 0x01
    # Trim: 5.0 deg -> (5.0 + 50.0) / 0.1 = 550 = 0x0226 -> 0x26, 0x02
    # Rudder: -10.0 deg -> (-10.0 + 90.0) / 0.1 = 800 = 0x0320 -> 0x20, 0x03
    frame_data = b"\xaf\x01\x01\x26\x02\x20\x03\xff"
    frame = CanFrame.create(
        channel_id="volvo_can",
        arbitration_id=0x18FF5000,  # PGN 65360 (0xFF50)
        data=frame_data,
        is_extended=True,
    )

    state = VolvoPentaDecoder.decode_evc_can_frame(frame)
    assert state is not None
    assert state.lever_position_percent == 50.0
    assert state.gear_state == "AHEAD"
    assert state.station_active is True
    assert round(state.trim_angle_deg, 1) == 5.0
    assert round(state.rudder_angle_deg, 1) == -10.0


def test_volvo_evc_edp_frame_is_rejected() -> None:
    """P2 fix: EDP=1 frames must not alias onto the 18-bit EVC PGN mask.

    Without the guard, an ID like 0x36FF5000 (EDP=1, DP=1, PF=0xFF, PS=0x50)
    masks down to PGN 65360 and would be false-decoded as helm telemetry.
    """
    frame_data = b"\xaf\x01\x01\x26\x02\x20\x03\xff"
    edp_frame = CanFrame.create(
        channel_id="volvo_can",
        arbitration_id=0x18FF5000 | (0x01 << 25),  # EDP set, same masked PGN
        data=frame_data,
        is_extended=True,
    )
    assert VolvoPentaDecoder.decode_evc_can_frame(edp_frame) is None
