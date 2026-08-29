from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from src.protocols.j1939.sentinel import (
    DecodedSignal,
    J1939SentinelFilter,
    J1939SignalDecoder,
    SignalDefinition,
    SignalQuality,
    decode_j1939_signal,
    decode_raw_value,
    decode_signal,
)

# ---------------------------------------------------------------------------
# SignalDefinition & DecodedSignal Models
# ---------------------------------------------------------------------------


def test_signal_definition_model_defaults_and_immutability() -> None:
    """Verify SignalDefinition dataclass attributes, defaults, and immutability."""
    sig = SignalDefinition(
        name="Engine Speed",
        spn=190,
        start_bit=24,
        length_bits=16,
    )
    assert sig.name == "Engine Speed"
    assert sig.spn == 190
    assert sig.start_bit == 24
    assert sig.length_bits == 16
    assert sig.byte_order == "little_endian"
    assert sig.is_signed is False
    assert sig.scale == 1.0
    assert sig.offset == 0.0
    assert sig.min_val is None
    assert sig.max_val is None
    assert sig.unit == ""

    # Immutability check (frozen=True)
    with pytest.raises(FrozenInstanceError):
        sig.scale = 0.5  # type: ignore[misc]


def test_decoded_signal_model_instantiation() -> None:
    """Verify DecodedSignal container attributes."""
    dec = DecodedSignal(quality=SignalQuality.VALID, raw_value=100, physical_value=25.0)
    assert dec.quality == SignalQuality.VALID
    assert dec.raw_value == 100
    assert dec.physical_value == 25.0


# ---------------------------------------------------------------------------
# Sentinel Range Checking Methods (Backward-Compatibility)
# ---------------------------------------------------------------------------


def test_uint8_sentinel_ranges() -> None:
    """Verify 8-bit unsigned sentinel ranges according to SAE J1939-71."""
    # Valid 0..250 (0x00..0xFA)
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

    # Out of range values
    assert J1939SentinelFilter.check_uint8(-1) == SignalQuality.ERROR
    assert J1939SentinelFilter.check_uint8(256) == SignalQuality.ERROR


def test_uint16_sentinel_ranges() -> None:
    """Verify 16-bit unsigned sentinel ranges according to SAE J1939-71."""
    # Valid 0x0000..0xFAFF
    assert J1939SentinelFilter.check_uint16(0x0000) == SignalQuality.VALID
    assert J1939SentinelFilter.check_uint16(0x1234) == SignalQuality.VALID
    assert J1939SentinelFilter.check_uint16(0xFAFF) == SignalQuality.VALID

    # Parameter Specific MSB = 0xFB (0xFB00..0xFBFF)
    assert J1939SentinelFilter.check_uint16(0xFB00) == SignalQuality.PARAMETER_SPECIFIC
    assert J1939SentinelFilter.check_uint16(0xFB80) == SignalQuality.PARAMETER_SPECIFIC

    # Reserved MSB = 0xFC..0xFD (0xFC00..0xFDFF)
    assert J1939SentinelFilter.check_uint16(0xFC00) == SignalQuality.RESERVED
    assert J1939SentinelFilter.check_uint16(0xFDFF) == SignalQuality.RESERVED

    # Error Indicator MSB = 0xFE (0xFE00..0xFEFF)
    assert J1939SentinelFilter.check_uint16(0xFE00) == SignalQuality.ERROR
    assert J1939SentinelFilter.check_uint16(0xFE80) == SignalQuality.ERROR
    assert J1939SentinelFilter.check_uint16(0xFEFF) == SignalQuality.ERROR

    # Not Available MSB = 0xFF (0xFF00..0xFFFF)
    assert J1939SentinelFilter.check_uint16(0xFF00) == SignalQuality.NOT_AVAILABLE
    assert J1939SentinelFilter.check_uint16(0xFFFF) == SignalQuality.NOT_AVAILABLE

    # Out of range
    assert J1939SentinelFilter.check_uint16(-1) == SignalQuality.ERROR
    assert J1939SentinelFilter.check_uint16(0x10000) == SignalQuality.ERROR


