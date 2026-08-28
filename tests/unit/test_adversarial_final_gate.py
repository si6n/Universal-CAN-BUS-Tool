"""Final Adversarial Stress & Forensic Invariant Test Suite.

Exhaustively verifies system behavior under adversarial, boundary, race condition,
and malformed input scenarios across:
1. E-Stop & TX Safety Gateway
2. HWID Collection & Nonce/HMAC Integrity
3. Anti-Tamper & Ed25519 License Validation
4. Non-Blocking UDS Client & ISO-TP Engine
5. DBC J1939 PGN Routing & LRU Cache Mechanics
6. AI Diagnostic Copilot & Resilient JSON/Markdown Parser
"""

from __future__ import annotations

import base64
import collections
import hashlib
import hmac
import json
import os
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.core.errors import LicenseError, SafetyError
from src.core.models.can_frame import CanFrame
from src.engine.ai.diagnostic_copilot import (
    AiDiagnosticCopilot,
    FaultSeverity,
)
from src.engine.decoder.dbc_decoder import DbcSignalDecoder
from src.hal.base import AbstractBus, BusState
from src.protocols.uds.client import UdsClient
from src.protocols.uds.isotp import IsoTpTransport
from src.protocols.uds.nrc import UdsNrc
from src.protocols.uds.services import (
    DiagnosticSessionType,
)
from src.safety.estop import EmergencyStopSystem, EStopEvent, EStopTriggerSource
from src.safety.gateway import TxSafetyGateway
from src.security.hwid.collector import (
    _INVALID_UUIDS,
    collect_bios_serial,
    collect_cpu_processor_id,
    collect_disk_serial,
    collect_motherboard_uuid,
    generate_hardware_fingerprint,
)
from src.security.license.validator import LicenseValidator

# ============================================================================
# Dummy Bus for Testing
# ============================================================================


class MockTestingBus(AbstractBus):
    """Thread-safe mock bus capturing all sent frames and simulating receive queues."""

    def __init__(self, channel_id: str = "mock_bus") -> None:
        super().__init__(channel_id=channel_id)
        self.sent_frames: list[CanFrame] = []
        self.rx_queue: collections.deque[CanFrame] = collections.deque()
        self._lock = threading.Lock()

    def connect(self) -> None:
        self.is_connected = True
        self.metrics.state = BusState.ACTIVE

    def disconnect(self) -> None:
        self.is_connected = False
        self.metrics.state = BusState.DISCONNECTED

    def _send_raw(self, frame: CanFrame) -> None:
        with self._lock:
            self.sent_frames.append(frame)
            self.metrics.tx_frames += 1

    def recv(self, timeout_s: float | None = 0.1) -> CanFrame | None:
        with self._lock:
            if self.rx_queue:
                frame = self.rx_queue.popleft()
                self.metrics.rx_frames += 1
                return frame
        if timeout_s is not None and timeout_s > 0:
            time.sleep(min(timeout_s, 0.01))
        return None

    def push_rx_frame(self, frame: CanFrame) -> None:
        with self._lock:
            self.rx_queue.append(frame)


# ============================================================================
# 1. E-STOP & TX SAFETY GATEWAY ADVERSARIAL TESTS
# ============================================================================


def test_all_10_estop_trigger_sources_record_and_dispatch() -> None:
    """Verify each of the 10 defined E-Stop triggers correctly captures state."""
    secret = os.urandom(32)
    estop = EmergencyStopSystem(reset_secret=secret)
    events_captured: list[EStopEvent] = []
    estop.register_callback(events_captured.append)

    for idx, trigger in enumerate(EStopTriggerSource):
        estop.trigger(trigger, f"Test reason {idx}", vehicle_speed_kmh=float(idx * 10))
        assert estop.is_engaged is True
        assert estop.last_event is not None
        assert estop.last_event.trigger == trigger
        assert estop.last_event.system_speed_kmh == float(idx * 10)
        assert len(events_captured) == idx + 1

        nonce = estop.get_reset_nonce()
        assert len(nonce) == 16
        token = estop.compute_reset_token(nonce)
        estop.reset(token)
        assert estop.is_engaged is False
        assert estop.last_event is None


