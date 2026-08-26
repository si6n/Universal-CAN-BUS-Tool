"""Unit tests for Core PlatformError hierarchy."""

from src.core.errors import (
    HardwareError,
    LicenseError,
    PlatformError,
    ProtocolError,
    SafetyError,
    TransportError,
)


def test_platform_error_base() -> None:
    err = PlatformError("General platform failure", code="CUSTOM_CODE", details={"foo": "bar"})
    assert str(err) == "General platform failure"
    assert err.code == "CUSTOM_CODE"
    assert err.details == {"foo": "bar"}
    assert err.timestamp_ns > 0

    d = err.to_dict()
    assert d["code"] == "CUSTOM_CODE"
    assert d["message"] == "General platform failure"
    assert d["details"] == {"foo": "bar"}
    assert "timestamp_ns" in d


def test_platform_error_cause() -> None:
    original = ValueError("Root value invalid")
    err = HardwareError("Adapter initialization failed", cause=original)
    assert err.code == "HARDWARE_ERROR"
    assert err.cause == original
    d = err.to_dict()
    assert "Root value invalid" in d["cause"]


def test_all_error_subclasses() -> None:
    hw_err = HardwareError("PEAK-USB not responding")
    assert isinstance(hw_err, PlatformError)
    assert hw_err.code == "HARDWARE_ERROR"

    tp_err = TransportError("J1939 BAM timeout")
    assert isinstance(tp_err, PlatformError)
    assert tp_err.code == "TRANSPORT_ERROR"

    proto_err = ProtocolError("Malformed SPN encoding")
    assert isinstance(proto_err, PlatformError)
    assert proto_err.code == "PROTOCOL_ERROR"

    safe_err = SafetyError("Vehicle speed > 0 during compression test")
    assert isinstance(safe_err, PlatformError)
    assert safe_err.code == "SAFETY_ERROR"

    lic_err = LicenseError("Ed25519 signature mismatch")
    assert isinstance(lic_err, PlatformError)
    assert lic_err.code == "LICENSE_ERROR"
