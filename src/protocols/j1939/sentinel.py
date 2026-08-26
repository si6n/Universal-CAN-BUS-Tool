"""SAE J1939-71 MSB-Based Sentinel Range Bounds and Error Validator.

Complies with SAE J1939-71 and MASTER_PLAN.md Section 4.3.
"""

from __future__ import annotations

from enum import Enum


class SignalQuality(Enum):
    """Quality and validity classification of a decoded J1939 signal."""

    VALID = "VALID"
    PARAMETER_SPECIFIC = "PARAMETER_SPECIFIC"
    RESERVED = "RESERVED"
    ERROR = "ERROR"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class J1939SentinelFilter:
    """Validator for MSB-encoded sentinel ranges across 1-byte, 2-byte, 4-byte and discrete signals."""

    @classmethod
    def check_uint8(cls, raw_val: int) -> SignalQuality:
        """Evaluate 8-bit unsigned raw integer."""
        if not (0 <= raw_val <= 0xFF):
            return SignalQuality.ERROR
        if raw_val <= 0xFA:
            return SignalQuality.VALID
        if raw_val == 0xFB:
            return SignalQuality.PARAMETER_SPECIFIC
        if 0xFC <= raw_val <= 0xFD:
            return SignalQuality.RESERVED
        if raw_val == 0xFE:
            return SignalQuality.ERROR
        return SignalQuality.NOT_AVAILABLE

    @classmethod
    def check_uint16(cls, raw_val: int) -> SignalQuality:
        """Evaluate 16-bit unsigned raw integer."""
        if not (0 <= raw_val <= 0xFFFF):
            return SignalQuality.ERROR
        msb = (raw_val >> 8) & 0xFF
        if msb <= 0xFA:
            return SignalQuality.VALID
        if msb == 0xFB:
            return SignalQuality.PARAMETER_SPECIFIC
        if 0xFC <= msb <= 0xFD:
            return SignalQuality.RESERVED
        if msb == 0xFE:
            return SignalQuality.ERROR
        return SignalQuality.NOT_AVAILABLE

    @classmethod
    def check_uint32(cls, raw_val: int) -> SignalQuality:
        """Evaluate 32-bit unsigned raw integer."""
        if not (0 <= raw_val <= 0xFFFFFFFF):
            return SignalQuality.ERROR
        msb = (raw_val >> 24) & 0xFF
        if msb <= 0xFA:
            return SignalQuality.VALID
        if msb == 0xFB:
            return SignalQuality.PARAMETER_SPECIFIC
        if 0xFC <= msb <= 0xFD:
            return SignalQuality.RESERVED
        if msb == 0xFE:
            return SignalQuality.ERROR
        return SignalQuality.NOT_AVAILABLE

    @classmethod
    def check_discrete_2bit(cls, raw_val: int) -> SignalQuality:
        """Evaluate 2-bit discrete state."""
        val = raw_val & 0x03
        if val == 0b00 or val == 0b01:
            return SignalQuality.VALID
        if val == 0b10:
            return SignalQuality.ERROR
        return SignalQuality.NOT_AVAILABLE
