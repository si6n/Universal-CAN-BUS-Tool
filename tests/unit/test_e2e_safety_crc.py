"""Unit tests for E2E CRC-8 mathematical foundations and lookup tables.

Tests Polynomial 0x1D (SAE J1850 / AUTOSAR Profile 1) and 0x2F (AUTOSAR Profile 2 / VAG MQB),
verifying lookup tables, bitwise calculations, standard test vectors, and error detection.
"""

from __future__ import annotations

import pytest

from src.safety.e2e.crc import (
    CRC8_TABLE_0X1D,
    CRC8_TABLE_0X2F,
    POLYNOMIAL_0X1D,
    POLYNOMIAL_0X2F,
    calculate_crc8,
    calculate_crc8_0x1d,
    calculate_crc8_0x2f,
    calculate_crc8_bitwise,
    calculate_crc8_sae_j1850,
    calculate_crc8_update,
    generate_crc8_table,
)


class TestCrc8LookupTables:
    """Validate 256-entry precomputed lookup tables against dynamic bitwise generation."""

    def test_crc8_table_0x1d_dimensions_and_generation(self) -> None:
        generated = generate_crc8_table(POLYNOMIAL_0X1D)
        assert len(generated) == 256
        assert len(CRC8_TABLE_0X1D) == 256
        assert generated == CRC8_TABLE_0X1D
        assert generated[0] == 0x00
        assert generated[1] == 0x1D
        assert generated[255] == 0xC4

    def test_crc8_table_0x2f_dimensions_and_generation(self) -> None:
        generated = generate_crc8_table(POLYNOMIAL_0X2F)
        assert len(generated) == 256
        assert len(CRC8_TABLE_0X2F) == 256
        assert generated == CRC8_TABLE_0X2F
        assert generated[0] == 0x00
        assert generated[1] == 0x2F
        assert generated[255] == 0x42


class TestCrc8StandardTestVectors:
    """Validate authoritative test vectors from AUTOSAR, SAE J1850, and CRC-8 standards."""

    @pytest.mark.parametrize(
        ("data", "expected_0x1d", "expected_0x2f"),
        [
            (b"123456789", 0x4B, 0xDF),
            (b"\x00\x00\x00\x00", 0x59, 0x12),
            (b"\xFF\xFF\xFF\xFF", 0x74, 0x6C),
            (b"", 0x00, 0x00),
            (b"\x00", 0x3B, 0xBD),
            (b"\xFF", 0xFF, 0xFF),
            (b"\x01\x02\x03\x04\x05\x06\x07\x08", 0xB4, 0x19),
        ],
    )
    def test_standard_test_vectors(self, data: bytes, expected_0x1d: int, expected_0x2f: int) -> None:
        # Table-based calculation
        assert calculate_crc8_0x1d(data) == expected_0x1d
        assert calculate_crc8_0x2f(data) == expected_0x2f

        # Bitwise reference calculation
        assert calculate_crc8_bitwise(data, poly=POLYNOMIAL_0X1D) == expected_0x1d
        assert calculate_crc8_bitwise(data, poly=POLYNOMIAL_0X2F) == expected_0x2f

        # Generic dispatch function
        assert calculate_crc8(data, poly=POLYNOMIAL_0X1D) == expected_0x1d
        assert calculate_crc8(data, poly=POLYNOMIAL_0X2F) == expected_0x2f

    def test_sae_j1850_helper(self) -> None:
        assert calculate_crc8_sae_j1850(b"123456789") == 0x4B
        assert calculate_crc8_sae_j1850(b"\x00\x00\x00\x00") == 0x59


class TestCrc8BitwiseEquivalenceAndProperties:
    """Verify bitwise and table-based calculations produce identical results across varied byte sequences."""

    def test_bitwise_matches_table_lookup_exhaustive_patterns(self) -> None:
        test_patterns = [
            bytes([i for i in range(256)]),
            bytes([255 - i for i in range(256)]),
            bytes([0xAA] * 64),
            bytes([0x55] * 64),
            bytes([0x00, 0xFF, 0x55, 0xAA, 0x12, 0x34, 0x56, 0x78]),
        ]
        for pattern in test_patterns:
            # 0x1D
            res_table_1d = calculate_crc8_0x1d(pattern)
            res_bit_1d = calculate_crc8_bitwise(pattern, poly=POLYNOMIAL_0X1D)
            assert res_table_1d == res_bit_1d

            # 0x2F
            res_table_2f = calculate_crc8_0x2f(pattern)
            res_bit_2f = calculate_crc8_bitwise(pattern, poly=POLYNOMIAL_0X2F)
            assert res_table_2f == res_bit_2f

    def test_progressive_update_equivalence(self) -> None:
        data = b"Hello AUTOSAR E2E Safety!"
        chunk1 = data[:10]
        chunk2 = data[10:]

        # One-shot calculation
        one_shot = calculate_crc8_0x1d(data)

        # Progressive calculation
        crc_running = calculate_crc8_update(0xFF, chunk1, table=CRC8_TABLE_0X1D)
        crc_running = calculate_crc8_update(crc_running, chunk2, table=CRC8_TABLE_0X1D)
        progressive_res = crc_running ^ 0xFF

        assert progressive_res == one_shot

    def test_single_bit_flip_detection(self) -> None:
        original = bytearray(b"\x10\x20\x30\x40\x50\x60\x70\x80")
        original_crc_1d = calculate_crc8_0x1d(original)
        original_crc_2f = calculate_crc8_0x2f(original)

        for byte_idx in range(len(original)):
            for bit_idx in range(8):
                mutated = bytearray(original)
                mutated[byte_idx] ^= 1 << bit_idx
                assert calculate_crc8_0x1d(mutated) != original_crc_1d
                assert calculate_crc8_0x2f(mutated) != original_crc_2f

    def test_custom_polynomial_generation_and_calculation(self) -> None:
        # Polynomial 0x07 (CRC-8-CCITT / SMBus)
        custom_poly = 0x07
        table_0x07 = generate_crc8_table(custom_poly)
        assert len(table_0x07) == 256
        data = b"123456789"
        res_table = calculate_crc8(data, poly=custom_poly, table=table_0x07, init_val=0x00, final_xor=0x00)
        res_bitwise = calculate_crc8_bitwise(data, poly=custom_poly, init_val=0x00, final_xor=0x00)
        assert res_table == res_bitwise
        assert res_table == 0xF4  # standard CRC-8/SMBus check value
