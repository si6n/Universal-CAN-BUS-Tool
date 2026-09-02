"""Safety Layer Exception Taxonomy.

Defines specialized functional safety exceptions inheriting from SafetyError.
Matches MASTER_PLAN.md Section 7 and ISO 26262 ASIL-B/D Fault Containment.
"""

from __future__ import annotations

from typing import Any

from src.core.errors import SafetyError


class WhitelistFailClosedError(SafetyError):
    """Raised when frame transmission is attempted against an empty or unconfigured whitelist."""

    def __init__(
        self,
        message: str = "Transmission blocked: Dynamic whitelist is empty or unconfigured (Fail-Closed)",
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, code="WHITELIST_FAIL_CLOSED", details=details, cause=cause)


class WhitelistViolationError(SafetyError):
    """Raised when frame arbitration ID is not found in the authorized whitelist."""

    def __init__(
        self,
        message: str = "Transmission blocked: Frame ID not in whitelist",
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, code="WHITELIST_VIOLATION", details=details, cause=cause)


class SpeedInterlockError(SafetyError):
    """Raised when a critical transmission is attempted while vehicle is in motion."""

    def __init__(
        self,
        message: str = "Safety Interlock: Critical command blocked while vehicle is moving",
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, code="SPEED_INTERLOCK_ACTIVE", details=details, cause=cause)


class SpeedDataStaleError(SafetyError):
    """Raised when a critical transmission is attempted with stale or missing speed telemetry."""

    def __init__(
        self,
        message: str = "Safety Interlock: Critical command blocked due to stale vehicle speed telemetry",
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, code="SPEED_DATA_STALE", details=details, cause=cause)


class DualConfirmationRequiredError(SafetyError):
    """Raised when a critical diagnostic command lacks explicit user confirmation."""

    def __init__(
        self,
        message: str = "Critical command rejected: Operator dual-confirmation missing",
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, code="CONFIRMATION_REQUIRED", details=details, cause=cause)


class FrameSanityError(SafetyError):
    """Raised when frame attributes violate CAN or CAN-FD sanity constraints."""

    def __init__(
        self,
        message: str = "Transmission rejected: Invalid frame sanity check",
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, code="INVALID_FRAME_SANITY", details=details, cause=cause)


class RateLimitExceededError(SafetyError):
    """Raised when transmission rate exceeds the permitted budget (100 msg/s)."""

    def __init__(
        self,
        message: str = "Transmission rate limit exceeded (100 msg/s)",
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, code="RATE_LIMIT_EXCEEDED", details=details, cause=cause)
