import asyncio
import concurrent.futures
import time
from unittest.mock import MagicMock

import pytest

from src.core.contracts.ports import TxPort
from src.core.errors import SafetyError
from src.core.models.can_frame import CanFrame
from src.hal.virtual import VirtualBus
from src.safety.estop import EmergencyStopSystem, EStopTriggerSource
from src.safety.exceptions import (
    DualConfirmationRequiredError,
    FrameSanityError,
    RateLimitExceededError,
    SpeedDataStaleError,
    SpeedInterlockError,
    WhitelistFailClosedError,
    WhitelistViolationError,
)
from src.safety.gateway import TxSafetyGateway


def test_safety_gateway_normal_tx() -> None:
    bus = VirtualBus(channel_id="safety_vbus_0")
    bus.connect()

    gateway = TxSafetyGateway(bus=bus, whitelist_ids={0x7E0})
    frame = CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"\x01")

    # Transmit allowed
    assert gateway.validate_and_transmit(frame) is True
    assert len(bus.sent_frames) == 1
    bus.disconnect()


def test_safety_gateway_estop_blocks_all() -> None:
    bus = VirtualBus(channel_id="safety_vbus_1")
    bus.connect()
    estop = EmergencyStopSystem()
    gateway = TxSafetyGateway(bus=bus, estop=estop, whitelist_ids={0x7E0})

    frame = CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"\x01")
    assert gateway.validate_and_transmit(frame) is True

    # Trigger E-Stop
    estop.trigger(EStopTriggerSource.USER_UI_BUTTON, "Operator Pressed Red E-Stop Button")
    assert estop.is_engaged is True

    with pytest.raises(SafetyError, match="Emergency Stop is currently ENGAGED"):
        gateway.validate_and_transmit(frame)

    # Reset requires challenge token
    nonce = estop.get_reset_nonce()
    valid_token = estop.compute_reset_token(nonce)
    estop.reset(valid_token)

    assert estop.is_engaged is False
    assert gateway.validate_and_transmit(frame) is True
    bus.disconnect()


def test_safety_gateway_whitelist_violation_triggers_estop() -> None:
    bus = VirtualBus(channel_id="safety_vbus_2")
    bus.connect()
    estop = EmergencyStopSystem()
    gateway = TxSafetyGateway(bus=bus, estop=estop, whitelist_ids={0x7E0})

    # Unauthorized ID 0x123
    frame_bad = CanFrame.create(channel_id="c0", arbitration_id=0x123, data=b"\x01")

    with pytest.raises(WhitelistViolationError) as exc_info:
        gateway.validate_and_transmit(frame_bad)

    assert exc_info.value.code == "WHITELIST_VIOLATION"

    # Verify that E-Stop was automatically tripped
    assert estop.is_engaged is True
    assert estop.last_event is not None
    assert estop.last_event.trigger == EStopTriggerSource.UNAUTHORIZED_PAYLOAD
    bus.disconnect()


def test_safety_gateway_fail_closed_empty_whitelist() -> None:
    """Verify that empty or None whitelist is strictly Fail-Closed (R3)."""
    bus = VirtualBus(channel_id="safety_vbus_fc")
    bus.connect()
    estop = EmergencyStopSystem()

    # Empty whitelist — production gateway is strictly Fail-Closed
    gateway = TxSafetyGateway(bus=bus, estop=estop, whitelist_ids=set())
    frame = CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"\x01")

    with pytest.raises(WhitelistFailClosedError) as exc_info:
        gateway.validate_and_transmit(frame)

    assert exc_info.value.code == "WHITELIST_FAIL_CLOSED"
    assert estop.is_engaged is False

    # None whitelist behaves identically
    gateway_none = TxSafetyGateway(bus=bus, estop=estop, whitelist_ids=None)
    with pytest.raises(WhitelistFailClosedError):
        gateway_none.validate_and_transmit(frame)

    bus.disconnect()


