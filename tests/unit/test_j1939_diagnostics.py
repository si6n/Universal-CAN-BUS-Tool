"""Unit tests for SAE J1939-73 Diagnostic Services (DM1, DM2, DM11, FMI 0-31)."""

from src.protocols.j1939.diagnostics import (
    J1939DiagnosticService,
    LampStatus,
)


def test_j1939_single_dtc_dm1_parsing() -> None:
    # DM1 Payload (8 bytes):
    # Byte 0: 0x40 (MIL=0b01 ON, RedStop=0b00 OFF, Amber=0b00 OFF, Protect=0b00 OFF)
    # Byte 1: 0xFF (Flash states not available)
    # Byte 2..5: SPN 100 (Engine Oil Pressure), FMI 1 (Low Most Severe), OC 3, CM 0
    # SPN 100 = 0x000064 -> Byte 0: 0x64, Byte 1: 0x00, Byte 2: ((SPN >> 11) << 5) | FMI = (0 << 5) | 1 = 0x01
    # Byte 3: (CM << 7) | OC = (0 << 7) | 3 = 0x03
    # Byte 6..7: 0xFF 0xFF
    dm1_raw = b"\x40\xff\x64\x00\x01\x03\xff\xff"

    msg = J1939DiagnosticService.parse_dm1_or_dm2(
        data=dm1_raw,
        pgn=65226,
        source_address=0,
        timestamp_ns=1000,
    )

    assert msg.source_address == 0
    assert msg.malfunction_indicator_lamp == LampStatus.ON
    assert msg.red_stop_lamp == LampStatus.OFF
    assert len(msg.dtcs) == 1

    dtc = msg.dtcs[0]
    assert dtc.spn == 100
    assert dtc.fmi == 1
    assert dtc.occurrence_count == 3
    assert dtc.is_critical is True
    assert "Below Normal" in dtc.fmi_description_en
    assert "Kritik" in dtc.fmi_description_tr


def test_j1939_multi_dtc_parsing() -> None:
    # 2 DTCs in payload (10 bytes)
    # Lamps: Amber Warning ON (Byte 0 = 0x04)
    # DTC 1: SPN 190 (Engine Speed), FMI 0 (High Most Severe), OC 5 -> 0xBE, 0x00, 0x00, 0x05
    # DTC 2: SPN 110 (Coolant Temp), FMI 3 (Voltage High), OC 1 -> 0x6E, 0x00, 0x03, 0x01
    dm_raw = b"\x04\xff\xbe\x00\x00\x05\x6e\x00\x03\x01"

    msg = J1939DiagnosticService.parse_dm1_or_dm2(data=dm_raw, pgn=65226, source_address=0)
    assert msg.amber_warning_lamp == LampStatus.ON
    assert len(msg.dtcs) == 2

    dtc1 = msg.dtcs[0]
    assert dtc1.spn == 190
    assert dtc1.fmi == 0
    assert dtc1.occurrence_count == 5

    dtc2 = msg.dtcs[1]
    assert dtc2.spn == 110
    assert dtc2.fmi == 3
    assert dtc2.occurrence_count == 1


def test_clear_diagnostic_requests() -> None:
    dm11_req = J1939DiagnosticService.create_dm11_clear_active_request()
    assert dm11_req == b"\xd3\xfe\x00"

    dm3_req = J1939DiagnosticService.create_dm3_clear_previously_active_request()
    assert dm3_req == b"\xcc\xfe\x00"