def test_estop_callback_exception_safety() -> None:
    """Ensure faulty callbacks do not prevent other callbacks or crash trigger flow."""
    estop = EmergencyStopSystem()
    broken_called = False
    good_called = False

    def broken_cb(ev: EStopEvent) -> None:
        nonlocal broken_called
        broken_called = True
        raise RuntimeError("Catastrophic callback failure")

    def good_cb(ev: EStopEvent) -> None:
        nonlocal good_called
        good_called = True

    estop.register_callback(broken_cb)
    estop.register_callback(good_cb)

    estop.trigger(EStopTriggerSource.HARDWARE_DISCONNECT, "Safety break")
    assert broken_called is True
    assert good_called is True
    assert estop.is_engaged is True


def test_estop_multithreaded_rapid_trigger_reset_race() -> None:
    """Stress test concurrent triggers and resets under 20 concurrent threads."""
    secret = b"fixed_super_secret_key_for_test"
    estop = EmergencyStopSystem(reset_secret=secret)
    stop_event = threading.Event()
    errors: list[Exception] = []

    def hammer_trigger(worker_id: int) -> None:
        while not stop_event.is_set():
            try:
                estop.trigger(
                    EStopTriggerSource.RATE_LIMIT_OVERFLOW,
                    f"Hammer from thread {worker_id}",
                )
            except Exception as exc:
                errors.append(exc)

    def hammer_reset() -> None:
        while not stop_event.is_set():
            try:
                nonce = estop.get_reset_nonce()
                if nonce:
                    token = hmac.new(secret, nonce, hashlib.sha256).hexdigest()
                    estop.reset(token)
            except SafetyError:
                # Expected if nonce rotated between read and reset
                pass
            except Exception as exc:
                errors.append(exc)

    threads = [threading.Thread(target=hammer_trigger, args=(i,)) for i in range(10)] + [
        threading.Thread(target=hammer_reset) for _ in range(10)
    ]

    for t in threads:
        t.start()

    time.sleep(0.3)
    stop_event.set()

    for t in threads:
        t.join()

    assert not errors, f"Unexpected exceptions during concurrency hammer: {errors}"


def test_gateway_complete_rule_matrix() -> None:
    """Exhaustive check of Gateway Rules 1 through 5."""
    bus = MockTestingBus()
    estop = EmergencyStopSystem()
    gateway = TxSafetyGateway(bus=bus, estop=estop, whitelist_ids={0x100, 0x200})

    frame_valid = CanFrame.create(channel_id="ch0", arbitration_id=0x100, data=b"\x01\x02\x03\x04")
    frame_non_whitelist = CanFrame.create(channel_id="ch0", arbitration_id=0x999, data=b"\x00")

    # Rule 2: Whitelist violation triggers EStop
    with pytest.raises(SafetyError, match="not in whitelist"):
        gateway.validate_and_transmit(frame_non_whitelist)
    assert estop.is_engaged is True
    assert estop.last_event is not None
    assert estop.last_event.trigger == EStopTriggerSource.UNAUTHORIZED_PAYLOAD

    # Rule 1: EStop blocks everything
    with pytest.raises(SafetyError, match="Emergency Stop is currently ENGAGED"):
        gateway.validate_and_transmit(frame_valid)

    # Reset E-Stop
    nonce = estop.get_reset_nonce()
    estop.reset(estop.compute_reset_token(nonce))
    assert estop.is_engaged is False

    # Rule 4: Critical command missing user confirmation.
    # INVARIANT FIX: fresh speed telemetry MUST be supplied first — the gateway now
    # fails closed at boot (no telemetry == stale), so Stage 4 would (correctly)
    # reject with SPEED_DATA_STALE before Stage 5 dual-confirmation is reached.
    gateway.update_vehicle_speed(0.0)
    with pytest.raises(SafetyError, match="Operator dual-confirmation missing"):
        gateway.validate_and_transmit(frame_valid, is_critical_command=True, user_confirmed=False)

    # Rule 3: Critical command while moving (> 0 km/h) triggers EStop
    gateway.update_vehicle_speed(25.5)
    with pytest.raises(SafetyError, match="Critical command blocked while vehicle is moving"):
        gateway.validate_and_transmit(frame_valid, is_critical_command=True, user_confirmed=True)
    assert estop.is_engaged is True
    assert estop.last_event is not None
    assert estop.last_event.trigger == EStopTriggerSource.SPEED_INTERLOCK_BREACH

    # Reset again and stop vehicle
    nonce = estop.get_reset_nonce()
    estop.reset(estop.compute_reset_token(nonce))
    gateway.update_vehicle_speed(0.0)

    # Legitimate critical command at 0 km/h with confirmation succeeds
    assert gateway.validate_and_transmit(frame_valid, is_critical_command=True, user_confirmed=True) is True
    assert len(bus.sent_frames) == 1