def test_uint24_sentinel_ranges() -> None:
    """Verify 24-bit unsigned sentinel ranges."""
    assert J1939SentinelFilter.check_uint24(0x000000) == SignalQuality.VALID
    assert J1939SentinelFilter.check_uint24(0xFAFFFF) == SignalQuality.VALID
    assert J1939SentinelFilter.check_uint24(0xFB0000) == SignalQuality.PARAMETER_SPECIFIC
    assert J1939SentinelFilter.check_uint24(0xFC0000) == SignalQuality.RESERVED
    assert J1939SentinelFilter.check_uint24(0xFDFFFF) == SignalQuality.RESERVED
    assert J1939SentinelFilter.check_uint24(0xFE0000) == SignalQuality.ERROR
    assert J1939SentinelFilter.check_uint24(0xFFFFFF) == SignalQuality.NOT_AVAILABLE
    assert J1939SentinelFilter.check_uint24(-1) == SignalQuality.ERROR
    assert J1939SentinelFilter.check_uint24(0x1000000) == SignalQuality.ERROR


def test_uint32_sentinel_ranges() -> None:
    """Verify 32-bit unsigned sentinel ranges."""
    assert J1939SentinelFilter.check_uint32(0x00000000) == SignalQuality.VALID
    assert J1939SentinelFilter.check_uint32(0xFAFFFFFF) == SignalQuality.VALID
    assert J1939SentinelFilter.check_uint32(0xFB000000) == SignalQuality.PARAMETER_SPECIFIC
    assert J1939SentinelFilter.check_uint32(0xFC000000) == SignalQuality.RESERVED
    assert J1939SentinelFilter.check_uint32(0xFDFFFFFF) == SignalQuality.RESERVED
    assert J1939SentinelFilter.check_uint32(0xFE000000) == SignalQuality.ERROR
    assert J1939SentinelFilter.check_uint32(0xFFFFFFFF) == SignalQuality.NOT_AVAILABLE
    assert J1939SentinelFilter.check_uint32(-1) == SignalQuality.ERROR
    assert J1939SentinelFilter.check_uint32(0x100000000) == SignalQuality.ERROR


def test_discrete_2bit_sentinel_ranges() -> None:
    """Verify 2-bit discrete state sentinel boundaries."""
    assert J1939SentinelFilter.check_discrete_2bit(0b00) == SignalQuality.VALID
    assert J1939SentinelFilter.check_discrete_2bit(0b01) == SignalQuality.VALID
    assert J1939SentinelFilter.check_discrete_2bit(0b10) == SignalQuality.ERROR
    assert J1939SentinelFilter.check_discrete_2bit(0b11) == SignalQuality.NOT_AVAILABLE


def test_nibble_4bit_sentinel_ranges() -> None:
    """Verify 4-bit nibble sentinel boundaries."""
    assert J1939SentinelFilter.check_nibble_4bit(0x0) == SignalQuality.VALID
    assert J1939SentinelFilter.check_nibble_4bit(0xD) == SignalQuality.VALID
    assert J1939SentinelFilter.check_nibble_4bit(0xE) == SignalQuality.ERROR
    assert J1939SentinelFilter.check_nibble_4bit(0xF) == SignalQuality.NOT_AVAILABLE


