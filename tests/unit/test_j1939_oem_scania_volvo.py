"""Unit tests for Scania and Volvo OEM J1939 Decoders."""

from __future__ import annotations

from src.core.models.can_frame import CanFrame
from src.engine.decoder.dbc_decoder import SignalStatus
from src.protocols.j1939.oem.registry import OemJ1939Registry
from src.protocols.j1939.oem.scania import ScaniaDecoder
from src.protocols.j1939.oem.volvo import VolvoDecoder

# =========================================================================
# Scania Decoder Unit Tests
# =========================================================================


def test_scania_aftertreatment_dpf_decoding() -> None:
    """Test Scania PGN 65400 (0xFF78) EMS Aftertreatment & DPF Control."""
    raw_payload = bytes([0x36, 0x01, 0x03, 0x7C, 0xD5, 0xF5, 0xB2, 0x0C])

    frame = CanFrame.create(
        channel_id="scania_can",
        arbitration_id=0x18FF7800,  # PGN 65400
        data=raw_payload,
        is_extended=True,
    )

    registry = OemJ1939Registry()
    decoded = registry.decode_frame(frame)
    assert decoded is not None
    assert decoded.manufacturer == "Scania"
    assert decoded.pgn == 65400

    assert decoded.get_value("scania_dpf_soot_mass") == 15.5
    assert decoded.get_value("scania_dpf_regeneration_state") == "Parked Regeneration Running"
    assert decoded.get_value("scania_adblue_dosing_command") == 12.4
    assert decoded.get_value("scania_adblue_tank_level") == 85.2
    assert decoded.get_value("scania_adblue_refractometer_quality") == 24.5
    assert decoded.get_value("scania_scr_catalyst_bed_temperature") == 285.0


def test_scania_aftertreatment_sentinels() -> None:
    """Test Scania PGN 65400 error and not available sentinel codes."""
    raw_payload = bytes([0xFF, 0xFF, 0xFE, 0xFE, 0xFF, 0xFE, 0xFE, 0xFF])
    frame = CanFrame.create(
        channel_id="scania_can",
        arbitration_id=0x18FF7800,
        data=raw_payload,
        is_extended=True,
    )
    decoder = ScaniaDecoder()
    decoded = decoder.decode(frame, 65400, sa=0)
    assert decoded is not None
    assert decoded.get_signal("scania_dpf_soot_mass").status == SignalStatus.NOT_AVAILABLE
    assert decoded.get_signal("scania_dpf_regeneration_state").status == SignalStatus.ERROR
    assert decoded.get_signal("scania_adblue_dosing_command").status == SignalStatus.ERROR
    assert decoded.get_signal("scania_adblue_tank_level").status == SignalStatus.NOT_AVAILABLE
    assert decoded.get_signal("scania_adblue_refractometer_quality").status == SignalStatus.ERROR
    assert decoded.get_signal("scania_scr_catalyst_bed_temperature").status == SignalStatus.ERROR


def test_scania_retarder_telemetry_and_underflow() -> None:
    """Test Scania PGN 65410 (0xFF82) Retarder Control & Telemetry with oil temp underflow check."""
    raw_payload = bytes([0x03, 0x96, 0xD0, 0x2C, 0xAA, 0x01, 0x02, 0x03])

    frame = CanFrame.create(
        channel_id="scania_can",
        arbitration_id=0x18FF8210,  # PGN 65410, SA=0x10 Retarder
        data=raw_payload,
        is_extended=True,
    )

    registry = OemJ1939Registry()
    decoded = registry.decode_frame(frame)
    assert decoded is not None
    assert decoded.manufacturer == "Scania"
    assert decoded.pgn == 65410

    assert decoded.get_value("scania_retarder_lever_stage_request") == "Stage 3 (60%)"
    assert decoded.get_value("scania_retarder_braking_torque_demand") == 60.0
    assert decoded.get_value("scania_retarder_oil_temperature") == 85.5
    assert decoded.get_value("scania_retarder_actuator_air_pressure") == 8.5

    # Test sensor disconnected sentinel (Edge Case 10: raw 0xFFFF on retarder oil temp)
    payload_disconnected = bytes([0x00, 0x00, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00])
    frame_disc = CanFrame.create(
        channel_id="scania_can",
        arbitration_id=0x18FF8210,
        data=payload_disconnected,
        is_extended=True,
    )
    decoded_disc = registry.decode_frame(frame_disc)
    assert decoded_disc is not None
    temp_sig = decoded_disc.get_signal("scania_retarder_oil_temperature")
    assert temp_sig is not None
    assert temp_sig.is_valid is False
    assert temp_sig.status == SignalStatus.NOT_AVAILABLE


def test_scania_smooth_running_v8_balancing() -> None:
    """Test Scania PGN 65420 (0xFF8C) Smooth Running for 8 cylinders."""
    raw_payload = bytes([0x80, 0x8A, 0x74, 0x85, 0x7D, 0x82, 0x7A, 0x8D])

    frame = CanFrame.create(
        channel_id="scania_can",
        arbitration_id=0x18FF8C00,
        data=raw_payload,
        is_extended=True,
    )

    decoder = ScaniaDecoder()
    decoded = decoder.decode(frame, 65420, sa=0)
    assert decoded is not None
    assert decoded.get_value("scania_cyl_1_smooth_running") == 0.0
    assert decoded.get_value("scania_cyl_2_smooth_running") == 2.5
    assert decoded.get_value("scania_cyl_3_smooth_running") == -3.0
    assert decoded.get_value("scania_cyl_4_smooth_running") == 1.25
    assert decoded.get_value("scania_cyl_5_smooth_running") == -0.75
    assert decoded.get_value("scania_cyl_6_smooth_running") == 0.50
    assert decoded.get_value("scania_cyl_7_smooth_running") == -1.50
    assert decoded.get_value("scania_cyl_8_smooth_running") == 3.25