# ============================================================================
# 2. HWID GENERATION & ADVERSARIAL ENVIRONMENT TESTS
# ============================================================================


def test_hwid_invalid_uuid_sentinels() -> None:
    """Verify all invalid UUID sentinels trigger robust fallback."""
    for sentinel in _INVALID_UUIDS:
        with patch("src.security.hwid.collector._wmi_query", return_value=sentinel):
            uuid_out = collect_motherboard_uuid()
            assert uuid_out.startswith("FALLBACK-")


def test_hwid_powershell_subcommand_adversarial_outputs() -> None:
    """Test collector when PowerShell returns unexpected or control characters."""
    with patch("src.security.hwid.collector._run_powershell", return_value="  \r\n\tDISK-SERIAL-123\x00\t  "):
        assert collect_disk_serial() == "DISK-SERIAL-123\x00"

    with patch("src.security.hwid.collector._run_powershell", return_value=""):
        assert collect_disk_serial() == "UNKNOWN_DISK"
        assert collect_cpu_processor_id() == "UNKNOWN_CPU"
        assert collect_bios_serial() == "UNKNOWN_BIOS"


def test_hwid_fingerprint_uniqueness_across_varied_hardware() -> None:
    """Generate 100 unique hardware profiles and verify zero hash collisions."""
    hashes: set[str] = set()
    for i in range(100):
        with (
            patch("src.security.hwid.collector.collect_motherboard_uuid", return_value=f"UUID-{i}"),
            patch("src.security.hwid.collector.collect_cpu_processor_id", return_value=f"CPU-{i % 10}"),
            patch("src.security.hwid.collector.collect_disk_serial", return_value=f"DISK-{i * 7}"),
            patch("src.security.hwid.collector.collect_bios_serial", return_value=f"BIOS-{i * 13}"),
        ):
            fp = generate_hardware_fingerprint()
            assert len(fp) == 64
            hashes.add(fp)

    assert len(hashes) == 100


# ============================================================================
# 3. ANTI-TAMPER & ED25519 LICENSE VALIDATOR ADVERSARIAL TESTS
# ============================================================================