def test_safety_gateway_for_testing_factory_bypasses_whitelist() -> None:
    """Verify the explicit for_testing() factory allows transmission when whitelist is empty."""
    bus = VirtualBus(channel_id="safety_vbus_testing")
    bus.connect()
    gateway = TxSafetyGateway.for_testing(bus=bus, whitelist_ids=set())

    frame = CanFrame.create(channel_id="c0", arbitration_id=0x123, data=b"\x01")
    assert gateway.validate_and_transmit(frame) is True
    assert len(bus.sent_frames) == 1
    bus.disconnect()


def test_safety_gateway_speed_interlock_and_dual_confirmation() -> None:
    bus = VirtualBus(channel_id="safety_vbus_3")
    bus.connect()
    estop = EmergencyStopSystem()
    gateway = TxSafetyGateway(bus=bus, estop=estop, whitelist_ids={0x7E0})

    frame = CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"\x31\x01\x02\x01")

    # Critical command without user confirmation fails when stationary
    with pytest.raises(DualConfirmationRequiredError, match="Operator dual-confirmation missing") as exc_info:
        gateway.validate_and_transmit(frame, is_critical_command=True, user_confirmed=False)
    assert exc_info.value.code == "CONFIRMATION_REQUIRED"

    # Critical command with confirmation succeeds when stationary (speed = 0)
    gateway.update_vehicle_speed(0.0)
    assert gateway.validate_and_transmit(frame, is_critical_command=True, user_confirmed=True) is True

    # Minor sensor jitter (e.g. 0.2 km/h <= SPEED_NOISE_THRESHOLD_KMH 0.5 km/h) is permitted
    gateway.update_vehicle_speed(0.2)
    assert gateway.validate_and_transmit(frame, is_critical_command=True, user_confirmed=True) is True

    # Vehicle starts moving (speed = 25 km/h) -> Speed Interlock trips E-Stop!
    gateway.update_vehicle_speed(25.0)
    with pytest.raises(SpeedInterlockError, match="Safety Interlock") as exc_info2:
        gateway.validate_and_transmit(frame, is_critical_command=True, user_confirmed=True)
    assert exc_info2.value.code == "SPEED_INTERLOCK_ACTIVE"

    assert estop.is_engaged is True
    assert estop.last_event is not None
    assert estop.last_event.trigger == EStopTriggerSource.SPEED_INTERLOCK_BREACH
    bus.disconnect()


def test_safety_gateway_rule_ordering_moving_vehicle_unconfirmed_command() -> None:
    """Verify CAN-24 Rule Ordering: Speed Interlock (Stage 4) takes precedence over Dual Confirmation (Stage 5)."""
    bus = VirtualBus(channel_id="safety_vbus_order")
    bus.connect()
    estop = EmergencyStopSystem()
    gateway = TxSafetyGateway(bus=bus, estop=estop, whitelist_ids={0x7E0})

    frame = CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"\x11\x01")

    # Set vehicle in motion
    gateway.update_vehicle_speed(50.0)

    # Attempt critical command WITHOUT confirmation
    with pytest.raises(SpeedInterlockError) as exc_info:
        gateway.validate_and_transmit(frame, is_critical_command=True, user_confirmed=False)

    assert exc_info.value.code == "SPEED_INTERLOCK_ACTIVE"
    assert estop.is_engaged is True
    assert estop.last_event is not None
    assert estop.last_event.trigger == EStopTriggerSource.SPEED_INTERLOCK_BREACH
    bus.disconnect()


def test_safety_gateway_speed_staleness_rejection() -> None:
    """Verify that stale vehicle speed telemetry (> 1.0s) blocks critical commands (CAN-24)."""
    bus = VirtualBus(channel_id="safety_vbus_stale")
    bus.connect()
    estop = EmergencyStopSystem()
    gateway = TxSafetyGateway(bus=bus, estop=estop, whitelist_ids={0x7E0})

    frame = CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"\x11\x01")

    # Set speed update timestamp to 2 seconds in the past
    stale_ts_ns = time.monotonic_ns() - 2_000_000_000
    gateway.update_vehicle_speed(0.0, timestamp_ns=stale_ts_ns)

    with pytest.raises(SpeedDataStaleError) as exc_info:
        gateway.validate_and_transmit(frame, is_critical_command=True, user_confirmed=True)

    assert exc_info.value.code == "SPEED_DATA_STALE"
    assert estop.is_engaged is True
    assert estop.last_event is not None
    assert estop.last_event.trigger == EStopTriggerSource.SPEED_INTERLOCK_BREACH
    bus.disconnect()


