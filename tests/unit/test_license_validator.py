"""Unit tests for Ed25519 LicenseValidator, 7-day offline grace period, and Anti-Clock High-Water Mark."""

from __future__ import annotations

import base64
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.core.errors import LicenseError
from src.security.hwid.collector import generate_hardware_fingerprint
from src.security.license.validator import LicenseValidator


def test_license_valid_verification() -> None:

    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()

    now = int(time.time())
    payload_dict = {
        "user_id": "usr_9988",
        "tier": "ENTERPRISE",
        "hardware_fingerprint": "HW_UUID_12345678",
        "issued_at": now - 3600,
        "expires_at": now + 86400 * 365,
        "features": ["CAN_SNIFFER", "J1939_DIAGNOSTICS", "UDS_ROUTINES"],
    }

    token_str = LicenseValidator.generate_signed_token(priv_key, payload_dict)

    validator = LicenseValidator(
        public_key=pub_key,
        hardware_fingerprint="HW_UUID_12345678",
        last_online_sync_ts=now,
    )

    verified = validator.verify_token(token_str, current_ts=now)
    assert verified.user_id == "usr_9988"
    assert verified.tier == "ENTERPRISE"
    assert "J1939_DIAGNOSTICS" in verified.features


def test_license_tampered_signature_rejected() -> None:
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()
    now = int(time.time())

    payload_dict = {
        "user_id": "usr_hacker",
        "tier": "FREE",
        "hardware_fingerprint": "HW_ANY",
        "issued_at": now,
        "expires_at": now + 3600,
    }
    token_str = LicenseValidator.generate_signed_token(priv_key, payload_dict)

    # Tamper token signature
    parts = token_str.split(".")
    tampered_sig = parts[1][:-4] + "AAAA"
    tampered_token = f"{parts[0]}.{tampered_sig}"

    validator = LicenseValidator(public_key=pub_key, hardware_fingerprint="HW_ANY")
    with pytest.raises(LicenseError, match="signature is invalid") as exc_info:
        validator.verify_token(tampered_token, current_ts=now)
    assert exc_info.value.code == "INVALID_SIGNATURE"


def test_license_hardware_mismatch() -> None:
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()
    now = int(time.time())

    payload_dict = {
        "user_id": "usr_1",
        "tier": "PRO",
        "hardware_fingerprint": "PC_ALICE",
        "issued_at": now,
        "expires_at": now + 3600,
    }
    token_str = LicenseValidator.generate_signed_token(priv_key, payload_dict)

    validator = LicenseValidator(public_key=pub_key, hardware_fingerprint="PC_BOB")
    with pytest.raises(LicenseError, match="locked to a different machine") as exc_info:
        validator.verify_token(token_str, current_ts=now)
    assert exc_info.value.code == "HARDWARE_MISMATCH"


def test_license_clock_rollback_detection() -> None:
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()
    now = int(time.time())

    payload_dict = {
        "user_id": "usr_1",
        "tier": "PRO",
        "hardware_fingerprint": "HW_1",
        "issued_at": now,
        "expires_at": now + 86400,
    }
    token_str = LicenseValidator.generate_signed_token(priv_key, payload_dict)

    validator = LicenseValidator(
        public_key=pub_key,
        hardware_fingerprint="HW_1",
        last_known_clock_ts=now + 5000,  # Future clock recorded
    )

    # Calling with earlier timestamp trips rollback
    with pytest.raises(LicenseError, match="clock manipulation detected") as exc_info:
        validator.verify_token(token_str, current_ts=now)
    assert exc_info.value.code == "CLOCK_ROLLBACK_DETECTED"


def test_license_offline_grace_period_expired() -> None:
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()
    now = int(time.time())

    payload_dict = {
        "user_id": "usr_1",
        "tier": "PRO",
        "hardware_fingerprint": "HW_1",
        "issued_at": now - 86400 * 30,
        "expires_at": now + 86400 * 365,
    }
    token_str = LicenseValidator.generate_signed_token(priv_key, payload_dict)

    # Last online sync was 8 days ago (> 7 days max grace)
    validator = LicenseValidator(
        public_key=pub_key,
        hardware_fingerprint="HW_1",
        last_online_sync_ts=now - (8 * 86400),
    )

    with pytest.raises(LicenseError, match="7-day offline grace period has expired") as exc_info:
        validator.verify_token(token_str, current_ts=now)
    assert exc_info.value.code == "OFFLINE_GRACE_EXPIRED"