def test_license_clock_rollback_attack_vectors(tmp_path: Path) -> None:
    """Verify anti-rollback halts validation across multiple jump magnitudes."""
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()
    hwm_file = tmp_path / "hwm.dat"
    # Save initial HWM at T=1,000,000 with HMAC
    data = b"1000000"
    mac = hmac.new(LicenseValidator._HWM_HMAC_KEY, data, hashlib.sha256).hexdigest()
    hwm_file.write_text(f"1000000.{mac}", encoding="utf-8")

    validator = LicenseValidator(
        public_key=pub,
        hardware_fingerprint="HWID_TEST_NODE_1",
        high_water_mark_path=hwm_file,
        last_known_clock_ts=1000000,
        last_online_sync_ts=1000000,
        boot_realtime=1000000,
        boot_monotonic=0.0,
    )

    token = LicenseValidator.generate_signed_token(
        priv,
        {
            "user_id": "test_user",
            "tier": "ENTERPRISE",
            "hardware_fingerprint": "HWID_TEST_NODE_1",
            "issued_at": 900000,
            "expires_at": 2000000,
            "features": ["CAN_PRO", "UDS_EXPERT"],
        },
    )

    # 1. Rollback to 999,999 (1 sec backward)
    with pytest.raises(LicenseError, match="System clock manipulation detected"):
        validator.verify_token(token, current_ts=999999)

    # 2. Rollback to 500,000 (huge backward jump)
    with pytest.raises(LicenseError, match="System clock manipulation detected"):
        validator.verify_token(token, current_ts=500000)

    # 3. Forward time at 1,000,100 should succeed and advance HWM
    with patch("time.monotonic", return_value=100.0):
        payload = validator.verify_token(token, current_ts=1000100)
        assert payload.user_id == "test_user"
        assert hwm_file.read_text(encoding="utf-8").strip().startswith("1000100.")


def test_license_signature_mutilation_attack(tmp_path: Path) -> None:
    """Mutilate Ed25519 signature bytes and ensure rejection."""
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()

    validator = LicenseValidator(
        public_key=pub,
        hardware_fingerprint="HWID_TEST_NODE_1",
        last_known_clock_ts=1000000,
        last_online_sync_ts=1000000,
        boot_realtime=1000000,
        boot_monotonic=0.0,
    )

    token = LicenseValidator.generate_signed_token(
        priv,
        {
            "user_id": "test_user",
            "tier": "PRO",
            "hardware_fingerprint": "HWID_TEST_NODE_1",
            "issued_at": 900000,
            "expires_at": 2000000,
        },
    )

    parts = token.split(".")
    sig_raw = base64.urlsafe_b64decode(parts[1])

    # Flip individual bits across signature
    for byte_idx in (0, 15, 31, 63):
        mutilated_sig = bytearray(sig_raw)
        mutilated_sig[byte_idx] ^= 0xFF
        bad_token = f"{parts[0]}.{base64.urlsafe_b64encode(mutilated_sig).decode('ascii')}"

        with patch("time.monotonic", return_value=10.0):
            with pytest.raises(LicenseError, match="signature is invalid"):
                validator.verify_token(bad_token, current_ts=1000010)


def test_license_wildcard_hwid_behavior() -> None:
    """Verify wildcard '*' HWID allows multi-machine activation."""
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()

    validator_node_a = LicenseValidator(
        public_key=pub,
        hardware_fingerprint="MACHINE_AAA",
        last_known_clock_ts=1000,
        last_online_sync_ts=1000,
        boot_realtime=1000,
        boot_monotonic=0.0,
    )
    validator_node_b = LicenseValidator(
        public_key=pub,
        hardware_fingerprint="MACHINE_BBB",
        last_known_clock_ts=1000,
        last_online_sync_ts=1000,
        boot_realtime=1000,
        boot_monotonic=0.0,
    )

    wildcard_token = LicenseValidator.generate_signed_token(
        priv,
        {
            "user_id": "floating_user",
            "tier": "ENTERPRISE",
            "hardware_fingerprint": "*",
            "issued_at": 500,
            "expires_at": 5000,
        },
    )

    with patch("time.monotonic", return_value=10.0):
        res_a = validator_node_a.verify_token(wildcard_token, current_ts=1010)
        res_b = validator_node_b.verify_token(wildcard_token, current_ts=1010)
        assert res_a.user_id == "floating_user"
        assert res_b.user_id == "floating_user"