def test_arbitrary_bit_length_sentinel_ranges() -> None:
    """Verify arbitrary length bitfield sentinel handling."""
    # 1-bit signal
    assert J1939SentinelFilter.check_raw_value(0, length_bits=1) == SignalQuality.VALID
    assert J1939SentinelFilter.check_raw_value(1, length_bits=1) == SignalQuality.VALID

    # 12-bit signal (max 4095)
    assert J1939SentinelFilter.check_raw_value(100, length_bits=12) == SignalQuality.VALID
    assert J1939SentinelFilter.check_raw_value(4092, length_bits=12) == SignalQuality.RESERVED
    assert J1939SentinelFilter.check_raw_value(4093, length_bits=12) == SignalQuality.RESERVED
    assert J1939SentinelFilter.check_raw_value(4094, length_bits=12) == SignalQuality.ERROR
    assert J1939SentinelFilter.check_raw_value(4095, length_bits=12) == SignalQuality.NOT_AVAILABLE

    # Invalid lengths or out-of-range values
    assert J1939SentinelFilter.check_raw_value(0, length_bits=0) == SignalQuality.ERROR
    assert J1939SentinelFilter.check_raw_value(-5, length_bits=8) == SignalQuality.ERROR
    assert J1939SentinelFilter.check_raw_value(500, length_bits=8) == SignalQuality.ERROR


# ---------------------------------------------------------------------------
# Signed 2's Complement Conversion & SPN 513
# ---------------------------------------------------------------------------


def test_convert_to_signed() -> None:
    """Verify conversion of unsigned integers to signed 2's complement."""
    # 8-bit conversion
    assert J1939SentinelFilter.convert_to_signed(0x00, 8) == 0
    assert J1939SentinelFilter.convert_to_signed(0x7F, 8) == 127
    assert J1939SentinelFilter.convert_to_signed(0x80, 8) == -128
    assert J1939SentinelFilter.convert_to_signed(0xFF, 8) == -1
    assert J1939SentinelFilter.convert_to_signed(0x9C, 8) == -100

    # 16-bit conversion
    assert J1939SentinelFilter.convert_to_signed(0x0000, 16) == 0
    assert J1939SentinelFilter.convert_to_signed(0x7FFF, 16) == 32767
    assert J1939SentinelFilter.convert_to_signed(0x8000, 16) == -32768
    assert J1939SentinelFilter.convert_to_signed(0xFFFF, 16) == -1
    assert J1939SentinelFilter.convert_to_signed(0xFF9C, 16) == -100

    # 12-bit conversion
    assert J1939SentinelFilter.convert_to_signed(0x7FF, 12) == 2047
    assert J1939SentinelFilter.convert_to_signed(0x800, 12) == -2048


def test_spn513_driver_demand_torque_decoding() -> None:
    """Verify SPN 513 16-bit signed torque decoding without false sentinel classification."""
    sig_def = SignalDefinition(
        name="Drivers Demand Engine - Percent Torque",
        spn=513,
        start_bit=0,
        length_bits=16,
        is_signed=True,
        scale=1.0,
        offset=0.0,
        unit="%",
    )

    # Raw 0xFF9C (65436) -> -100% torque (VALID)
    d_neg100 = decode_raw_value(0xFF9C, sig_def)
    assert d_neg100.quality == SignalQuality.VALID
    assert d_neg100.raw_value == -100
    assert d_neg100.physical_value == -100.0

    # Raw 0x0000 -> 0% torque (VALID)
    d_zero = decode_raw_value(0x0000, sig_def)
    assert d_zero.quality == SignalQuality.VALID
    assert d_zero.raw_value == 0
    assert d_zero.physical_value == 0.0

    # Raw 0x007D -> +125% torque (VALID)
    d_pos125 = decode_raw_value(0x007D, sig_def)
    assert d_pos125.quality == SignalQuality.VALID
    assert d_pos125.raw_value == 125
    assert d_pos125.physical_value == 125.0

    # Raw 0x8000 (-32768) -> VALID
    d_min = decode_raw_value(0x8000, sig_def)
    assert d_min.quality == SignalQuality.VALID
    assert d_min.raw_value == -32768
    assert d_min.physical_value == -32768.0

    # Raw 0xFFFF (All 1s) -> NOT_AVAILABLE sentinel for signed 16-bit
    d_na = decode_raw_value(0xFFFF, sig_def)
    assert d_na.quality == SignalQuality.NOT_AVAILABLE
    assert d_na.raw_value == 0xFFFF
    assert d_na.physical_value is None

    # Raw 0xFFFE (All 1s except LSB) -> ERROR sentinel for signed 16-bit
    d_err = decode_raw_value(0xFFFE, sig_def)
    assert d_err.quality == SignalQuality.ERROR
    assert d_err.raw_value == 0xFFFE
    assert d_err.physical_value is None