def test_safety_gateway_frame_sanity_checks() -> None:
    """Verify Stage 1: Frame Sanity & Range Validation."""
    bus = VirtualBus(channel_id="safety_vbus_sanity")
    bus.connect()
    gateway = TxSafetyGateway.for_testing(bus=bus, whitelist_ids={0x100})

    # 1. Non-CanFrame object
    with pytest.raises(FrameSanityError) as exc1:
        gateway.validate_and_transmit("invalid_frame_string")  # type: ignore[arg-type]
    assert exc1.value.code == "INVALID_FRAME_SANITY"

    # 2. Mock frame with out-of-range standard ID
    mock_bad_id = MagicMock(spec=CanFrame)
    mock_bad_id.is_extended = False
    mock_bad_id.arbitration_id = 0x800
    mock_bad_id.is_fd = False
    mock_bad_id.data = b"\x01"
    with pytest.raises(FrameSanityError) as exc2:
        gateway.validate_and_transmit(mock_bad_id)
    assert exc2.value.code == "INVALID_FRAME_SANITY"

    # 3. Mock frame with Classic CAN payload > 8 bytes
    mock_bad_len = MagicMock(spec=CanFrame)
    mock_bad_len.is_extended = False
    mock_bad_len.arbitration_id = 0x100
    mock_bad_len.is_fd = False
    mock_bad_len.data = b"\x01" * 12
    with pytest.raises(FrameSanityError) as exc3:
        gateway.validate_and_transmit(mock_bad_len)
    assert exc3.value.code == "INVALID_FRAME_SANITY"

    # 4. Valid CAN-FD frame up to 64 bytes passes sanity check
    frame_valid_fd = CanFrame.create(channel_id="c0", arbitration_id=0x100, data=b"\x01" * 64, is_fd=True)
    assert gateway.validate_and_transmit(frame_valid_fd) is True

    bus.disconnect()


def test_safety_gateway_rate_limiting_deque_overflow() -> None:
    """Verify that transmitting over MAX_TX_RATE_PER_SEC within 1s triggers E-Stop and raises error."""
    bus = VirtualBus(channel_id="safety_vbus_rate_0")
    bus.connect()
    estop = EmergencyStopSystem()
    gateway = TxSafetyGateway(bus=bus, estop=estop, whitelist_ids={0x7E0})

    frame = CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"\x01")

    # Transmit exactly 100 messages (MAX_TX_RATE_PER_SEC)
    for _ in range(gateway.MAX_TX_RATE_PER_SEC):
        assert gateway.validate_and_transmit(frame) is True

    assert len(gateway._tx_timestamps) == 100

    # 101st transmission must be rejected and trip E-Stop
    with pytest.raises(RateLimitExceededError) as exc_info:
        gateway.validate_and_transmit(frame)

    assert exc_info.value.code == "RATE_LIMIT_EXCEEDED"
    assert estop.is_engaged is True
    assert estop.last_event is not None
    assert estop.last_event.trigger == EStopTriggerSource.RATE_LIMIT_OVERFLOW
    bus.disconnect()


def test_safety_gateway_sliding_window_expiration() -> None:
    """Verify that deque rate limiter pops expired timestamps (> 1s)."""
    bus = VirtualBus(channel_id="safety_vbus_rate_1")
    bus.connect()
    gateway = TxSafetyGateway(bus=bus, whitelist_ids={0x7E0})

    frame = CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"\x01")

    # Insert old timestamps (> 1.5 seconds ago) into deque
    old_time = time.monotonic() - 2.0
    for _ in range(50):
        gateway._tx_timestamps.append(old_time)

    assert len(gateway._tx_timestamps) == 50

    # Transmit a new frame -> expired timestamps should be popped out
    assert gateway.validate_and_transmit(frame) is True
    assert len(gateway._tx_timestamps) == 1
    bus.disconnect()


