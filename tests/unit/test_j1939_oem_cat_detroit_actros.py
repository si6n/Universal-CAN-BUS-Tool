"""Unit tests for Caterpillar, Detroit Diesel, and Mercedes-Benz Actros OEM J1939 Decoders."""

from __future__ import annotations

from src.core.models.can_frame import CanFrame
from src.engine.decoder.dbc_decoder import SignalStatus
from src.protocols.j1939.oem.actros import ActrosDecoder
from src.protocols.j1939.oem.caterpillar import CaterpillarDecoder
from src.protocols.j1939.oem.detroit import DetroitDecoder
from src.protocols.j1939.oem.registry import OemJ1939Registry

# =========================================================================
# Caterpillar Decoder Unit Tests
# =========================================================================


def test_caterpillar_aftertreatment_regen_decoding() -> None:
    """Test Caterpillar PGN 65320 (0xFF28) Aftertreatment & Regeneration Engine Control."""
    raw_payload = bytes([0x7D, 0x78, 0x82, 0x03, 0xA5, 0x1E, 0x82, 0x64])

    frame = CanFrame.create(
        channel_id="cat_can",
        arbitration_id=0x18FF2800,  # PGN 65320
        data=raw_payload,
        is_extended=True,
    )

    registry = OemJ1939Registry()
    decoded = registry.decode_frame(frame)
    assert decoded is not None
    assert decoded.manufacturer == "Caterpillar"
    assert decoded.pgn == 65320

    assert decoded.get_value("cat_ard_combustion_air_pressure") == 62.5
    assert decoded.get_value("cat_ard_fuel_pressure") == 240.0
    assert decoded.get_value("cat_ard_flame_temperature") == 610.0
    assert decoded.get_value("cat_dpf_regeneration_mode") == "Parked Service Regen"
    assert decoded.get_value("cat_regeneration_inhibit_status") == "Enabled"
    assert decoded.get_value("cat_dpf_soot_loading_index") == 78.45
    assert decoded.get_value("cat_def_quality") == 32.5
    assert decoded.get_value("cat_compression_brake_request") == 50.0


def test_caterpillar_sentinels() -> None:
    """Test Caterpillar PGN 65320 sentinel error codes."""
    raw_payload = bytes([0xFF, 0xFE, 0xFF, 0xEE, 0xFF, 0xFF, 0xFE, 0xFF])
    frame = CanFrame.create(
        channel_id="cat_can",
        arbitration_id=0x18FF2800,
        data=raw_payload,
        is_extended=True,
    )
    decoder = CaterpillarDecoder()
    decoded = decoder.decode(frame, 65320, sa=0)
    assert decoded is not None
    assert decoded.get_signal("cat_ard_combustion_air_pressure").status == SignalStatus.NOT_AVAILABLE
    assert decoded.get_signal("cat_ard_fuel_pressure").status == SignalStatus.ERROR
    assert decoded.get_signal("cat_ard_flame_temperature").status == SignalStatus.NOT_AVAILABLE
    assert decoded.get_signal("cat_dpf_regeneration_mode").status == SignalStatus.ERROR
    assert decoded.get_signal("cat_regeneration_inhibit_status").status == SignalStatus.ERROR
    assert decoded.get_signal("cat_dpf_soot_loading_index").status == SignalStatus.NOT_AVAILABLE
    assert decoded.get_signal("cat_def_quality").status == SignalStatus.ERROR
    assert decoded.get_signal("cat_compression_brake_request").status == SignalStatus.NOT_AVAILABLE


def test_caterpillar_cylinder_trim_and_heui_pressure() -> None:
    """Test Caterpillar PGN 65325 (0xFF2D) MEUI/HEUI Injection Trimming."""
    raw_payload = bytes([0x7B, 0x8C, 0x80, 0x6C, 0x87, 0x75, 0x1D, 0x01])

    frame = CanFrame.create(
        channel_id="cat_can",
        arbitration_id=0x18FF2D00,
        data=raw_payload,
        is_extended=True,
    )

    decoder = CaterpillarDecoder()
    decoded = decoder.decode(frame, 65325, sa=0)
    assert decoded is not None
    assert decoded.get_value("cat_cyl_1_trim_offset") == -0.5
    assert decoded.get_value("cat_cyl_2_trim_offset") == 1.2
    assert decoded.get_value("cat_cyl_3_trim_offset") == 0.0
    assert decoded.get_value("cat_cyl_4_trim_offset") == -2.0
    assert decoded.get_value("cat_cyl_5_trim_offset") == 0.7
    assert decoded.get_value("cat_cyl_6_trim_offset") == -1.1
    assert decoded.get_value("cat_rail_actuation_high_pressure") == 28.5


