"""Unit tests for AntiTamperGuard."""

from src.security.anti_tamper.guard import AntiTamperGuard


def test_anti_tamper_checks() -> None:
    # Under test runner, debugger query should execute safely returning bool
    is_dbg = AntiTamperGuard.is_debugger_present()
    assert isinstance(is_dbg, bool)

    remote_dbg = AntiTamperGuard.check_remote_debugger()
    assert isinstance(remote_dbg, bool)

    # Timing anomaly should not be triggered under standard fast execution
    anomaly = AntiTamperGuard.detect_timing_anomaly(threshold_ms=500.0)
    assert anomaly is False