def test_safety_gateway_tx_port_protocol_conformance() -> None:
    """Verify TxSafetyGateway implements TxPort (send and send_sync)."""
    bus = VirtualBus(channel_id="safety_vbus_port")
    bus.connect()
    gateway = TxSafetyGateway(bus=bus, whitelist_ids={0x7E0})

    assert isinstance(gateway, TxPort)

    frame = CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"\x02\x10\x01")

    # Synchronous TxPort entry
    gateway.send_sync(frame)
    assert len(bus.sent_frames) == 1

    # Asynchronous TxPort entry
    asyncio.run(gateway.send(frame))
    assert len(bus.sent_frames) == 2

    bus.disconnect()


def test_safety_gateway_multithreaded_concurrency() -> None:
    """Verify thread safety under concurrent multi-threaded transmits."""
    bus = VirtualBus(channel_id="safety_vbus_rate_2")
    bus.connect()
    gateway = TxSafetyGateway(bus=bus, whitelist_ids={0x7E0})

    frame = CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"\x01")

    # Run 50 transmits across 4 concurrent worker threads (total 50 frames <= 100 limit)
    def worker_transmit() -> bool:
        return gateway.validate_and_transmit(frame)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(worker_transmit) for _ in range(50)]
        results = [f.result() for f in futures]

    assert all(results)
    assert len(gateway._tx_timestamps) == 50
    bus.disconnect()


# ============================================================================
# F-18: Per-Category Token-Bucket Budget DoD tests
# ============================================================================


def _budget_gateway(channel: str) -> tuple[VirtualBus, TxSafetyGateway]:
    bus = VirtualBus(channel_id=channel)
    bus.connect()
    gateway = TxSafetyGateway(bus=bus, whitelist_ids={0x7E0})
    return bus, gateway


def test_protocol_burst_budget_allows_full_bam_transfer() -> None:
    """F-18 DoD: a full J1939 BAM transfer (255 packets) must NOT trip E-Stop."""
    bus, gateway = _budget_gateway("safety_vbus_bam")
    frame = CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"")

    # 255 CF packets — exactly the BAM maximum; must all pass without E-Stop
    for _ in range(255):
        assert gateway.validate_and_transmit(frame, budget_category="protocol_burst") is True

    assert gateway.estop.is_engaged is False
    assert len(bus.sent_frames) == 255
    bus.disconnect()


def test_protocol_burst_budget_exhaustion_at_capacity_plus_one() -> None:
    """F-18: protocol_burst capacity is 255 — the 256th burst frame is rejected."""
    bus, gateway = _budget_gateway("safety_vbus_bam2")
    frame = CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"")

    for _ in range(255):
        gateway.validate_and_transmit(frame, budget_category="protocol_burst")

    with pytest.raises(RateLimitExceededError, match="protocol_burst"):
        gateway.validate_and_transmit(frame, budget_category="protocol_burst")
    bus.disconnect()


def test_diagnostic_budget_capacity_is_ten() -> None:
    """F-18: diagnostic budget (10 tokens, 10/s refill) rejects the 11th frame."""
    bus, gateway = _budget_gateway("safety_vbus_diag")
    frame = CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"")

    for _ in range(10):
        assert gateway.validate_and_transmit(frame, budget_category="diagnostic") is True

    with pytest.raises(RateLimitExceededError, match="diagnostic"):
        gateway.validate_and_transmit(frame, budget_category="diagnostic")
    bus.disconnect()


def test_calibration_budget_capacity_is_five() -> None:
    """F-18: calibration budget (5 tokens, 5/s refill) rejects the 6th frame."""
    bus, gateway = _budget_gateway("safety_vbus_cal")
    frame = CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"")

    for _ in range(5):
        assert gateway.validate_and_transmit(frame, budget_category="calibration") is True

    with pytest.raises(RateLimitExceededError, match="calibration"):
        gateway.validate_and_transmit(frame, budget_category="calibration")
    bus.disconnect()


def test_unknown_budget_category_is_rejected() -> None:
    """F-18: an unregistered category fails closed instead of silently passing."""
    bus, gateway = _budget_gateway("safety_vbus_unk")
    frame = CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"")

    with pytest.raises(FrameSanityError, match="Unknown TX budget category"):
        gateway.validate_and_transmit(frame, budget_category="nonexistent_category")
    bus.disconnect()


