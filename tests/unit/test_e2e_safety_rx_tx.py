"""Unit tests for E2E Safety Rx Validator and Tx Packager.

Verifies stateful sequence counter progression, verdict state transitions (INITIAL, OK, REPEATED,
SOME_LOST, WRONG_SEQUENCE, CRC_ERROR), outbound frame packaging, roundtrips, and multithreaded concurrency.
"""

from __future__ import annotations

import concurrent.futures

import pytest

from src.core.models.can_frame import CanFrame
from src.safety.e2e.packager import E2ESafetyPackager
from src.safety.e2e.profiles import (
    E2EProfileConfig,
    E2EProfileType,
    E2EStatus,
)
from src.safety.e2e.validator import E2ESafetyValidator


class TestE2ESafetyPackager:
    """Validate Tx packager frame stamping, counter increments, and CRC sealing."""

    def test_packager_initial_and_sequential_stamping(self) -> None:
        packager = E2ESafetyPackager()
        profile = E2EProfileConfig.create_autosar_profile_1(data_id=0x1234, variant="1C")

        frame_raw = CanFrame.create(
            channel_id="can0",
            arbitration_id=0x100,
            data=b"\x00\x00\x11\x22\x33\x44\x55\x66",
            direction="tx",
        )

        # First packaged frame -> counter 0
        sealed_0 = packager.package(frame_raw, profile)
        assert sealed_0.direction == "tx"
        assert sealed_0.data[1] & 0x0F == 0
        assert packager.get_counter("can0", 0x100) == 0

        # Second packaged frame -> counter 1
        sealed_1 = packager.package(frame_raw, profile)
        assert sealed_1.data[1] & 0x0F == 1
        assert packager.get_counter("can0", 0x100) == 1

    def test_packager_modulo_wraparound(self) -> None:
        packager = E2ESafetyPackager()
        profile = E2EProfileConfig.create_autosar_profile_1(data_id=0x1234, variant="1C")  # mod 16

        frame = CanFrame.create(
            channel_id="can0",
            arbitration_id=0x200,
            data=b"\x00\x00\x01\x02\x03\x04\x05\x06",
        )

        counters = []
        for _ in range(20):
            sealed = packager.package(frame, profile)
            counters.append(sealed.data[1] & 0x0F)

        expected = list(range(16)) + [0, 1, 2, 3]
        assert counters == expected

    def test_packager_profile_1a_modulo_15_wraparound(self) -> None:
        packager = E2ESafetyPackager()
        profile = E2EProfileConfig.create_autosar_profile_1(data_id=0x1234, variant="1A")  # mod 15

        frame = CanFrame.create(
            channel_id="can0",
            arbitration_id=0x300,
            data=b"\x00\x00\xAA\xBB\xCC\xDD\xEE\xFF",
        )

        counters = []
        for _ in range(18):
            sealed = packager.package(frame, profile)
            counters.append(sealed.data[1] & 0x0F)

        expected = list(range(15)) + [0, 1, 2]
        assert counters == expected

    def test_packager_stream_isolation(self) -> None:
        packager = E2ESafetyPackager()
        profile = E2EProfileConfig.create_autosar_profile_1(data_id=0x1234)

        f1 = CanFrame.create(channel_id="can0", arbitration_id=0x100, data=b"\x00" * 8)
        f2 = CanFrame.create(channel_id="can0", arbitration_id=0x200, data=b"\x00" * 8)
        f3 = CanFrame.create(channel_id="can1", arbitration_id=0x100, data=b"\x00" * 8)

        s1_0 = packager.package(f1, profile)
        s2_0 = packager.package(f2, profile)
        s1_1 = packager.package(f1, profile)
        s3_0 = packager.package(f3, profile)

        assert s1_0.data[1] & 0x0F == 0
        assert s2_0.data[1] & 0x0F == 0
        assert s1_1.data[1] & 0x0F == 1
        assert s3_0.data[1] & 0x0F == 0

    def test_packager_manual_counter_and_reset(self) -> None:
        packager = E2ESafetyPackager()
        profile = E2EProfileConfig.create_autosar_profile_1(data_id=0x1234)
        frame = CanFrame.create(channel_id="can0", arbitration_id=0x100, data=b"\x00" * 8)

        sealed_custom = packager.package(frame, profile, counter=9)
        assert sealed_custom.data[1] & 0x0F == 9
        assert packager.get_counter("can0", 0x100) == 9

        packager.set_counter("can0", 0x100, 14)
        sealed_next = packager.package(frame, profile)
        assert sealed_next.data[1] & 0x0F == 15

        packager.reset("can0", 0x100)
        assert packager.get_counter("can0", 0x100) is None

    def test_package_payload_raw_helper(self) -> None:
        packager = E2ESafetyPackager()
        profile = E2EProfileConfig.create_toyota(crc_byte_offset=7, counter_byte_offset=6)

        data = b"\x10\x20\x30\x40\x50\x60\x00\x00"
        sealed_bytes, counter, crc = packager.package_payload(
            data, profile, arbitration_id=0x2E4, dlc=8
        )
        assert counter == 0
        assert sealed_bytes[6] & 0x0F == 0
        assert sealed_bytes[7] == crc