def test_caterpillar_proprietary_a_service_commands() -> None:
    """Test Caterpillar PGN 61184 (0xEF00) Proprietary A Service Commands."""
    payload = bytes([0x20, 0x02, 0x00, 0x00])
    frame = CanFrame.create(
        channel_id="cat_can",
        arbitration_id=0x18EF00F9,
        data=payload,
        is_extended=True,
    )
    registry = OemJ1939Registry()
    decoded = registry.decode_frame(frame, manufacturer_hint="Caterpillar")
    assert decoded is not None
    assert decoded.manufacturer == "Caterpillar"
    assert decoded.service_id == 0x20
    assert decoded.get_value("service_command_name") == "Cylinder Cutout Diagnostic Test"
    assert decoded.get_value("target_cylinder") == 2


# =========================================================================
# Detroit Diesel Decoder Unit Tests
# =========================================================================


def test_detroit_aftertreatment_acm_decoding() -> None:
    """Test Detroit Diesel PGN 65370 (0xFF5A) ACM DPF & DEF Quality."""
    raw_payload = bytes([0x5A, 0x01, 0x78, 0x00, 0x02, 0xC4, 0x01, 0x00])

    frame = CanFrame.create(
        channel_id="detroit_can",
        arbitration_id=0x18FF5A27,  # PGN 65370, SA=0x27 ACM
        data=raw_payload,
        is_extended=True,
    )

    registry = OemJ1939Registry()
    decoded = registry.decode_frame(frame)
    assert decoded is not None
    assert decoded.manufacturer == "Detroit"
    assert decoded.pgn == 65370

    assert decoded.get_value("detroit_dpf_soot_mass_accumulation") == 34.6
    assert decoded.get_value("detroit_dpf_ash_mass_accumulation") == 120.0
    assert decoded.get_value("detroit_dpf_regeneration_mode") == "Active High"
    assert decoded.get_value("detroit_dpf_regeneration_inhibit_reason") == "None"
    assert decoded.get_value("detroit_def_dosing_rate") == 45.2
    assert decoded.get_value("detroit_def_quality_status") == "Nominal (32.5% Urea)"

    # Test degraded DEF / Tamper detection
    tamper_payload = bytes([0x5A, 0x01, 0x78, 0x00, 0x04, 0x00, 0x00, 0x03])
    frame_tamper = CanFrame.create(
        channel_id="detroit_can",
        arbitration_id=0x18FF5A27,
        data=tamper_payload,
        is_extended=True,
    )
    decoded_tamper = registry.decode_frame(frame_tamper)
    assert decoded_tamper is not None
    assert decoded_tamper.get_value("detroit_dpf_regeneration_mode") == "Inhibited"
    assert decoded_tamper.get_value("detroit_def_quality_status") == "Tamper / Water Detected"


def test_detroit_jake_brake_and_retarder() -> None:
    """Test Detroit Diesel PGN 65375 (0xFF5F) Jake Brake & Retarder."""
    raw_payload = bytes([0x02, 0x64, 0x85, 0x0C, 0x00, 0x00, 0x00, 0x00])

    frame = CanFrame.create(
        channel_id="detroit_can",
        arbitration_id=0x18FF5F00,
        data=raw_payload,
        is_extended=True,
    )

    decoder = DetroitDecoder()
    decoded = decoder.decode(frame, 65375, sa=0)
    assert decoded is not None
    assert decoded.get_value("detroit_jake_brake_stage") == "Medium (4-Cylinder)"
    assert decoded.get_value("detroit_voith_secondary_water_retarder") == 40.0
    assert decoded.get_value("detroit_engine_retardation_power") == 320.5


def test_detroit_mcm_balancing_and_apcrs_pressure() -> None:
    """Test Detroit Diesel PGN 65380 (0xFF64) Injector Balancing & APCRS Pressure."""
    raw_payload = bytes([0x80, 0x8C, 0x67, 0x87, 0x78, 0x82, 0x60, 0x09])

    frame = CanFrame.create(
        channel_id="detroit_can",
        arbitration_id=0x18FF6400,
        data=raw_payload,
        is_extended=True,
    )

    registry = OemJ1939Registry()
    decoded = registry.decode_frame(frame)
    assert decoded is not None
    assert decoded.manufacturer == "Detroit"
    assert decoded.pgn == 65380

    assert decoded.get_value("detroit_cyl_1_fuel_offset_trim") == 0.0
    assert decoded.get_value("detroit_cyl_2_fuel_offset_trim") == 0.6
    assert decoded.get_value("detroit_cyl_3_fuel_offset_trim") == -1.25
    assert decoded.get_value("detroit_cyl_4_fuel_offset_trim") == 0.35
    assert decoded.get_value("detroit_cyl_5_fuel_offset_trim") == -0.4
    assert decoded.get_value("detroit_cyl_6_fuel_offset_trim") == 0.1
    assert decoded.get_value("detroit_amplified_rail_pressure") == 240.0