def test_budgets_are_independent_per_category() -> None:
    """F-18: draining one category must not consume another's tokens."""
    bus, gateway = _budget_gateway("safety_vbus_indep")
    frame = CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"")

    # Drain diagnostic fully...
    for _ in range(10):
        gateway.validate_and_transmit(frame, budget_category="diagnostic")
    # ...calibration must still have its own 5 tokens
    for _ in range(5):
        assert gateway.validate_and_transmit(frame, budget_category="calibration") is True
    bus.disconnect()


def test_whitelist_masks_authorize_id_family() -> None:
    """E5: a (value, mask) pair authorizes the whole protocol-response family."""
    bus = VirtualBus(channel_id="safety_vbus_mask")
    bus.connect()

    # Authorize every TP.CM frame sourced from SA 0xF9 (any peer in the DA byte)
    masks = [(0x18EC00F9, 0x18EC00FF)]
    gateway = TxSafetyGateway(bus=bus, whitelist_masks=masks)

    # Responses to two different peers both match (id & mask) == value
    to_peer_a = CanFrame.create(channel_id="c0", arbitration_id=0x18EC01F9, data=b"\x11", is_extended=True)
    to_peer_b = CanFrame.create(channel_id="c0", arbitration_id=0x18EC42F9, data=b"\x11", is_extended=True)
    assert gateway.validate_and_transmit(to_peer_a) is True
    assert gateway.validate_and_transmit(to_peer_b) is True

    # A frame sourced from a DIFFERENT source address does not match the family
    other_sa = CanFrame.create(channel_id="c0", arbitration_id=0x18EC01AA, data=b"\x11", is_extended=True)
    with pytest.raises(WhitelistViolationError):
        gateway.validate_and_transmit(other_sa)
    bus.disconnect()


def test_whitelist_masks_alone_are_not_fail_closed() -> None:
    """E5: providing masks (without exact IDs) counts as a configured whitelist."""
    bus = VirtualBus(channel_id="safety_vbus_mask_only")
    bus.connect()

    gateway = TxSafetyGateway(bus=bus, whitelist_masks=[(0x7E0, 0x7FF)])
    frame = CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"\x01")

    # Must not raise WhitelistFailClosedError; the ID matches the mask
    assert gateway.validate_and_transmit(frame) is True
    bus.disconnect()


def test_production_constructor_has_no_testing_bypass_flag() -> None:
    """B1 regression: allow_all_for_testing must not be a production constructor knob."""
    import inspect

    params = inspect.signature(TxSafetyGateway.__init__).parameters
    assert "allow_all_for_testing" not in params


# ============================================================================
# Lock-Scope Refactor Regression Tests (H2)
# ============================================================================


def test_estop_callback_does_not_block_on_slow_driver_io() -> None:
    """H2 Regression: E-Stop callback completes immediately even when privileged_send blocks.

    Verifies that the gateway lock is released before calling privileged_send, so
    E-Stop callbacks (which acquire the same lock) do not wait for driver I/O.
    """
    import threading

    # Controllable mock bus with event-gated send
    class SlowBus:
        def __init__(self) -> None:
            self.send_gate = threading.Event()
            self.privileged_send_entered = threading.Event()
            self.sent_frames: list[CanFrame] = []

        def connect(self) -> None:
            pass

        def disconnect(self) -> None:
            pass

        def privileged_send(self, frame: CanFrame) -> None:
            self.privileged_send_entered.set()
            self.send_gate.wait()  # Block until gate is opened
            self.sent_frames.append(frame)

    bus = SlowBus()
    estop = EmergencyStopSystem()
    gateway = TxSafetyGateway(bus=bus, estop=estop, whitelist_ids={0x7E0})

    frame = CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"\x01")

    callback_completed = threading.Event()

    def estop_callback(event: object) -> None:
        callback_completed.set()

    estop.register_callback(estop_callback)

    # Start transmit in background (will block in privileged_send)
    def transmit_worker() -> None:
        try:
            gateway.validate_and_transmit(frame)
        except SafetyError:
            pass

    tx_thread = threading.Thread(target=transmit_worker)
    tx_thread.start()

    # Wait for privileged_send to be entered
    assert bus.privileged_send_entered.wait(timeout=2.0), "privileged_send was not entered"

    # Trigger E-Stop while send is blocked
    estop.trigger(EStopTriggerSource.USER_UI_BUTTON, "Operator pressed red button")

    # Callback must complete immediately (not block on driver I/O)
    assert callback_completed.wait(timeout=2.0), "E-Stop callback blocked on gateway lock"

    # Unblock the send and clean up
    bus.send_gate.set()
    tx_thread.join(timeout=2.0)

    assert estop.is_engaged