class TestE2ESafetyValidator:
    """Validate Rx stateful verification engine, delta transitions, and error verdicts."""

    def test_validator_state_progression_initial_and_ok(self) -> None:
        packager = E2ESafetyPackager()
        validator = E2ESafetyValidator()
        profile = E2EProfileConfig.create_autosar_profile_1(data_id=0x55AA, variant="1C")

        raw = CanFrame.create(channel_id="can0", arbitration_id=0x120, data=b"\x00" * 8)

        f0 = packager.package(raw, profile)
        res0 = validator.validate(f0, profile)
        assert res0.verdict == E2EStatus.INITIAL
        assert res0.counter == 0
        assert res0.previous_counter is None
        assert res0.is_valid is True
        assert res0.is_ok is False  # First frame is INITIAL, not OK

        f1 = packager.package(raw, profile)
        res1 = validator.validate(f1, profile)
        assert res1.verdict == E2EStatus.OK
        assert res1.counter == 1
        assert res1.previous_counter == 0
        assert res1.delta == 1
        assert res1.is_ok is True
        assert res1.is_valid is True

    def test_validator_repeated_frame_detection(self) -> None:
        packager = E2ESafetyPackager()
        validator = E2ESafetyValidator()
        profile = E2EProfileConfig.create_autosar_profile_1(data_id=0x55AA)

        raw = CanFrame.create(channel_id="can0", arbitration_id=0x120, data=b"\x00" * 8)
        f0 = packager.package(raw, profile)
        validator.validate(f0, profile)

        # Send exact duplicate frame
        res_repeat = validator.validate(f0, profile)
        assert res_repeat.verdict == E2EStatus.REPEATED
        assert res_repeat.delta == 0
        assert res_repeat.is_ok is False
        assert res_repeat.is_valid is False

        # Next regular frame should still validate as OK (counter incremented from 0 to 1)
        f1 = packager.package(raw, profile)
        res1 = validator.validate(f1, profile)
        assert res1.verdict == E2EStatus.OK
        assert res1.counter == 1

    def test_validator_some_lost_within_max_delta(self) -> None:
        packager = E2ESafetyPackager()
        validator = E2ESafetyValidator()
        profile = E2EProfileConfig.create_autosar_profile_1(data_id=0x1234, max_delta_counter=2)

        raw = CanFrame.create(channel_id="can0", arbitration_id=0x100, data=b"\x00" * 8)
        f0 = packager.package(raw, profile)  # counter 0
        validator.validate(f0, profile)

        # Drop counter 1, send counter 2 (delta = 2, max_delta = 2)
        packager.package(raw, profile)  # dropped frame 1
        f2 = packager.package(raw, profile)  # frame 2
        res2 = validator.validate(f2, profile)

        assert res2.verdict == E2EStatus.SOME_LOST
        assert res2.delta == 2
        assert res2.is_valid is True
        assert res2.is_ok is False

        state = validator.get_stream_state("can0", 0x100)
        assert state is not None
        assert state.dropped_frames_estimated == 1

    def test_validator_wrong_sequence_exceeding_max_delta(self) -> None:
        packager = E2ESafetyPackager()
        validator = E2ESafetyValidator()
        profile = E2EProfileConfig.create_autosar_profile_1(data_id=0x1234, max_delta_counter=2)

        raw = CanFrame.create(channel_id="can0", arbitration_id=0x100, data=b"\x00" * 8)
        f0 = packager.package(raw, profile)  # counter 0
        validator.validate(f0, profile)

        # Jump to counter 5 (delta = 5 > max_delta 2)
        f5 = packager.package(raw, profile, counter=5)
        res5 = validator.validate(f5, profile)

        assert res5.verdict == E2EStatus.WRONG_SEQUENCE
        assert res5.delta == 5
        assert res5.is_valid is False

        state = validator.get_stream_state("can0", 0x100)
        assert state is not None
        assert state.sequence_errors == 1

    def test_validator_crc_error_rejection(self) -> None:
        packager = E2ESafetyPackager()
        validator = E2ESafetyValidator()
        profile = E2EProfileConfig.create_autosar_profile_1(data_id=0x1234)

        raw = CanFrame.create(channel_id="can0", arbitration_id=0x100, data=b"\x00" * 8)
        f0 = packager.package(raw, profile)
        validator.validate(f0, profile)

        # Valid frame 1
        f1 = packager.package(raw, profile)

        # Corrupt data payload byte
        corrupt_data = bytearray(f1.data)
        corrupt_data[4] ^= 0xFF
        corrupted_frame = CanFrame.create(
            channel_id=f1.channel_id,
            arbitration_id=f1.arbitration_id,
            data=bytes(corrupt_data),
        )

        res_corrupt = validator.validate(corrupted_frame, profile)
        assert res_corrupt.verdict == E2EStatus.CRC_ERROR
        assert res_corrupt.is_crc_valid is False
        assert res_corrupt.is_valid is False

        state = validator.get_stream_state("can0", 0x100)
        assert state is not None
        assert state.crc_errors == 1

    def test_validator_wraparound_continuity(self) -> None:
        packager = E2ESafetyPackager()
        validator = E2ESafetyValidator()
        profile = E2EProfileConfig.create_autosar_profile_1(data_id=0x1234)  # mod 16

        raw = CanFrame.create(channel_id="can0", arbitration_id=0x100, data=b"\x00" * 8)

        # Initialize and run up to counter 15
        for c in range(16):
            f = packager.package(raw, profile, counter=c)
            res = validator.validate(f, profile)
            if c == 0:
                assert res.verdict == E2EStatus.INITIAL
            else:
                assert res.verdict == E2EStatus.OK

        # Counter 15 -> 0 (wrap-around delta 1)
        f_wrap = packager.package(raw, profile, counter=0)
        res_wrap = validator.validate(f_wrap, profile)
        assert res_wrap.verdict == E2EStatus.OK
        assert res_wrap.delta == 1

    def test_validator_stream_reset(self) -> None:
        packager = E2ESafetyPackager()
        validator = E2ESafetyValidator()
        profile = E2EProfileConfig.create_autosar_profile_1(data_id=0x1234)

        raw1 = CanFrame.create(channel_id="can0", arbitration_id=0x100, data=b"\x00" * 8)
        raw2 = CanFrame.create(channel_id="can0", arbitration_id=0x200, data=b"\x00" * 8)

        validator.validate(packager.package(raw1, profile), profile)
        validator.validate(packager.package(raw2, profile), profile)

        assert len(validator.get_all_states()) == 2

        validator.reset("can0", 0x100)
        assert validator.get_stream_state("can0", 0x100) is None
        assert validator.get_stream_state("can0", 0x200) is not None

        validator.reset()
        assert len(validator.get_all_states()) == 0