def test_detroit_proprietary_a_service_commands() -> None:
    """Test Detroit Diesel PGN 61184 (0xEF00) Proprietary A Service Commands."""
    payload = bytes([0x07, 0x00, 0x00, 0x00])
    frame = CanFrame.create(
        channel_id="detroit_can",
        arbitration_id=0x18EF00F9,
        data=payload,
        is_extended=True,
    )
    registry = OemJ1939Registry()
    decoded = registry.decode_frame(frame, manufacturer_hint="Detroit")
    assert decoded is not None
    assert decoded.manufacturer == "Detroit"
    assert decoded.service_id == 0x07
    assert decoded.get_value("service_command_name") == "Detroit ACM DPF Service Regeneration Trigger"


# =========================================================================
# Mercedes-Benz Actros Decoder Unit Tests
# =========================================================================


def test_actros_bluetec_aftertreatment_decoding() -> None:
    """Test Mercedes-Benz Actros PGN 65450 (0xFFAA) BlueTec 6 Aftertreatment."""
    raw_payload = bytes([0xA9, 0x01, 0x01, 0xB9, 0x00, 0xC0, 0xF5, 0xF0])

    frame = CanFrame.create(
        channel_id="actros_can",
        arbitration_id=0x18FFAA27,  # PGN 65450, SA=0x27 ACM
        data=raw_payload,
        is_extended=True,
    )

    registry = OemJ1939Registry()
    decoded = registry.decode_frame(frame)
    assert decoded is not None
    assert decoded.manufacturer == "Mercedes-Benz"
    assert decoded.pgn == 65450

    assert decoded.get_value("mercedes_dpf_soot_load_index") == 42.5
    assert decoded.get_value("mercedes_bluetec_regeneration_mode") == "Regeneration Fahren (Highway)"
    assert decoded.get_value("mercedes_adblue_dosierrate_istwert") == 1.85
    assert decoded.get_value("mercedes_adblue_fuellstand_kombi") == 76.8
    assert decoded.get_value("mercedes_adblue_qualitaet_konzentration") == 24.5
    assert decoded.get_value("mercedes_scr_katalysator_wirkungsgrad") == 96.0


def test_actros_hpeb_and_retarder() -> None:
    """Test Mercedes Actros PGN 65455 (0xFFAF) HPEB Engine Brake & Retarder."""
    raw_payload = bytes([0x03, 0xC8, 0xA8, 0x2D, 0x01, 0x00, 0x00, 0x00])

    frame = CanFrame.create(
        channel_id="actros_can",
        arbitration_id=0x18FFAF00,
        data=raw_payload,
        is_extended=True,
    )

    decoder = ActrosDecoder()
    decoded = decoder.decode(frame, 65455, sa=0)
    assert decoded is not None
    assert decoded.get_value("mercedes_hpeb_motorbremse_stufe") == "Stufe 3 (Volllast Dauerbremse 100%)"
    assert decoded.get_value("mercedes_retarder_bremsmomentanforderung") == 80.0
    assert decoded.get_value("mercedes_retarder_kuehlmitteltemperatur") == 92.25


def test_actros_laufruheregelung_and_raildruck() -> None:
    """Test Mercedes Actros PGN 65460 (0xFFB4) Laufruheregelung & Common-Rail Pressure."""
    raw_payload = bytes([0x78, 0x85, 0x8B, 0x7D, 0x80, 0x7B, 0xFC, 0x53])

    frame = CanFrame.create(
        channel_id="actros_can",
        arbitration_id=0x18FFB400,
        data=raw_payload,
        is_extended=True,
    )

    registry = OemJ1939Registry()
    decoded = registry.decode_frame(frame)
    assert decoded is not None
    assert decoded.manufacturer == "Mercedes-Benz"
    assert decoded.pgn == 65460

    assert decoded.get_value("zylinder_1_mengenkorrektur") == -0.8
    assert decoded.get_value("zylinder_2_mengenkorrektur") == 0.5
    assert decoded.get_value("zylinder_3_mengenkorrektur") == 1.1
    assert decoded.get_value("zylinder_4_mengenkorrektur") == -0.3
    assert decoded.get_value("zylinder_5_mengenkorrektur") == 0.0
    assert decoded.get_value("zylinder_6_mengenkorrektur") == -0.5
    assert decoded.get_value("common_rail_raildruck_istwert") == 2150.0


def test_actros_proprietary_a_service_commands() -> None:
    """Test Mercedes Actros PGN 61184 (0xEF00) Proprietary A Service Commands."""
    payload = bytes([0x24, 0x00, 0x00, 0x00])
    frame = CanFrame.create(
        channel_id="actros_can",
        arbitration_id=0x18EF00F9,
        data=payload,
        is_extended=True,
    )
    registry = OemJ1939Registry()
    decoded = registry.decode_frame(frame, manufacturer_hint="Mercedes-Benz")
    assert decoded is not None
    assert decoded.manufacturer == "Mercedes-Benz"
    assert decoded.service_id == 0x24
    assert decoded.get_value("service_command_name") == "Mercedes DPF Service Regeneration Trigger"