def test_license_default_hwid_wiring() -> None:
    """Verify that LicenseValidator defaults to genuine generate_hardware_fingerprint()."""
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()

    expected_hwid = generate_hardware_fingerprint()

    # Instantiate validator without passing hardware_fingerprint
    validator = LicenseValidator(public_key=pub_key)
    assert validator.hardware_fingerprint == expected_hwid

    now = int(time.time())
    payload_dict = {
        "user_id": "usr_autohwid",
        "tier": "PRO",
        "hardware_fingerprint": expected_hwid,
        "issued_at": now - 60,
        "expires_at": now + 3600,
    }
    token_str = LicenseValidator.generate_signed_token(priv_key, payload_dict)

    verified = validator.verify_token(token_str, current_ts=now)
    assert verified.hardware_fingerprint == expected_hwid


def test_license_wildcard_hwid() -> None:
    """Verify that tokens with wildcard '*' hardware fingerprint match any machine."""
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()
    now = int(time.time())

    payload_dict = {
        "user_id": "enterprise_fleet",
        "tier": "ENTERPRISE",
        "hardware_fingerprint": "*",
        "issued_at": now,
        "expires_at": now + 86400,
    }
    token_str = LicenseValidator.generate_signed_token(priv_key, payload_dict)

    validator = LicenseValidator(public_key=pub_key, hardware_fingerprint="ANY_RANDOM_HWID_STRING")
    verified = validator.verify_token(token_str, current_ts=now)
    assert verified.user_id == "enterprise_fleet"
    assert verified.hardware_fingerprint == "*"


def test_license_expired() -> None:
    """Verify that expired license token raises LICENSE_EXPIRED."""
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()
    now = int(time.time())

    payload_dict = {
        "user_id": "usr_expired",
        "tier": "FREE",
        "hardware_fingerprint": "HW_EXP",
        "issued_at": now - 7200,
        "expires_at": now - 3600,  # Expired 1 hour ago
    }
    token_str = LicenseValidator.generate_signed_token(priv_key, payload_dict)

    validator = LicenseValidator(public_key=pub_key, hardware_fingerprint="HW_EXP")
    with pytest.raises(LicenseError, match="License expired at") as exc_info:
        validator.verify_token(token_str, current_ts=now)
    assert exc_info.value.code == "LICENSE_EXPIRED"


@pytest.mark.parametrize(
    "bad_token",
    [
        "",
        "not_a_valid_token",
        "part1.part2.part3",
        "singleword",
    ],
)
def test_license_invalid_token_format(bad_token: str) -> None:
    """Verify tokens not in <payload>.<signature> format raise INVALID_TOKEN_FORMAT."""
    priv_key = ed25519.Ed25519PrivateKey.generate()
    validator = LicenseValidator(public_key=priv_key.public_key(), hardware_fingerprint="HW_1")

    with pytest.raises(LicenseError, match="Invalid license token format") as exc_info:
        validator.verify_token(bad_token)
    assert exc_info.value.code == "INVALID_TOKEN_FORMAT"


def test_license_base64_decode_error() -> None:
    """Verify corrupted non-base64 tokens raise TOKEN_DECODE_ERROR."""
    priv_key = ed25519.Ed25519PrivateKey.generate()
    validator = LicenseValidator(public_key=priv_key.public_key(), hardware_fingerprint="HW_1")

    with pytest.raises(LicenseError, match="Failed to decode license base64") as exc_info:
        validator.verify_token("@@@bad_base64@@@.###bad_sig###")
    assert exc_info.value.code == "TOKEN_DECODE_ERROR"


def test_license_malformed_json_payload() -> None:
    """Verify validly signed but non-JSON or missing fields raise MALFORMED_PAYLOAD."""
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()
    now = int(time.time())

    # Raw bytes that are valid base64 but not valid license JSON
    bad_json_bytes = b'{"incomplete": true}'
    sig_bytes = priv_key.sign(bad_json_bytes)

    b64_payload = base64.urlsafe_b64encode(bad_json_bytes).decode("ascii")
    b64_sig = base64.urlsafe_b64encode(sig_bytes).decode("ascii")
    token_str = f"{b64_payload}.{b64_sig}"

    validator = LicenseValidator(public_key=pub_key, hardware_fingerprint="HW_1")
    with pytest.raises(LicenseError, match="Malformed license JSON payload") as exc_info:
        validator.verify_token(token_str, current_ts=now)
    assert exc_info.value.code == "MALFORMED_PAYLOAD"


