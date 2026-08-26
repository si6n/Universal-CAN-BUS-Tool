"""Unit tests for Formal Safety State Machine and State Transitions."""

from __future__ import annotations

import pytest

from src.core.errors import SafetyError
from src.safety.state_machine import SafetyState, SafetySupervisor


def test_safety_state_machine_initial_state_and_safe_transitions() -> None:
    supervisor = SafetySupervisor(initial_state=SafetyState.STARTUP)
    assert supervisor.current_state == SafetyState.STARTUP
    assert supervisor.is_tx_permitted is False

    # STARTUP -> SAFE
    supervisor.transition_to(SafetyState.SAFE, "Hardware initialized")
    assert supervisor.current_state == SafetyState.SAFE
    assert supervisor.is_tx_permitted is False

    # SAFE -> PASSIVE
    supervisor.transition_to(SafetyState.PASSIVE, "Default Listen-Only mode")
    assert supervisor.current_state == SafetyState.PASSIVE
    assert supervisor.is_passive is True
    assert supervisor.is_tx_permitted is False

    # PASSIVE -> ARMED_TX
    supervisor.arm_tx("Operator explicit authorization")
    assert supervisor.current_state == SafetyState.ARMED_TX
    assert supervisor.is_tx_permitted is True

    # ARMED_TX -> ACTIVE
    supervisor.activate_tx("Active transmission stream")
    assert supervisor.current_state == SafetyState.ACTIVE
    assert supervisor.is_tx_permitted is True

    # ACTIVE -> FAULT
    supervisor.trigger_fault("Watchdog timeout event")
    assert supervisor.current_state == SafetyState.FAULT
    assert supervisor.is_fault is True
    assert supervisor.is_tx_permitted is False
    assert "Watchdog timeout event" in supervisor.fault_reason

    # FAULT -> PASSIVE (Allowed recovery)
    supervisor.enter_passive_mode("Operator resolved fault in listen-only mode")
    assert supervisor.current_state == SafetyState.PASSIVE
    assert supervisor.is_tx_permitted is False


def test_safety_state_machine_illegal_transition_triggers_emergency_fault() -> None:
    supervisor = SafetySupervisor(initial_state=SafetyState.STARTUP)

    # Illegal transition: STARTUP directly to ACTIVE (Must go through SAFE -> PASSIVE -> ARMED_TX)
    with pytest.raises(SafetyError, match="Illegal Safety State transition"):
        supervisor.transition_to(SafetyState.ACTIVE, "Direct jump attempt")

    # Verify that illegal transition forced the state machine into FAULT
    assert supervisor.current_state == SafetyState.FAULT
    assert supervisor.is_tx_permitted is False
    assert "ILLEGAL_STATE_TRANSITION" in supervisor.fault_reason


def test_safety_state_machine_cannot_jump_from_fault_to_active() -> None:
    supervisor = SafetySupervisor(initial_state=SafetyState.FAULT)
    assert supervisor.current_state == SafetyState.FAULT

    # FAULT directly to ARMED_TX or ACTIVE is strictly illegal
    with pytest.raises(SafetyError, match="Illegal Safety State transition"):
        supervisor.transition_to(SafetyState.ACTIVE)

    assert supervisor.current_state == SafetyState.FAULT


def test_safety_state_machine_callbacks() -> None:
    events: list[tuple[SafetyState, SafetyState, str]] = []

    def _cb(old: SafetyState, new: SafetyState, reason: str) -> None:
        events.append((old, new, reason))

    supervisor = SafetySupervisor(initial_state=SafetyState.STARTUP)
    supervisor.register_callback(_cb)

    supervisor.transition_to(SafetyState.SAFE, "init")
    supervisor.transition_to(SafetyState.PASSIVE, "passive")

    assert len(events) == 2
    assert events[0] == (SafetyState.STARTUP, SafetyState.SAFE, "init")
    assert events[1] == (SafetyState.SAFE, SafetyState.PASSIVE, "passive")
