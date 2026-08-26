"""Unit tests for SAE J1939-71 MSB Sentinel range validation."""

from src.protocols.j1939.sentinel import J1939SentinelFilter, SignalQuality


def test_uint8_sentinel_ranges() -> None:
    # Valid 0..250
    assert J1939SentinelFilter.check_uint8(0) == SignalQuality.VALID
    assert J1939SentinelFilter.check_uint8(100) == SignalQuality.VALID
    assert J1939SentinelFilter.check_uint8(0xFA) == SignalQuality.VALID

    # Parameter Specific (251 / 0xFB)
    assert J1939SentinelFilter.check_uint8(0xFB) == SignalQuality.PARAMETER_SPECIFIC

    # Reserved (252..253 / 0xFC..0xFD)
    assert J1939SentinelFilter.check_uint8(0xFC) == SignalQuality.RESERVED
    assert J1939SentinelFilter.check_uint8(0xFD) == SignalQuality.RESERVED

    # Error Indicator (254 / 0xFE)
    assert J1939SentinelFilter.check_uint8(0xFE) == SignalQuality.ERROR

    # Not Available / Not Installed (255 / 0xFF)
    assert J1939SentinelFilter.check_uint8(0xFF) == SignalQuality.NOT_AVAILABLE


def test_uint16_sentinel_ranges() -> None:
    # Valid 0x0000..0xFAFF
    assert J1939SentinelFilter.check_uint16(0x0000) == SignalQuality.VALID
    assert J1939SentinelFilter.check_uint16(0x1234) == SignalQuality.VALID
    assert J1939SentinelFilter.check_uint16(0xFAFF) == SignalQuality.VALID

    # Error Indicator MSB = 0xFE (0xFE00..0xFEFF)
    assert J1939SentinelFilter.check_uint16(0xFE00) == SignalQuality.ERROR
    assert J1939SentinelFilter.check_uint16(0xFE80) == SignalQuality.ERROR

    # Not Available MSB = 0xFF (0xFF00..0xFFFF)
    assert J1939SentinelFilter.check_uint16(0xFF00) == SignalQuality.NOT_AVAILABLE
    assert J1939SentinelFilter.check_uint16(0xFFFF) == SignalQuality.NOT_AVAILABLE


def test_discrete_2bit_sentinel_ranges() -> None:
    assert J1939SentinelFilter.check_discrete_2bit(0b00) == SignalQuality.VALID
    assert J1939SentinelFilter.check_discrete_2bit(0b01) == SignalQuality.VALID
    assert J1939SentinelFilter.check_discrete_2bit(0b10) == SignalQuality.ERROR
    assert J1939SentinelFilter.check_discrete_2bit(0b11) == SignalQuality.NOT_AVAILABLE
