"""Unit tests for E2E Safety Profiles and Checksum Engines.

Tests AUTOSAR Profile 1 (1A, 1B, 1C), AUTOSAR Profile 2, SAE J1850, Toyota, VAG MQB, and Volvo profiles.
"""

from __future__ import annotations

import pytest

from src.safety.e2e.profiles import (
    E2EProfileConfig,
    E2EProfileType,
    compute_checksum,
    extract_counter,
    extract_crc,
    inject_counter,
    inject_crc,
)


class TestE2EProfileFactoriesAndValidation:
    """Validate profile configuration factories and sanity guards."""

    def test_autosar_profile_1_factory(self) -> None:
        p1c = E2EProfileConfig.create_autosar_profile_1(data_id=0x0123, variant="1C")
        assert p1c.profile_type == E2EProfileType.AUTOSAR_PROFILE_1C
        assert p1c.data_id == 0x0123
        assert p1c.counter_modulo == 16
        assert p1c.crc_byte_offset == 0
        assert p1c.counter_byte_offset == 1

        p1a = E2EProfileConfig.create_autosar_profile_1(data_id=0x0456, variant="1A")
        assert p1a.profile_type == E2EProfileType.AUTOSAR_PROFILE_1A
        assert p1a.counter_modulo == 15

        p1b = E2EProfileConfig.create_autosar_profile_1(data_id=0x0789, variant="1B")
        assert p1b.profile_type == E2EProfileType.AUTOSAR_PROFILE_1B
        assert p1b.counter_modulo == 16

    def test_autosar_profile_2_factory(self) -> None:
        valid_list = list(range(0x10, 0x20))
        p2 = E2EProfileConfig.create_autosar_profile_2(valid_list)
        assert p2.profile_type == E2EProfileType.AUTOSAR_PROFILE_2
        assert len(p2.data_id_list) == 16  # type: ignore[arg-type]
        assert p2.counter_modulo == 16

        with pytest.raises(ValueError, match="requires exactly 16 Data IDs"):
            E2EProfileConfig.create_autosar_profile_2([1, 2, 3])

    def test_oem_profile_factories(self) -> None:
        toyota = E2EProfileConfig.create_toyota(crc_byte_offset=7, counter_byte_offset=6)
        assert toyota.profile_type == E2EProfileType.TOYOTA
        assert toyota.crc_byte_offset == 7
        assert toyota.counter_byte_offset == 6
        assert toyota.include_can_id_in_crc is True

        vag = E2EProfileConfig.create_vag_mqb(data_id=0x1234)
        assert vag.profile_type == E2EProfileType.VAG_MQB
        assert vag.data_id == 0x1234
        assert vag.crc_byte_offset == 0

        volvo = E2EProfileConfig.create_volvo()
        assert volvo.profile_type == E2EProfileType.VOLVO
        assert volvo.crc_byte_offset == 7

    def test_invalid_parameters_raise(self) -> None:
        with pytest.raises(ValueError, match="counter_modulo must be positive"):
            E2EProfileConfig(profile_type=E2EProfileType.SAE_J1850, counter_modulo=0)

        with pytest.raises(ValueError, match="max_delta_counter must be positive"):
            E2EProfileConfig(profile_type=E2EProfileType.SAE_J1850, max_delta_counter=0)

        with pytest.raises(ValueError, match="crc_byte_offset must be non-negative"):
            E2EProfileConfig(profile_type=E2EProfileType.SAE_J1850, crc_byte_offset=-1)


