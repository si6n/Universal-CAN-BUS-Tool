"""Unit tests for TX Watchdog and Heartbeat Lease Supervisor."""

from __future__ import annotations

import time

from src.safety.estop import EmergencyStopSystem, EStopTriggerSource
from src.safety.state_machine import SafetyState, SafetySupervisor
from src.safety.watchdog import TxWatchdogSupervisor


def test_tx_watchdog_lease_and_heartbeat() -> None:
    supervisor = SafetySupervisor(initial_state=SafetyState.SAFE)
    supervisor.transition_to(SafetyState.PASSIVE)
    supervisor.arm_tx()

    watchdog = TxWatchdogSupervisor(supervisor=supervisor, timeout_ms=200.0)
    assert watchdog.is_lease_valid is True
    assert watchdog.remaining_lease_sec > 0.1

    # Keep lease alive with heartbeat
    time.sleep(0.05)
    watchdog.heartbeat()
    assert watchdog.is_lease_valid is True


def test_tx_watchdog_timeout_revokes_tx_and_triggers_estop() -> None:
    supervisor = SafetySupervisor(initial_state=SafetyState.SAFE)
    supervisor.transition_to(SafetyState.PASSIVE)
    supervisor.arm_tx()
    assert supervisor.is_tx_permitted is True

    estop = EmergencyStopSystem()
    assert estop.is_engaged is False

    # Short timeout for fast unit testing (100ms)
    watchdog = TxWatchdogSupervisor(supervisor=supervisor, estop=estop, timeout_ms=100.0)
    watchdog.start()

    try:
        # Wait 200ms without heartbeat
        time.sleep(0.20)

        # Verify that supervisor entered FAULT state
        assert supervisor.current_state == SafetyState.FAULT
        assert supervisor.is_tx_permitted is False
        assert "WATCHDOG_TIMEOUT" in supervisor.fault_reason

        # Verify that E-Stop engaged
        assert estop.is_engaged is True
        assert estop.last_event is not None
        assert estop.last_event.trigger == EStopTriggerSource.KEEPALIVE_TIMEOUT
    finally:
        watchdog.stop()