class TestE2EProfilesRoundtripIntegrity:
    """Validate full transmission and reception roundtrips across all supported profiles."""

    @pytest.mark.parametrize(
        "profile",
        [
            E2EProfileConfig.create_autosar_profile_1(data_id=0x0123, variant="1C"),
            E2EProfileConfig.create_autosar_profile_1(data_id=0x0123, variant="1B"),
            E2EProfileConfig.create_autosar_profile_1(data_id=0x0123, variant="1A"),
            E2EProfileConfig.create_autosar_profile_2(list(range(0x10, 0x20))),
            E2EProfileConfig.create_sae_j1850(),
            E2EProfileConfig.create_toyota(crc_byte_offset=7, counter_byte_offset=6),
            E2EProfileConfig.create_vag_mqb(data_id=0x4321),
            E2EProfileConfig.create_volvo(crc_byte_offset=7, counter_byte_offset=1),
        ],
    )
    def test_all_profiles_100_frame_clean_stream(self, profile: E2EProfileConfig) -> None:
        packager = E2ESafetyPackager()
        validator = E2ESafetyValidator()

        raw_payload = b"\x00\x00\x11\x22\x33\x44\x55\x66"
        can_id = 0x250

        for seq in range(100):
            frame = CanFrame.create(
                channel_id="can0",
                arbitration_id=can_id,
                data=raw_payload,
            )
            sealed = packager.package(frame, profile)
            result = validator.validate(sealed, profile)

            if seq == 0:
                assert result.verdict == E2EStatus.INITIAL
            else:
                assert result.verdict == E2EStatus.OK, f"Failed at seq {seq} for {profile.profile_type}"
            assert result.is_valid is True
            assert result.is_crc_valid is True

        state = validator.get_stream_state("can0", can_id)
        assert state is not None
        assert state.total_frames == 100
        assert state.valid_frames == 100
        assert state.crc_errors == 0
        assert state.sequence_errors == 0