# ============================================================================
# 4. UDS ASYNC CLIENT & ISO-TP ADVERSARIAL TESTS
# ============================================================================


def test_uds_client_negative_response_code_handling() -> None:
    """Verify handling of NRC frames (0x7F <SID> <NRC>)."""
    bus = MockTestingBus()
    client = UdsClient(bus=bus, tx_id=0x7E0, rx_id=0x7E8)

    # Simulate ECU responding with NRC 0x11 (ServiceNotSupported) to DiagnosticSessionControl (0x10)
    # ISO-TP Single Frame: [Length=3, 0x7F, 0x10, 0x11, 0x00, 0x00, 0x00, 0x00]
    nrc_frame = CanFrame.create(
        channel_id="uds_ch0",
        arbitration_id=0x7E8,
        data=bytes([0x03, 0x7F, 0x10, UdsNrc.SERVICE_NOT_SUPPORTED.value, 0, 0, 0, 0]),
    )
    bus.push_rx_frame(nrc_frame)

    resp = client.change_session(DiagnosticSessionType.EXTENDED_DIAGNOSTIC_SESSION)
    assert resp.is_positive is False
    assert resp.service_id == 0x10
    assert resp.nrc == UdsNrc.SERVICE_NOT_SUPPORTED
    client.close()


def test_isotp_segmented_multiframe_roundtrip_stress() -> None:
    """Stress test ISO-TP segmentation of large payloads (up to 4095 bytes)."""
    transport = IsoTpTransport(tx_id=0x7E0, rx_id=0x7E8)
    large_payload = bytes([i % 256 for i in range(1024)])

    frames = transport.segment_message(large_payload)
    # First frame (0x10) + consecutive frames (0x20..0x2F)
    assert len(frames) == 1 + (1024 - 6 + 6) // 7  # 147 frames total

    # Reassemble using another transport instance simulating ECU
    receiver = IsoTpTransport(tx_id=0x7E8, rx_id=0x7E0)
    reassembled: bytes | None = None

    for idx, f in enumerate(frames):
        completed, fc = receiver.handle_rx_frame(f)
        if idx == 0:
            assert fc is not None  # Must emit Flow Control frame
        if completed is not None:
            reassembled = completed
            break

    assert reassembled == large_payload


# ============================================================================
# 5. DBC J1939 LOOKUP & LRU CACHE ADVERSARIAL TESTS
# ============================================================================


def test_dbc_j1939_and_standard_decoding_robustness() -> None:
    """Verify both standard 11-bit and extended 29-bit J1939 decoding."""
    dbc_content = """VERSION ""
NS_ :
BS_:
BU_: Engine Tester
BO_ 2364539904 EEC1: 8 Engine
 SG_ EngineSpeed : 24|16@1+ (0.125,0) [0|8031.875] "rpm" Vector__XXX
BO_ 256 StandardMsg: 8 Engine
 SG_ CoolantTemp : 0|8@1+ (1,-40) [-40|215] "degC" Vector__XXX
"""
    decoder = DbcSignalDecoder.from_dbc_string(dbc_content, max_cache_size=64)

    # Standard frame
    frame_std = CanFrame.create(
        channel_id="ch0",
        arbitration_id=256,
        data=b"\x78\x00\x00\x00\x00\x00\x00\x00",
        is_extended=False,
    )
    decoded_std = decoder.decode_frame(frame_std)
    assert decoded_std is not None
    assert decoded_std.message_name == "StandardMsg"
    assert decoded_std.signals["CoolantTemp"].value == 80

    # J1939 frame (PGN 0xF004 = 61444, SA 0x00 -> 0x0CF00400)
    frame_j1939 = CanFrame.create(
        channel_id="ch0",
        arbitration_id=0x0CF00400,
        data=b"\xff\xff\xff\x00\x32\xff\xff\xff",
        is_extended=True,
    )
    decoded_j1939 = decoder.decode_frame(frame_j1939)
    assert decoded_j1939 is not None
    assert decoded_j1939.message_name == "EEC1"
    assert decoded_j1939.signals["EngineSpeed"].value == 1600.0