def test_estop_race_window_snapshot_already_engaged() -> None:
    """H2 Regression: E-Stop engaged during Stage 2 → tokens rolled back on Phase 2 rejection.

    Scenario: estop.is_engaged=True at snapshot time (caught in Stage 2 or between
    Stage 2 and snapshot). Tokens are consumed but frame is rejected in Phase 2.
    Verify rollback occurs.
    """
    bus = VirtualBus(channel_id="safety_vbus_race_engaged")
    bus.connect()
    estop = EmergencyStopSystem()
    gateway = TxSafetyGateway(bus=bus, estop=estop, whitelist_ids={0x7E0})

    frame = CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"\x01")

    # Engage E-Stop before validation
    estop.trigger(EStopTriggerSource.USER_UI_BUTTON, "Pre-engaged")
    assert estop.is_engaged

    initial_timestamps = len(gateway._tx_timestamps)
    initial_budget_tokens = gateway._budgets["default"]._tokens

    # Attempt transmission — should be rejected in Stage 2 (no token consumption)
    with pytest.raises(SafetyError, match="Emergency Stop is currently ENGAGED"):
        gateway.validate_and_transmit(frame)

    # Verify no tokens were consumed (Stage 2 rejection happens before Stage 6)
    assert len(gateway._tx_timestamps) == initial_timestamps
    assert gateway._budgets["default"]._tokens == initial_budget_tokens
    assert len(bus.sent_frames) == 0

    bus.disconnect()


def test_estop_race_window_triggered_between_phases() -> None:
    """H2 Regression: E-Stop triggered between Phase 1 (lock release) and Phase 3 (send).

    Scenario: estop snapshot clear → estop.trigger() in another thread → Phase 2
    detects engagement → tokens rolled back, frame rejected, no send.
    """
    import threading
    from unittest.mock import Mock

    estop = EmergencyStopSystem()

    # Mock bus that signals when privileged_send is about to be called
    bus = Mock()
    bus.sent_frames = []

    phase1_completed = threading.Event()
    estop_triggered = threading.Event()

    # Patch estop.is_engaged property to trigger E-Stop after Phase 1 snapshot
    call_count = [0]
    def patched_is_engaged_getter(self: EmergencyStopSystem) -> bool:
        call_count[0] += 1
        # First call: Stage 2 check (inside lock) → return False
        # Second call: snapshot at lock release → return False, signal Phase 1 done
        # Third call: Phase 2 double-check → trigger estop, return True
        if call_count[0] == 2:
            phase1_completed.set()
        elif call_count[0] == 3:
            if not estop_triggered.is_set():
                estop._is_engaged = True
                estop_triggered.set()
        return estop._is_engaged

    # Monkey-patch the property
    original_property = type(estop).is_engaged
    type(estop).is_engaged = property(lambda self: patched_is_engaged_getter(self))

    try:
        gateway = TxSafetyGateway(bus=bus, estop=estop, whitelist_ids={0x7E0})
        frame = CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"\x01")

        initial_budget_tokens = gateway._budgets["default"]._tokens

        # Attempt transmission — Phase 2 should detect estop and rollback
        with pytest.raises(SafetyError, match="Emergency Stop is currently ENGAGED"):
            gateway.validate_and_transmit(frame)

        # Verify tokens were rolled back
        assert len(gateway._tx_timestamps) == 0
        assert gateway._budgets["default"]._tokens == initial_budget_tokens
        assert not bus.privileged_send.called
        assert estop._is_engaged
    finally:
        # Restore original property
        type(estop).is_engaged = original_property
