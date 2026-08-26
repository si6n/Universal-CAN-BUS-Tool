"""Ed25519 Asymmetric License Ticketing & 7-Day Offline Grace Period Validator.

Complies with MASTER_PLAN.md Section 3.2 (ADR-003).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.core.errors import LicenseError
from src.core.logging import get_logger
from src.security.hwid.collector import generate_hardware_fingerprint

logger = get_logger("security.license")


@dataclass(slots=True, frozen=True)
class LicensePayload:
    """Decoded and verified license parameters."""

    user_id: str
    tier: str  # "FREE" | "PRO" | "ENTERPRISE"
    hardware_fingerprint: str
    issued_at: int
    expires_at: int
    features: tuple[str, ...] = field(default_factory=tuple)


class LicenseValidator:
    """Validates Ed25519 signed license tokens and manages offline grace period."""

    MAX_OFFLINE_GRACE_SEC: ClassVar[int] = 7 * 24 * 3600  # 7 Days (604,800 s)
    _HWM_HMAC_KEY: ClassVar[bytes] = b"CAN_LICENSE_HWM_HMAC_SECRET_V1"

    def __init__(
        self,
        public_key: ed25519.Ed25519PublicKey,
        hardware_fingerprint: str | None = None,
        last_online_sync_ts: int | None = None,
        last_known_clock_ts: int | None = None,
        high_water_mark_path: Path | str | None = None,
        boot_realtime: int | None = None,
        boot_monotonic: float | None = None,
    ) -> None:
        self.public_key = public_key
        self.hardware_fingerprint = hardware_fingerprint if hardware_fingerprint is not None else generate_hardware_fingerprint()
        self.last_online_sync_ts = last_online_sync_ts or int(time.time())
        self.boot_realtime = boot_realtime
        self.boot_monotonic = boot_monotonic
        self.high_water_mark_path = Path(high_water_mark_path) if high_water_mark_path is not None else None
        self.last_known_clock_ts = last_known_clock_ts or int(time.time())

        # Load persisted High-Water Mark from disk if present
        if self.high_water_mark_path and self.high_water_mark_path.exists():
            try:
                content = self.high_water_mark_path.read_text(encoding="utf-8").strip()
                if "." in content:
                    ts_str, hmac_str = content.split(".", 1)
                    ts_val = int(ts_str)
                    expected_mac = hmac.new(self._HWM_HMAC_KEY, ts_str.encode("utf-8"), hashlib.sha256).hexdigest()
                    if hmac.compare_digest(hmac_str, expected_mac):
                        if ts_val > self.last_known_clock_ts:
                            self.last_known_clock_ts = ts_val
                else:
                    ts_val = int(content)
                    if ts_val > self.last_known_clock_ts:
                        self.last_known_clock_ts = ts_val
            except Exception:
                # Corrupted or unreadable HWM file falls back cleanly
                pass

    def verify_token(self, token_str: str, current_ts: int | None = None) -> LicensePayload:
        """Verify Ed25519 token signature, hardware fingerprint, and expiration."""
        now = current_ts if current_ts is not None else int(time.time())

        # Anti-Clock Rollback Check
        if now < self.last_known_clock_ts:
            logger.critical("System clock rollback detected!", extra={"now": now, "last": self.last_known_clock_ts})
            raise LicenseError(
                "System clock manipulation detected. License validation halted.",
                code="CLOCK_ROLLBACK_DETECTED",
            )

        # Monotonic counter drift / freeze cross-check
        if self.boot_realtime is not None and self.boot_monotonic is not None:
            curr_mono = time.monotonic()
            mono_elapsed = curr_mono - self.boot_monotonic
            real_elapsed = now - self.boot_realtime
            if mono_elapsed > (real_elapsed + 60.0):
                logger.critical("Monotonic counter mismatch detected!", extra={"mono_elapsed": mono_elapsed, "real_elapsed": real_elapsed})
                raise LicenseError(
                    "System clock manipulation detected (monotonic counter mismatch).",
                    code="CLOCK_MONOTONIC_MISMATCH",
                )

        self.last_known_clock_ts = now

        # Persist high water mark to disk
        if self.high_water_mark_path:
            try:
                self.high_water_mark_path.parent.mkdir(parents=True, exist_ok=True)
                data_bytes = str(now).encode("utf-8")
                mac = hmac.new(self._HWM_HMAC_KEY, data_bytes, hashlib.sha256).hexdigest()
                self.high_water_mark_path.write_text(f"{now}.{mac}", encoding="utf-8")
            except OSError as exc:
                logger.warning("Failed to persist high water mark to disk", extra={"error": str(exc)})

        # Parse token: <payload_b64>.<sig_b64>
        parts = token_str.strip().split(".")
        if len(parts) != 2:
            raise LicenseError("Invalid license token format", code="INVALID_TOKEN_FORMAT")

        payload_b64, sig_b64 = parts[0], parts[1]

        try:
            payload_bytes = base64.urlsafe_b64decode(payload_b64.encode("ascii"))
            sig_bytes = base64.urlsafe_b64decode(sig_b64.encode("ascii"))
        except Exception as exc:
            raise LicenseError(
                f"Failed to decode license base64: {exc}",
                code="TOKEN_DECODE_ERROR",
                cause=exc,
            ) from exc

        # Cryptographic Signature Verification
        try:
            self.public_key.verify(sig_bytes, payload_bytes)
        except InvalidSignature as exc:
            logger.error("License token Ed25519 signature verification failed!")
            raise LicenseError(
                "License token signature is invalid or has been tampered with.",
                code="INVALID_SIGNATURE",
                cause=exc,
            ) from exc

        # Parse JSON payload
        try:
            data = json.loads(payload_bytes.decode("utf-8"))
            if not isinstance(data, dict) or not {"user_id", "tier", "hardware_fingerprint", "issued_at", "expires_at"}.issubset(data.keys()):
                raise ValueError("Incomplete license payload schema")
            payload = LicensePayload(
                user_id=data["user_id"],
                tier=data["tier"],
                hardware_fingerprint=data["hardware_fingerprint"],
                issued_at=data["issued_at"],
                expires_at=data["expires_at"],
                features=tuple(data.get("features", [])),
            )
        except Exception as exc:
            raise LicenseError(
                f"Malformed license JSON payload: {exc}",
                code="MALFORMED_PAYLOAD",
                cause=exc,
            ) from exc

        # Hardware Fingerprint Check
        if payload.hardware_fingerprint != self.hardware_fingerprint and payload.hardware_fingerprint != "*":
            logger.warning("Hardware fingerprint mismatch", extra={"expected": self.hardware_fingerprint, "token": payload.hardware_fingerprint})
            raise LicenseError(
                "License is locked to a different machine hardware ID.",
                code="HARDWARE_MISMATCH",
            )

        # Expiration Check
        if now > payload.expires_at:
            raise LicenseError(
                f"License expired at {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(payload.expires_at))}.",
                code="LICENSE_EXPIRED",
            )

        # 7-Day Offline Grace Period Check
        offline_elapsed = now - self.last_online_sync_ts
        if offline_elapsed > self.MAX_OFFLINE_GRACE_SEC:
            logger.warning("Offline grace period expired", extra={"elapsed_days": offline_elapsed / 86400})
            raise LicenseError(
                "7-day offline grace period has expired. Please connect to the internet to re-validate.",
                code="OFFLINE_GRACE_EXPIRED",
            )

        logger.info("License token verified successfully", extra={"user": payload.user_id, "tier": payload.tier})
        return payload

    @classmethod
    def generate_signed_token(
        cls,
        private_key: ed25519.Ed25519PrivateKey,
        payload_dict: dict[str, object],
    ) -> str:
        """Helper to create signed license token for testing or backend licensing servers."""
        payload_json = json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")
        sig_bytes = private_key.sign(payload_json)

        b64_payload = base64.urlsafe_b64encode(payload_json).decode("ascii")
        b64_sig = base64.urlsafe_b64encode(sig_bytes).decode("ascii")

        return f"{b64_payload}.{b64_sig}"