def test_dbc_cache_churn_and_eviction_under_10000_unique_ids() -> None:
    """Flooding decoder with 10,000 distinct CAN IDs never exceeds max_cache_size."""
    dbc_content = """VERSION ""
NS_ :
BS_:
BU_: ECU
BO_ 100 MSG_100: 4 ECU
 SG_ Sig1 : 0|8@1+ (1,0) [0|255] "" Vector__XXX
"""
    cache_limit = 128
    decoder = DbcSignalDecoder.from_dbc_string(dbc_content, max_cache_size=cache_limit)

    for i in range(10000):
        frame = CanFrame.create(
            channel_id="ch0",
            arbitration_id=(i & 0x7FF),
            is_extended=False,
            data=b"\x01\x02\x03\x04",
        )
        decoder.decode_frame(frame)
        assert len(decoder._message_cache) <= cache_limit

    assert len(decoder._message_cache) <= cache_limit


# ============================================================================
# 6. AI DIAGNOSTIC COPILOT & ROBUST JSON/MARKDOWN PARSER ADVERSARIAL TESTS
# ============================================================================


def test_ai_copilot_json_parser_torture_patterns() -> None:
    """Stress test JSON extraction against extreme markdown, backticks, and conversational wrapping."""
    copilot = AiDiagnosticCopilot()

    valid_dict = {
        "summary": "Turbo boost failure",
        "severity": "CRITICAL_STOP",
        "root_cause_probability": "%96",
        "likely_causes": ["Hose leak"],
        "troubleshooting_steps": [
            {"step_number": 1, "action": "Check hose", "target_component": "Pipe", "difficulty": "Kolay"}
        ],
        "affected_subsystems": ["Turbo"],
        "telemetry_correlations": ["Boost 90 kPa at 2500 RPM"],
    }
    json_str = json.dumps(valid_dict)

    test_payloads = [
        f"```json\n{json_str}\n```",
        f"```JSON\n{json_str}\n```",
        f"```\n{json_str}\n```",
        f"Here is your report:\n\n```json\n{json_str}\n```\n\nHope this helps!",
        f"<response>\n```json\n{json_str}\n```\n</response>",
        f"Prefix discussion before markdown\n```json\n{json_str}\n```\nFollow-up recommendation comments.",
        f"  \t\r\n{json_str}\r\n\t ",
    ]

    for payload in test_payloads:
        parsed = copilot._clean_and_parse_json(payload)
        assert isinstance(parsed, dict)
        assert parsed["summary"] == "Turbo boost failure"
        assert parsed["severity"] == "CRITICAL_STOP"


def test_ai_copilot_local_expert_simultaneous_multi_fault() -> None:
    """Verify local expert engine when 5 simultaneous severe faults are present."""
    copilot = AiDiagnosticCopilot()
    active_dtcs = [
        {"spn": 100, "fmi": 1, "description": "Low Oil Pressure"},
        {"spn": 110, "fmi": 0, "description": "High Coolant Temp"},
        {"spn": 651, "fmi": 5, "description": "Injector Cylinder 1 Open Circuit"},
        {"spn": 102, "fmi": 18, "description": "Low Boost Pressure"},
        {"spn": 3251, "fmi": 0, "description": "DPF High Soot Load"},
    ]
    telemetry = {
        "EngineSpeed": 2200.0,
        "BoostPressure": 95.0,
        "CoolantTemp": 112.0,
    }

    report = copilot.analyze_session(active_dtcs, telemetry, active_ecus=["EMS", "ACM"])

    assert report.severity == FaultSeverity.CRITICAL_STOP
    assert len(report.affected_subsystems) == 5
    assert len(report.likely_causes) == 5
    assert len(report.troubleshooting_steps) >= 5
    assert report.raw_dtc_count == 5
