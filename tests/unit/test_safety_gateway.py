import concurrent.futures
import time

import pytest

from src.core.errors import SafetyError
from src.core.models.can_frame import CanFrame
from src.hal.drivers.pcan_kvaser import PythonCanBus
from src.safety.estop import EmergencyStopSystem, EStopTriggerSource
from src.safety.gateway import TxSafetyGateway


def test_safety_gateway_normal_tx() -> None:
    bus = PythonCanBus(interface="virtual", channel="safety_vbus_0")
    bus.connect()

    gateway = TxSafetyGateway(bus=bus, whitelist_ids={0x7E0})
    frame = CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"\x01")

    # Transmit allowed
    assert gateway.validate_and_transmit(frame) is True
    bus.disconnect()


def test_safety_gateway_estop_blocks_all() -> None:
    bus = PythonCanBus(interface="virtual", channel="safety_vbus_1")
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

    # Reset requires correct HMAC challenge-response token
    with pytest.raises(SafetyError, match="Invalid E-Stop reset token"):
        estop.reset("wrong_token")

    nonce = estop.get_reset_nonce()
    valid_token = estop.compute_reset_token(nonce)
    estop.reset(valid_token)
    assert estop.is_engaged is False
    assert gateway.validate_and_transmit(frame) is True
    bus.disconnect()


def test_safety_gateway_whitelist_violation_triggers_estop() -> None:
    bus = PythonCanBus(interface="virtual", channel="safety_vbus_2")
    bus.connect()
    estop = EmergencyStopSystem()
    gateway = TxSafetyGateway(bus=bus, estop=estop, whitelist_ids={0x7E0})

    # Unauthorized ID 0x123
    frame_bad = CanFrame.create(channel_id="c0", arbitration_id=0x123, data=b"\x01")

    with pytest.raises(SafetyError, match="not in whitelist"):
        gateway.validate_and_transmit(frame_bad)

    # Verify that E-Stop was automatically tripped
    assert estop.is_engaged is True
    assert estop.last_event is not None
    assert estop.last_event.trigger == EStopTriggerSource.UNAUTHORIZED_PAYLOAD
    bus.disconnect()


def test_safety_gateway_speed_interlock_and_dual_confirmation() -> None:
    bus = PythonCanBus(interface="virtual", channel="safety_vbus_3")
    bus.connect()
    estop = EmergencyStopSystem()
    gateway = TxSafetyGateway(bus=bus, estop=estop, whitelist_ids={0x7E0})

    frame = CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"\x31\x01\x02\x01")

    # Critical command without user confirmation fails
    with pytest.raises(SafetyError, match="Operator dual-confirmation missing"):
        gateway.validate_and_transmit(frame, is_critical_command=True, user_confirmed=False)

    # Critical command with confirmation succeeds when stationary (speed = 0)
    gateway.update_vehicle_speed(0.0)
    assert gateway.validate_and_transmit(frame, is_critical_command=True, user_confirmed=True) is True

    # Minor sensor jitter (e.g. 0.2 km/h <= SPEED_NOISE_THRESHOLD_KMH 0.5 km/h) is permitted
    gateway.update_vehicle_speed(0.2)
    assert gateway.validate_and_transmit(frame, is_critical_command=True, user_confirmed=True) is True

    # Vehicle starts moving (speed = 25 km/h) -> Speed Interlock trips E-Stop!
    gateway.update_vehicle_speed(25.0)
    with pytest.raises(SafetyError, match="Safety Interlock"):
        gateway.validate_and_transmit(frame, is_critical_command=True, user_confirmed=True)

    assert estop.is_engaged is True
    assert estop.last_event is not None
    assert estop.last_event.trigger == EStopTriggerSource.SPEED_INTERLOCK_BREACH
    bus.disconnect()


def test_safety_gateway_rate_limiting_deque_overflow() -> None:
    """Verify that transmitting over MAX_TX_RATE_PER_SEC within 1s triggers E-Stop and raises error."""
    bus = PythonCanBus(interface="virtual", channel="safety_vbus_rate_0")
    bus.connect()
    estop = EmergencyStopSystem()
    gateway = TxSafetyGateway(bus=bus, estop=estop, whitelist_ids={0x7E0})

    frame = CanFrame.create(channel_id="c0", arbitration_id=0x7E0, data=b"\x01")

    # Transmit exactly 100 messages (MAX_TX_RATE_PER_SEC)
    for _ in range(gateway.MAX_TX_RATE_PER_SEC):
        assert gateway.validate_and_transmit(frame) is True

    assert len(gateway._tx_timestamps) == 100

    # 101st transmission must be rejected and trip E-Stop
    with pytest.raises(SafetyError) as exc_info:
        gateway.validate_and_transmit(frame)

    assert exc_info.value.code == "RATE_LIMIT_EXCEEDED"
    assert estop.is_engaged is True
    assert estop.last_event is not None
    assert estop.last_event.trigger == EStopTriggerSource.RATE_LIMIT_OVERFLOW
    bus.disconnect()


def test_safety_gateway_sliding_window_expiration() -> None:
    """Verify that deque rate limiter pops expired timestamps (> 1s)."""
    bus = PythonCanBus(interface="virtual", channel="safety_vbus_rate_1")
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


def test_safety_gateway_multithreaded_concurrency() -> None:
    """Verify thread safety under concurrent multi-threaded transmits."""
    bus = PythonCanBus(interface="virtual", channel="safety_vbus_rate_2")
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