# ---------------------------------------------------------------------------
# Bit Extraction & Endianness
# ---------------------------------------------------------------------------


def test_extract_raw_bits_little_endian() -> None:
    """Verify bit extraction from little endian payload bytes."""
    payload = b"\x12\x34\x56\x78\x9a\xbc\xde\xf0"

    # Byte 0: 0x12
    assert J1939SentinelFilter.extract_raw_bits(payload, start_bit=0, length_bits=8) == 0x12

    # Bytes 0..1 (16-bit LE): 0x3412
    assert J1939SentinelFilter.extract_raw_bits(payload, start_bit=0, length_bits=16) == 0x3412

    # Intra-byte bitfield: bits 4..7 of byte 0 (0x12 -> high nibble is 1)
    assert J1939SentinelFilter.extract_raw_bits(payload, start_bit=4, length_bits=4) == 0x01

    # Cross-byte bitfield: bits 4..19 (16 bits starting at bit 4)
    # payload_int = ... 0x3412
    # (0x3412 >> 4) & 0xFFFF = (0x0341) | (0x56 & 0x0F) << 12 = 0x6341
    assert J1939SentinelFilter.extract_raw_bits(payload, start_bit=4, length_bits=16) == 0x6341


def test_extract_raw_bits_big_endian() -> None:
    """Verify bit extraction from big endian payload bytes."""
    payload = b"\x12\x34\x56\x78"

    # First 8 bits: 0x12
    assert (
        J1939SentinelFilter.extract_raw_bits(
            payload, start_bit=0, length_bits=8, byte_order="big_endian"
        )
        == 0x12
    )

    # First 16 bits: 0x1234
    assert (
        J1939SentinelFilter.extract_raw_bits(
            payload, start_bit=0, length_bits=16, byte_order="big_endian"
        )
        == 0x1234
    )


def test_extract_raw_bits_error_conditions() -> None:
    """Verify error handling on invalid extraction inputs."""
    with pytest.raises(ValueError, match="Payload cannot be empty"):
        J1939SentinelFilter.extract_raw_bits(b"", start_bit=0, length_bits=8)

    with pytest.raises(ValueError, match="Invalid start_bit"):
        J1939SentinelFilter.extract_raw_bits(b"\x00", start_bit=-1, length_bits=8)

    with pytest.raises(ValueError, match="Invalid length_bits"):
        J1939SentinelFilter.extract_raw_bits(b"\x00", start_bit=0, length_bits=0)

    with pytest.raises(ValueError, match="requires 16 bits"):
        J1939SentinelFilter.extract_raw_bits(b"\x00", start_bit=0, length_bits=16)

    with pytest.raises(ValueError, match="Unsupported byte_order"):
        J1939SentinelFilter.extract_raw_bits(
            b"\x00", start_bit=0, length_bits=8, byte_order="invalid_order"
        )


# ---------------------------------------------------------------------------
# 3-Stage Decoding from Raw Bytes & Scaling Pipeline
# ---------------------------------------------------------------------------