class TestE2EConcurrencyStress:
    """Stress test packager and validator under high-frequency multithreaded concurrent streams."""

    def test_concurrent_streams_thread_safety(self) -> None:
        packager = E2ESafetyPackager()
        validator = E2ESafetyValidator()
        profile = E2EProfileConfig.create_autosar_profile_1(data_id=0xABCD)

        num_streams = 8
        frames_per_stream = 50

        def run_stream(stream_idx: int) -> int:
            arb_id = 0x100 + stream_idx
            channel = f"can{stream_idx % 2}"
            raw = CanFrame.create(channel_id=channel, arbitration_id=arb_id, data=b"\x00" * 8)
            valid_count = 0

            for _ in range(frames_per_stream):
                sealed = packager.package(raw, profile)
                res = validator.validate(sealed, profile)
                if res.is_valid:
                    valid_count += 1
            return valid_count

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(run_stream, i) for i in range(num_streams)]
            results = [f.result() for f in futures]

        assert all(count == frames_per_stream for count in results)

        all_states = validator.get_all_states()
        assert len(all_states) == num_streams
        for state in all_states.values():
            assert state.total_frames == frames_per_stream
            assert state.valid_frames == frames_per_stream
            assert state.crc_errors == 0
            assert state.sequence_errors == 0


class TestE2ESafetyEdgeCasesAndVariants:
    """Validate advanced configurations, payload sizing, and corner cases."""

    def test_validate_raw_buffer_api(self) -> None:
        packager = E2ESafetyPackager()
        validator = E2ESafetyValidator()
        profile = E2EProfileConfig.create_toyota(crc_byte_offset=7, counter_byte_offset=6)

        data = b"\x01\x02\x03\x04\x05\x06\x00\x00"
        sealed_0, _, _ = packager.package_payload(data, profile, arbitration_id=0x1A0, dlc=8)
        res_0 = validator.validate_raw("can0", 0x1A0, sealed_0, profile, dlc=8)
        assert res_0.verdict == E2EStatus.INITIAL

        sealed_1, _, _ = packager.package_payload(data, profile, arbitration_id=0x1A0, dlc=8)
        res_1 = validator.validate_raw("can0", 0x1A0, sealed_1, profile, dlc=8)
        assert res_1.verdict == E2EStatus.OK
        assert res_1.counter == 1

    def test_high_nibble_counter_mask_and_shift(self) -> None:
        packager = E2ESafetyPackager()
        validator = E2ESafetyValidator()
        profile = E2EProfileConfig(
            profile_type=E2EProfileType.CUSTOM,
            crc_byte_offset=0,
            counter_byte_offset=1,
            counter_bit_mask=0xF0,
            counter_bit_shift=4,
            counter_modulo=16,
            max_delta_counter=3,
        )

        raw = CanFrame.create(channel_id="can0", arbitration_id=0x500, data=b"\x00\x0A\x22\x33\x44\x55\x66\x77")

        # First frame -> counter 0 in upper nibble, lower nibble (0x0A) preserved
        s0 = packager.package(raw, profile)
        assert s0.data[1] & 0xF0 == 0x00
        assert s0.data[1] & 0x0F == 0x0A
        r0 = validator.validate(s0, profile)
        assert r0.verdict == E2EStatus.INITIAL
        assert r0.counter == 0

        # Second frame -> counter 1 in upper nibble
        s1 = packager.package(raw, profile)
        assert s1.data[1] & 0xF0 == 0x10
        assert s1.data[1] & 0x0F == 0x0A
        r1 = validator.validate(s1, profile)
        assert r1.verdict == E2EStatus.OK
        assert r1.counter == 1

    def test_undersized_payload_auto_expansion(self) -> None:
        packager = E2ESafetyPackager()
        profile = E2EProfileConfig.create_toyota(crc_byte_offset=7, counter_byte_offset=6)

        # 3-byte payload, offsets require at least 8 bytes
        short_frame = CanFrame.create(channel_id="can0", arbitration_id=0x123, data=b"\xAA\xBB\xCC")
        sealed = packager.package(short_frame, profile)
        assert len(sealed.data) >= 8
        assert sealed.data[0:3] == b"\xAA\xBB\xCC"

    def test_large_max_delta_counter_boundary(self) -> None:
        packager = E2ESafetyPackager()
        validator = E2ESafetyValidator()
        profile = E2EProfileConfig.create_autosar_profile_1(data_id=0x9999, max_delta_counter=5)

        raw = CanFrame.create(channel_id="can0", arbitration_id=0x100, data=b"\x00" * 8)
        validator.validate(packager.package(raw, profile, counter=0), profile)

        # Delta = 5 (allowed under max_delta_counter=5)
        res_5 = validator.validate(packager.package(raw, profile, counter=5), profile)
        assert res_5.verdict == E2EStatus.SOME_LOST
        assert res_5.delta == 5

        # Delta = 6 (exceeds max_delta_counter=5)
        res_11 = validator.validate(packager.package(raw, profile, counter=11), profile)
        assert res_11.verdict == E2EStatus.WRONG_SEQUENCE
        assert res_11.delta == 6