def test_scania_proprietary_a_service_commands() -> None:
    """Test Scania PGN 61184 (0xEF00) Proprietary A Service Commands."""
    payload = bytes([0x12, 0x01, 0x00, 0x00])
    frame = CanFrame.create(
        channel_id="scania_can",
        arbitration_id=0x18EF00F9,
        data=payload,
        is_extended=True,
    )
    registry = OemJ1939Registry()
    decoded = registry.decode_frame(frame, manufacturer_hint="Scania")
    assert decoded is not None
    assert decoded.manufacturer == "Scania"
    assert decoded.service_id == 0x12
    assert decoded.get_value("service_command_name") == "Scania DPF Forced Regeneration Request"


# =========================================================================
# Volvo Decoder Unit Tests
# =========================================================================


def test_volvo_aftertreatment_acm_decoding() -> None:
    """Test Volvo PGN 65350 (0xFF46) Aftertreatment ACM Telemetry & DPF Status."""
    raw_payload = bytes([0x74, 0x02, 0x12, 0x31, 0x00, 0xE7, 0xA3, 0x01])

    frame = CanFrame.create(
        channel_id="volvo_can",
        arbitration_id=0x18FF4627,  # PGN 65350, SA=0x27 ACM
        data=raw_payload,
        is_extended=True,
    )

    registry = OemJ1939Registry()
    decoded = registry.decode_frame(frame)
    assert decoded is not None
    assert decoded.manufacturer == "Volvo"
    assert decoded.pgn == 65350

    assert decoded.get_value("volvo_dpf_soot_accumulation_level") == 62.8
    assert decoded.get_value("dpf_regeneration_active_state") == "Active In-drive"
    assert decoded.get_value("dpf_regeneration_inhibit_switch_state") == "Normal"
    assert decoded.get_value("high_exhaust_temperature_warning_flag") == "Warning Level 1"
    assert decoded.get_value("volvo_adblue_dosing_mass_flow_rate") == 2.45
    assert decoded.get_value("volvo_adblue_tank_level") == 92.4
    assert decoded.get_value("volvo_adblue_concentration_quality") == 32.6


def test_volvo_veb_engine_brake_and_retarder() -> None:
    """Test Volvo PGN 65352 (0xFF48) VEB+ Engine Brake & Retarder Control."""
    raw_payload = bytes([0x03, 0xC8, 0x58, 0x1B, 0x00, 0x00, 0x00, 0x00])

    frame = CanFrame.create(
        channel_id="volvo_can",
        arbitration_id=0x18FF4800,  # PGN 65352
        data=raw_payload,
        is_extended=True,
    )

    decoder = VolvoDecoder()
    decoded = decoder.decode(frame, 65352, sa=0)
    assert decoded is not None
    assert decoded.manufacturer == "Volvo"
    assert decoded.pgn == 65352

    assert decoded.get_value("volvo_veb_engine_brake_stage") == "High (100% VEB+ Compression Brake)"
    assert decoded.get_value("volvo_retarder_torque_demand") == 80.0
    assert decoded.get_value("volvo_retarder_delivered_braking_torque") == 2500.0


def test_volvo_cylinder_balancing_and_common_rail() -> None:
    """Test Volvo PGN 65355 (0xFF4B) Cylinder Balancing & Common Rail Pressure."""
    raw_payload = bytes([0x74, 0x84, 0x80, 0x95, 0x78, 0x81, 0xCE, 0x08])

    frame = CanFrame.create(
        channel_id="volvo_can",
        arbitration_id=0x18FF4B00,
        data=raw_payload,
        is_extended=True,
    )

    registry = OemJ1939Registry()
    decoded = registry.decode_frame(frame)
    assert decoded is not None
    assert decoded.manufacturer == "Volvo"
    assert decoded.pgn == 65355

    assert decoded.get_value("volvo_cyl_1_adaptive_trim_offset") == -1.2
    assert decoded.get_value("volvo_cyl_2_adaptive_trim_offset") == 0.4
    assert decoded.get_value("volvo_cyl_3_adaptive_trim_offset") == 0.0
    assert decoded.get_value("volvo_cyl_4_adaptive_trim_offset") == 2.1
    assert decoded.get_value("volvo_cyl_5_adaptive_trim_offset") == -0.8
    assert decoded.get_value("volvo_cyl_6_adaptive_trim_offset") == 0.1
    assert decoded.get_value("volvo_common_rail_pressure_actual") == 225.4


def test_volvo_proprietary_a_service_commands() -> None:
    """Test Volvo PGN 61184 (0xEF00) Proprietary A Service Commands."""
    payload = bytes([0x05, 0x00, 0x00, 0x00])
    frame = CanFrame.create(
        channel_id="volvo_can",
        arbitration_id=0x18EF00F9,
        data=payload,
        is_extended=True,
    )
    registry = OemJ1939Registry()
    decoded = registry.decode_frame(frame, manufacturer_hint="Volvo")
    assert decoded is not None
    assert decoded.manufacturer == "Volvo"
    assert decoded.service_id == 0x05
    assert decoded.get_value("service_command_name") == "Volvo DPF Stationary Regeneration Request"