def test_decode_signal_from_can_payload() -> None:
    """Verify end-to-end payload extraction and 3-stage decoding."""
    # EEC1 CAN payload (8 bytes):
    # Byte 0: Status/Torque Mode
    # Byte 1: Driver Demand Torque (SPN 512, 8-bit, scale 1.0, offset -125.0)
    # Byte 2: Actual Engine - Percent Torque (SPN 513, 8-bit, scale 1.0, offset -125.0)
    # Bytes 3..4: Engine Speed (SPN 190, 16-bit, scale 0.125, offset 0.0)
    # Bytes 5..7: Other
    payload = bytes([0xF0, 155, 175, 0x00, 0x1F, 0xFF, 0xFF, 0xFF])  # Speed = 0x1F00 = 7936 -> 992.0 rpm

    spn512_def = SignalDefinition(
        name="Driver Demand Engine - Percent Torque",
        spn=512,
        start_bit=8,
        length_bits=8,
        is_signed=False,
        scale=1.0,
        offset=-125.0,
        unit="%",
    )
    spn190_def = SignalDefinition(
        name="Engine Speed",
        spn=190,
        start_bit=24,
        length_bits=16,
        is_signed=False,
        scale=0.125,
        offset=0.0,
        unit="rpm",
    )

    d_torque = decode_signal(payload, spn512_def)
    assert d_torque.quality == SignalQuality.VALID
    assert d_torque.raw_value == 155
    assert d_torque.physical_value == 30.0  # 155 - 125 = 30.0%

    d_speed = decode_signal(payload, spn190_def)
    assert d_speed.quality == SignalQuality.VALID
    assert d_speed.raw_value == 7936  # 0x1F00
    assert d_speed.physical_value == 992.0  # 7936 * 0.125 = 992.0 rpm


def test_decode_signal_aliases_and_class_instances() -> None:
    """Verify class methods, aliases, and instance invocations."""
    sig = SignalDefinition(
        name="Coolant Temp",
        spn=110,
        start_bit=0,
        length_bits=8,
        scale=1.0,
        offset=-40.0,
    )
    payload = b"\x50"  # 80 -> 40 deg C

    # Using J1939SentinelFilter
    d1 = J1939SentinelFilter.decode_signal(payload, sig)
    assert d1.physical_value == 40.0

    # Using J1939SignalDecoder alias
    d2 = J1939SignalDecoder.decode_signal(payload, sig)
    assert d2.physical_value == 40.0

    # Using instance
    decoder = J1939SentinelFilter()
    d3 = decoder.decode_signal(payload, sig)
    assert d3.physical_value == 40.0

    # Using functional helper decode_j1939_signal
    d4 = decode_j1939_signal(80, sig)
    assert d4.physical_value == 40.0


def test_decode_invalid_quality_returns_none_physical_value() -> None:
    """Verify that non-VALID quality returns physical_value=None and raw integer."""
    sig_uint8 = SignalDefinition(name="Test8", spn=100, start_bit=0, length_bits=8, scale=2.0, offset=10.0)
    sig_uint16 = SignalDefinition(name="Test16", spn=101, start_bit=0, length_bits=16, scale=0.5)

    # 8-bit NOT_AVAILABLE
    d_na8 = decode_raw_value(0xFF, sig_uint8)
    assert d_na8.quality == SignalQuality.NOT_AVAILABLE
    assert d_na8.raw_value == 0xFF
    assert d_na8.physical_value is None

    # 8-bit ERROR
    d_err8 = decode_raw_value(0xFE, sig_uint8)
    assert d_err8.quality == SignalQuality.ERROR
    assert d_err8.raw_value == 0xFE
    assert d_err8.physical_value is None

    # 8-bit PARAMETER_SPECIFIC
    d_ps8 = decode_raw_value(0xFB, sig_uint8)
    assert d_ps8.quality == SignalQuality.PARAMETER_SPECIFIC
    assert d_ps8.raw_value == 0xFB
    assert d_ps8.physical_value is None

    # 8-bit RESERVED
    d_res8 = decode_raw_value(0xFC, sig_uint8)
    assert d_res8.quality == SignalQuality.RESERVED
    assert d_res8.raw_value == 0xFC
    assert d_res8.physical_value is None

    # 16-bit NOT_AVAILABLE
    d_na16 = decode_raw_value(0xFFFF, sig_uint16)
    assert d_na16.quality == SignalQuality.NOT_AVAILABLE
    assert d_na16.physical_value is None

    # 16-bit ERROR
    d_err16 = decode_raw_value(0xFE00, sig_uint16)
    assert d_err16.quality == SignalQuality.ERROR
    assert d_err16.physical_value is None