class TestE2EChecksumCalculations:
    """Validate checksum routines against authoritative test vectors."""

    def test_autosar_profile_1c_test_vector(self) -> None:
        # Spec Section 9.2: Data ID = 0x0123, Counter = 0x05, Payload bytes 1..7 = 05 11 22 33 44 55 66
        # Buffer = 23 01 05 11 22 33 44 55 66 -> CRC-8 (0x1D) = 0x95
        cfg = E2EProfileConfig.create_autosar_profile_1(data_id=0x0123, variant="1C")
        raw_frame = bytes([0x00, 0x05, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66])
        crc = compute_checksum(raw_frame, cfg)
        assert crc == 0x95

    def test_autosar_profile_1a_and_1b_calculations(self) -> None:
        data = bytes([0x00, 0x04, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF])
        cfg_1a = E2EProfileConfig.create_autosar_profile_1(data_id=0x0521, variant="1A")
        crc_1a = compute_checksum(data, cfg_1a)
        assert isinstance(crc_1a, int)
        assert 0 <= crc_1a <= 0xFF

        cfg_1b = E2EProfileConfig.create_autosar_profile_1(data_id=0x0521, variant="1B")
        crc_1b = compute_checksum(data, cfg_1b)
        assert isinstance(crc_1b, int)
        assert 0 <= crc_1b <= 0xFF
        assert crc_1a != crc_1b

    def test_autosar_profile_2_test_vector(self) -> None:
        # Spec Section 9.3:
        # Data ID List: [0x10..0x1F], Counter = 0x02 (Selected Data ID = 0x12)
        # Payload bytes 1..7 = 02 AA BB CC DD EE FF -> Buffer = 02 AA BB CC DD EE FF 12 -> CRC-8 (0x2F) = 0x6D
        data_id_list = list(range(0x10, 0x20))
        cfg = E2EProfileConfig.create_autosar_profile_2(data_id_list)
        raw_frame = bytes([0x00, 0x02, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF])
        crc = compute_checksum(raw_frame, cfg)
        assert crc == 0x6D

    def test_toyota_checksum_test_vector(self) -> None:
        # Spec Section 9.4:
        # CAN_ID = 0x2E4, Payload = 10 20 30 40 50 60 01 (Byte 7 is CRC slot), DLC = 8
        # Sum = 0x10 + 0x20 + 0x30 + 0x40 + 0x50 + 0x60 + 0x01 + 0x02 + 0xE4 + 8 = 0x023F & 0xFF = 0x3F
        cfg = E2EProfileConfig.create_toyota(crc_byte_offset=7, counter_byte_offset=6, include_can_id=True, include_dlc=True)
        raw_frame = bytes([0x10, 0x20, 0x30, 0x40, 0x50, 0x60, 0x01, 0x00])
        crc = compute_checksum(raw_frame, cfg, arbitration_id=0x2E4, dlc=8)
        assert crc == 0x3F

    def test_vag_mqb_test_vector(self) -> None:
        # Spec Section 9.4:
        # DataID = 0x1234, Payload = 00 01 02 03 04 05 06 07 (Byte 0 is CRC slot)
        # Calculation input: 01 02 03 04 05 06 07 34 12
        # Expected Checksum = 0xA4
        cfg = E2EProfileConfig.create_vag_mqb(data_id=0x1234)
        raw_frame = bytes([0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07])
        crc = compute_checksum(raw_frame, cfg)
        assert crc == 0xA4

    def test_volvo_checksum_test_vector(self) -> None:
        # Spec Section 9.4:
        # Payload (Bytes 0..6) = 10 20 30 40 50 60 01, Byte 7 is CRC slot
        # Sum = 0x51 -> Checksum = ~0x51 & 0xFF = 0xAE
        cfg = E2EProfileConfig.create_volvo(crc_byte_offset=7, counter_byte_offset=6)
        raw_frame = bytes([0x10, 0x20, 0x30, 0x40, 0x50, 0x60, 0x01, 0x00])
        crc = compute_checksum(raw_frame, cfg)
        assert crc == 0xAE

    def test_sae_j1850_profile_checksum(self) -> None:
        cfg = E2EProfileConfig.create_sae_j1850(crc_byte_offset=0)
        raw_frame = bytes([0x00, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37])
        crc = compute_checksum(raw_frame, cfg)
        assert isinstance(crc, int)
        assert 0 <= crc <= 0xFF


class TestFieldExtractAndInjectHelpers:
    """Validate nibble and byte level counter/CRC injection and extraction routines."""

    def test_counter_extraction_and_injection_low_nibble(self) -> None:
        cfg = E2EProfileConfig.create_autosar_profile_1(
            data_id=0x1000,
            counter_byte_offset=1,
            counter_bit_mask=0x0F,
            counter_bit_shift=0,
        )
        buf = bytearray(b"\x00\x00\x00\x00\x00\x00\x00\x00")
        inject_counter(buf, 7, cfg)
        assert buf[1] == 0x07
        assert extract_counter(buf, cfg) == 7

        # Ensure high nibble bits are preserved
        buf[1] = 0xF0
        inject_counter(buf, 11, cfg)
        assert buf[1] == 0xFB
        assert extract_counter(buf, cfg) == 11

    def test_counter_extraction_and_injection_high_nibble(self) -> None:
        cfg = E2EProfileConfig(
            profile_type=E2EProfileType.CUSTOM,
            counter_byte_offset=1,
            counter_bit_mask=0xF0,
            counter_bit_shift=4,
        )
        buf = bytearray(b"\x00\x05\x00\x00\x00\x00\x00\x00")
        inject_counter(buf, 9, cfg)
        assert buf[1] == 0x95
        assert extract_counter(buf, cfg) == 9

    def test_crc_extraction_and_injection(self) -> None:
        cfg = E2EProfileConfig.create_autosar_profile_1(data_id=0x1000, crc_byte_offset=0)
        buf = bytearray(b"\x00\x01\x02\x03\x04\x05\x06\x07")
        inject_crc(buf, 0xA5, cfg)
        assert buf[0] == 0xA5
        assert extract_crc(buf, cfg) == 0xA5

        cfg_tail = E2EProfileConfig.create_toyota(crc_byte_offset=7)
        inject_crc(buf, 0x5A, cfg_tail)
        assert buf[7] == 0x5A
        assert extract_crc(buf, cfg_tail) == 0x5A

    def test_short_payload_raises_value_error(self) -> None:
        cfg = E2EProfileConfig.create_toyota(crc_byte_offset=7, counter_byte_offset=6)
        short_buf = bytearray(b"\x01\x02")
        with pytest.raises(ValueError, match="too short for counter offset"):
            extract_counter(short_buf, cfg)
        with pytest.raises(ValueError, match="too short for counter offset"):
            inject_counter(short_buf, 1, cfg)
        with pytest.raises(ValueError, match="too short for CRC offset"):
            extract_crc(short_buf, cfg)
        with pytest.raises(ValueError, match="too short for CRC offset"):
            inject_crc(short_buf, 0x10, cfg)
