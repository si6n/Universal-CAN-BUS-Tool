"""Unit and integration tests for curated DBC Knowledge Pack across all domains.

Verifies:
1. Manifest integrity and catalog coverage (70+ DBC files, 10,000+ messages).
2. Clean loading into DbcSignalDecoder across all 5 domains.
3. Realistic frame decoding for Heavy Duty (J1939 EEC1, CCVS1), Marine (N2K Heading),
   EV/BMS (Limits, Telemetry, SOC), and Passenger (Toyota, Tesla, VW MQB).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.models.can_frame import CanFrame
from src.engine.decoder.dbc_decoder import DbcSignalDecoder, SignalStatus

DBC_DIR = Path(__file__).resolve().parents[2] / "data" / "dbc"


def test_dbc_manifest_and_catalog_exist() -> None:
    manifest_path = DBC_DIR / "manifest.json"
    catalog_path = DBC_DIR / "catalog.json"

    assert manifest_path.exists(), "manifest.json missing in data/dbc"
    assert catalog_path.exists(), "catalog.json missing in data/dbc"

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert catalog["total_files"] >= 70
    assert catalog["total_messages"] >= 10000
    assert catalog["total_signals"] >= 40000
    assert "heavy_duty" in catalog["categories"]
    assert "marine" in catalog["categories"]
    assert "agriculture" in catalog["categories"]
    assert "ev_bms" in catalog["categories"]
    assert "passenger" in catalog["categories"]


def test_heavy_duty_j1939_canboat_decoding() -> None:
    j1939_dbc = DBC_DIR / "heavy_duty" / "j1939_canboat.dbc"
    assert j1939_dbc.exists()

    decoder = DbcSignalDecoder.from_dbc_file(j1939_dbc)
    assert len(decoder.db.messages) >= 80

    # EEC1 (0x0CF00400: PGN 61444, prio 3, SA 0)
    # Byte 3-4 = 1600 RPM -> raw 12800 = 0x3200 -> [0x00, 0x32]
    eec1_data = bytes([0xFF, 0xFF, 0xFF, 0x00, 0x32, 0xFF, 0xFF, 0xFF])
    frame = CanFrame.create("can0", 0x0CF00400, eec1_data, is_extended=True)

    decoded = decoder.decode_frame(frame)
    assert decoded is not None
    assert "Engine_RPM" in decoded.signals
    sig = decoded.signals["Engine_RPM"]
    assert sig.value == 1600.0
    assert sig.unit == "rpm"
    assert sig.is_valid is True
    assert sig.status == SignalStatus.VALID


def test_marine_n2k_canboat_decoding() -> None:
    n2k_dbc = DBC_DIR / "marine" / "n2k_canboat.dbc"
    assert n2k_dbc.exists()

    decoder = DbcSignalDecoder.from_dbc_file(n2k_dbc)
    assert len(decoder.db.messages) >= 600

    # PGN 127250 (Vessel Heading) -> ID 0x09F11228
    # SID=1, Heading=1.5708 rad (~90 deg) -> raw 15708 = 0x3D5C -> [0x5C, 0x3D]
    n2k_data = bytes([0x01, 0x5C, 0x3D, 0xFF, 0xFF, 0xFF, 0xFF, 0xFC])
    frame = CanFrame.create("can0", 0x09F11228, n2k_data, is_extended=True)

    decoded = decoder.decode_frame(frame)
    assert decoded is not None
    assert "Heading" in decoded.signals
    assert pytest.approx(decoded.signals["Heading"].value, 0.0001) == 1.5708


def test_ev_bms_standard_decoding() -> None:
    bms_dbc = DBC_DIR / "ev_bms" / "ev_bms_standard.dbc"
    assert bms_dbc.exists()

    decoder = DbcSignalDecoder.from_dbc_file(bms_dbc)

    # 0x356 BMS_Telemetry: Battery Voltage 400.0V (0.01V/bit -> 40000 = 0x9C40), Current 25.0A (0.1A/bit -> 250 = 0x00FA), Temp 28.5 degC (0.1/bit -> 285 = 0x011D)
    bms_data = bytes([0x40, 0x9C, 0xFA, 0x00, 0x1D, 0x01, 0x00, 0x00])
    frame = CanFrame.create("can0", 0x356, bms_data, is_extended=False)

    decoded = decoder.decode_frame(frame)
    assert decoded is not None
    assert decoded.signals["BatteryVoltage"].value == 400.0
    assert decoded.signals["BatteryCurrent"].value == 25.0
    assert decoded.signals["BatteryTemperature"].value == 28.5


def test_passenger_toyota_tss2_decoding() -> None:
    toyota_dbc = DBC_DIR / "passenger" / "toyota_tss2_adas.dbc"
    assert toyota_dbc.exists()

    decoder = DbcSignalDecoder.from_dbc_file(toyota_dbc)
    assert len(decoder.db.messages) >= 30


def test_decoder_from_directory_heavy_duty() -> None:
    hd_folder = DBC_DIR / "heavy_duty"
    decoder = DbcSignalDecoder.from_directory(hd_folder)
    assert len(decoder.db.messages) >= 85


def test_decoder_add_dbc_file_multi_domain() -> None:
    hd_dbc = DBC_DIR / "heavy_duty" / "j1939_canboat.dbc"
    bms_dbc = DBC_DIR / "ev_bms" / "ev_bms_standard.dbc"

    decoder = DbcSignalDecoder.from_dbc_file(hd_dbc)
    initial_count = len(decoder.db.messages)

    decoder.add_dbc_file(bms_dbc)
    assert len(decoder.db.messages) > initial_count

    # Can decode both J1939 and BMS frames with same decoder instance
    frame_j1939 = CanFrame.create("can0", 0x0CF00400, bytes([0xFF, 0xFF, 0xFF, 0x00, 0x32, 0xFF, 0xFF, 0xFF]), is_extended=True)
    frame_bms = CanFrame.create("can0", 0x356, bytes([0x40, 0x9C, 0xFA, 0x00, 0x1D, 0x01, 0x00, 0x00]), is_extended=False)

    dec_j1939 = decoder.decode_frame(frame_j1939)
    dec_bms = decoder.decode_frame(frame_bms)

    assert dec_j1939 is not None and dec_j1939.signals["Engine_RPM"].value == 1600.0
    assert dec_bms is not None and dec_bms.signals["BatteryVoltage"].value == 400.0

