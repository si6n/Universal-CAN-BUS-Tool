"""Integration tests verifying Golden-Traces benchmark vectors against master specifications.

Implements MASTER_PLAN.md Section 18 test pyramid requirements using real-world
benchmark traces and golden YAML expectations from the Golden-Traces corpus.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from src.hal.replay.parsers import VectorAscParser
from src.hal.replay.safety_filter import ReplaySafetyFilter

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "benchmarks"
VECTORS_DIR = FIXTURES_DIR / "vectors"
EXPECTED_DIR = FIXTURES_DIR / "expected"

CAN_BENCHMARK_VECTORS = [
    "j1939_dm1_single",
    "j1939_dm1_bam_multiframe",
    "j1939_cmdt_rts_cts",
    "j1939_address_claim_win",
    "j1939_address_claim_loss",
    "j1939_dm11_clear_ack",
    "n2k_engine_rapid",
    "n2k_fast_packet_dynamic",
    "n2k_transmission_dynamic",
    "n2k_fluid_level",
    "uds_iso15765_flow_control",
    "uds_routine_compression",
    "road_correlated_signal",
]


def load_golden_spec(name: str) -> dict[str, Any]:
    golden_file = EXPECTED_DIR / f"{name}.golden.yaml"
    assert golden_file.exists(), f"Golden expectation file missing: {golden_file}"
    return yaml.safe_load(golden_file.read_text(encoding="utf-8"))


@pytest.mark.parametrize("vector_name", CAN_BENCHMARK_VECTORS)
def test_can_benchmark_vector_conformance(vector_name: str) -> None:
    """Verify each benchmark vector parses cleanly and matches its golden specification."""
    asc_path = VECTORS_DIR / f"{vector_name}.asc"
    assert asc_path.exists(), f"Benchmark ASC file missing: {asc_path}"

    frames = VectorAscParser.parse_file(asc_path)
    golden = load_golden_spec(vector_name)

    # 1. Total frame count
    assert len(frames) == golden["frames"], f"Frame count mismatch for {vector_name}"

    # 2. DLC distribution
    dlc_dist: dict[int, int] = {}
    for fr in frames:
        dlc_dist[fr.dlc] = dlc_dist.get(fr.dlc, 0) + 1
    assert dlc_dist == golden["dlc_distribution"], f"DLC distribution mismatch for {vector_name}"

    # 3. Extended ID check
    if golden.get("all_extended"):
        assert all(f.is_extended for f in frames), f"Expected all extended frames for {vector_name}"

    # 4. Unique arbitration IDs count
    unique_ids = len({f.arbitration_id for f in frames})
    assert unique_ids == golden["unique_ids"], f"Unique IDs mismatch for {vector_name}"

    # 5. Timestamp strict non-decreasing monotonicity
    timestamps = [f.timestamp_ns for f in frames]
    assert timestamps == sorted(timestamps), f"Timestamp monotonicity violated for {vector_name}"


def test_j1708_vector_rejected_by_design() -> None:
    """Volvo MID128 (J1708/J1587 on RS-485 with payload > 8 bytes) is rejected by CAN parser."""
    asc_path = VECTORS_DIR / "volvo_mid128_pid100.asc"
    assert asc_path.exists()
    with pytest.raises(ValueError, match="Invalid DLC|DLC"):
        VectorAscParser.parse_file(asc_path)


def test_replay_safety_filter_on_benchmark_vectors() -> None:
    """Verify ReplaySafetyFilter correctly identifies hazardous vs benign benchmark frames."""
    safety_filter = ReplaySafetyFilter()

    # 1. Address Claiming should be blocked
    win_frames = VectorAscParser.parse_file(VECTORS_DIR / "j1939_address_claim_win.asc")
    blocked_claims = [f for f in win_frames if not safety_filter.is_frame_safe(f)[0]]
    assert len(blocked_claims) > 0, "Address claiming frames must be blocked by safety filter"

    # 2. RoutineControl (UDS 0x31 request) should be blocked, while 0x71 response is allowed
    uds_frames = VectorAscParser.parse_file(VECTORS_DIR / "uds_routine_compression.asc")
    blocked_uds = [f for f in uds_frames if not safety_filter.is_frame_safe(f)[0]]
    assert len(blocked_uds) == 1, "UDS 0x31 RoutineControl request must be blocked"
    assert blocked_uds[0].data[1] == 0x31, "The blocked frame must be the 0x31 request"

    # 3. Benign DM1 frames should pass
    dm1_frames = VectorAscParser.parse_file(VECTORS_DIR / "j1939_dm1_single.asc")
    passed_dm1 = [f for f in dm1_frames if safety_filter.is_frame_safe(f)[0]]
    assert len(passed_dm1) == len(dm1_frames), "Benign DM1 frames must pass safely"
