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

    # Empty whitelist without allow_all_for_testing
    gateway = TxSafetyGateway(bus=bus, estop=estop, whitelist_ids=set(), allow_all_for_testing=False)
    frame = CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"\x01")

    with pytest.raises(WhitelistFailClosedError) as exc_info:
        gateway.validate_and_transmit(frame)

    assert exc_info.value.code == "WHITELIST_FAIL_CLOSED"
    assert estop.is_engaged is False

    # None whitelist behaves identically
    gateway_none = TxSafetyGateway(bus=bus, estop=estop, whitelist_ids=None, allow_all_for_testing=False)
    with pytest.raises(WhitelistFailClosedError):
        gateway_none.validate_and_transmit(frame)

    bus.disconnect()


def test_safety_gateway_allow_all_for_testing_override() -> None:
    """Verify allow_all_for_testing=True allows transmission when whitelist is empty."""
    bus = VirtualBus(channel_id="safety_vbus_testing")
    bus.connect()
    gateway = TxSafetyGateway(bus=bus, whitelist_ids=set(), allow_all_for_testing=True)

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

    # INVARIANT FIX: fresh speed telemetry MUST exist before ANY critical command
    # (fail-closed boot). The prior version issued a critical command with zero
    # telemetry and expected the Stage 5 dual-confirmation error — that only
    # passed because the gateway wrongly seeded speed freshness at construction.
    gateway.update_vehicle_speed(0.0)

    # Critical command without user confirmation fails when stationary
    with pytest.raises(DualConfirmationRequiredError, match="Operator dual-confirmation missing") as exc_info:
        gateway.validate_and_transmit(frame, is_critical_command=True, user_confirmed=False)
    assert exc_info.value.code == "CONFIRMATION_REQUIRED"

    # Critical command with confirmation succeeds when stationary (speed = 0)
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
    gateway = TxSafetyGateway(bus=bus, whitelist_ids={0x100}, allow_all_for_testing=True)

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

    # Insert old timestamps (> 1.5 seconds ago) into deque.
    # INVARIANT (CAN-25): rate window entries are time.monotonic_ns() integers ONLY.
    # The prior float-seconds injection encoded a wrong invariant that required a
    # unit-guessing heuristic inside the safety-critical rate limiter.
    old_time = time.monotonic_ns() - 2_000_000_000
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