def test_license_monotonic_mismatch_detected() -> None:
    """Verify monotonic clock cross-check catches backward real-time drift."""
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()

    # Injected boot reference: 1000s realtime, 0s monotonic
    boot_realtime = 1000
    boot_monotonic = 0.0

    validator = LicenseValidator(
        public_key=pub_key,
        hardware_fingerprint="HW_1",
        last_online_sync_ts=boot_realtime,
        boot_realtime=boot_realtime,
        boot_monotonic=boot_monotonic,
        last_known_clock_ts=boot_realtime,
    )

    payload_dict = {
        "user_id": "usr_mono",
        "tier": "PRO",
        "hardware_fingerprint": "HW_1",
        "issued_at": 500,
        "expires_at": 50000,
    }
    token_str = LicenseValidator.generate_signed_token(priv_key, payload_dict)

    # If monotonic is 500s (expected realtime is 1500s), but now is 1200s (< 1500 - 60)
    with patch("time.monotonic", return_value=500.0):
        with pytest.raises(LicenseError, match="monotonic counter") as exc_info:
            validator.verify_token(token_str, current_ts=1200)
        assert exc_info.value.code == "CLOCK_MONOTONIC_MISMATCH"


def test_persistent_high_water_mark_file_flow(tmp_path: Path) -> None:
    """Verify High-Water Mark is persisted to disk and prevents rollback on new validator instances."""
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()
    hwm_file = tmp_path / "subdir" / "hwm.dat"

    now = 2000000000
    payload_dict = {
        "user_id": "usr_hwm",
        "tier": "ENTERPRISE",
        "hardware_fingerprint": "HW_HWM",
        "issued_at": now - 1000,
        "expires_at": now + 100000,
    }
    token_str = LicenseValidator.generate_signed_token(priv_key, payload_dict)

    # 1. Run validator and verify token at now
    validator1 = LicenseValidator(
        public_key=pub_key,
        hardware_fingerprint="HW_HWM",
        high_water_mark_path=hwm_file,
        last_online_sync_ts=now,
        boot_realtime=now,
        boot_monotonic=0.0,
    )
    with patch("time.monotonic", return_value=0.0):
        validator1.verify_token(token_str, current_ts=now)

    assert hwm_file.exists()
    assert hwm_file.read_text(encoding="utf-8").strip().startswith(f"{now}.")

    # 2. Instantiate a second validator instance reading the same file
    validator2 = LicenseValidator(
        public_key=pub_key,
        hardware_fingerprint="HW_HWM",
        high_water_mark_path=hwm_file,
        last_online_sync_ts=now,
        boot_realtime=now,
        boot_monotonic=0.0,
    )
    assert validator2.last_known_clock_ts == now

    # 3. An attacker sets system clock backward to now - 5000 -> must fail
    with patch("time.monotonic", return_value=0.0):
        with pytest.raises(LicenseError, match="clock manipulation detected") as exc_info:
            validator2.verify_token(token_str, current_ts=now - 5000)
        assert exc_info.value.code == "CLOCK_ROLLBACK_DETECTED"


def test_persistent_high_water_mark_corrupt_file(tmp_path: Path) -> None:
    """Verify corrupt / non-integer HWM file gracefully falls back without crashing."""
    hwm_file = tmp_path / "corrupt_hwm.dat"
    hwm_file.write_text("CORRUPTED_NON_INTEGER_VALUE", encoding="utf-8")

    priv_key = ed25519.Ed25519PrivateKey.generate()
    validator = LicenseValidator(
        public_key=priv_key.public_key(),
        hardware_fingerprint="HW_1",
        high_water_mark_path=hwm_file,
    )
    # last_known_clock_ts should default to current time
    assert validator.last_known_clock_ts is not None


def test_persistent_high_water_mark_save_error(tmp_path: Path) -> None:
    """Verify that disk write error on saving HWM logs warning and does not crash validation."""
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()
    now = int(time.time())

    payload_dict = {
        "user_id": "usr_save_err",
        "tier": "PRO",
        "hardware_fingerprint": "HW_SAVE_ERR",
        "issued_at": now,
        "expires_at": now + 3600,
    }
    token_str = LicenseValidator.generate_signed_token(priv_key, payload_dict)

    hwm_file = tmp_path / "readonly_hwm.dat"
    validator = LicenseValidator(
        public_key=pub_key,
        hardware_fingerprint="HW_SAVE_ERR",
        high_water_mark_path=hwm_file,
    )

    with patch.object(Path, "write_text", side_effect=OSError("Disk write permission denied")):
        # Verification should succeed despite save error
        verified = validator.verify_token(token_str, current_ts=now)
        assert verified.user_id == "usr_save_err"