def test_signed_8bit_and_32bit_decoding() -> None:
    """Verify signed 8-bit and 32-bit signal decoding."""
    sig_s8 = SignalDefinition(
        name="Signed 8", spn=200, start_bit=0, length_bits=8, is_signed=True, scale=0.5, offset=10.0
    )
    # 0x80 = -128 -> (-128 * 0.5) + 10.0 = -54.0
    d_s8 = decode_raw_value(0x80, sig_s8)
    assert d_s8.quality == SignalQuality.VALID
    assert d_s8.raw_value == -128
    assert d_s8.physical_value == -54.0

    # 0xFF = NOT_AVAILABLE for signed 8-bit
    d_s8_na = decode_raw_value(0xFF, sig_s8)
    assert d_s8_na.quality == SignalQuality.NOT_AVAILABLE
    assert d_s8_na.physical_value is None

    # 0xFE = ERROR for signed 8-bit
    d_s8_err = decode_raw_value(0xFE, sig_s8)
    assert d_s8_err.quality == SignalQuality.ERROR
    assert d_s8_err.physical_value is None

    sig_s32 = SignalDefinition(
        name="Signed 32", spn=300, start_bit=0, length_bits=32, is_signed=True, scale=1.0, offset=0.0
    )
    # 0xFFFFFF9C = -100
    d_s32 = decode_raw_value(0xFFFFFF9C, sig_s32)
    assert d_s32.quality == SignalQuality.VALID
    assert d_s32.raw_value == -100
    assert d_s32.physical_value == -100.0

    # 0xFFFFFFFF = NOT_AVAILABLE
    d_s32_na = decode_raw_value(0xFFFFFFFF, sig_s32)
    assert d_s32_na.quality == SignalQuality.NOT_AVAILABLE
    assert d_s32_na.physical_value is None


def test_decode_signal_big_endian_payload() -> None:
    """Verify multi-byte big-endian signal decoding from raw payload."""
    sig_be = SignalDefinition(
        name="Big Endian Speed",
        spn=400,
        start_bit=0,
        length_bits=16,
        byte_order="big_endian",
        scale=0.1,
        offset=0.0,
    )
    # In big endian, b"\x03\xe8" = 1000 -> 1000 * 0.1 = 100.0
    payload = b"\x03\xe8\x00\x00"
    d = decode_signal(payload, sig_be)
    assert d.quality == SignalQuality.VALID
    assert d.raw_value == 1000
    assert d.physical_value == 100.0


def test_decode_discrete_2bit_from_payload() -> None:
    """Verify discrete 2-bit signal extraction and decoding from payload."""
    sig_switch = SignalDefinition(
        name="Parking Brake Switch",
        spn=70,
        start_bit=2,
        length_bits=2,
    )
    # Byte 0 = 0b00000100 (bits 2..3 = 0b01 -> VALID On)
    d_on = decode_signal(b"\x04", sig_switch)
    assert d_on.quality == SignalQuality.VALID
    assert d_on.raw_value == 1
    assert d_on.physical_value == 1.0

    # Byte 0 = 0b00001000 (bits 2..3 = 0b10 -> ERROR)
    d_err = decode_signal(b"\x08", sig_switch)
    assert d_err.quality == SignalQuality.ERROR
    assert d_err.physical_value is None

    # Byte 0 = 0b00001100 (bits 2..3 = 0b11 -> NOT_AVAILABLE)
    d_na = decode_signal(b"\x0C", sig_switch)
    assert d_na.quality == SignalQuality.NOT_AVAILABLE
    assert d_na.physical_value is None

