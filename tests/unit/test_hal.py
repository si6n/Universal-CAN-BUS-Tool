"""Unit tests for Hardware Abstraction Layer (HAL) base classes and BusState enum."""

import json

from src.core.models.can_frame import CanFrame
from src.hal import AbstractBus, BusMetrics, BusState


class DummyTestBus(AbstractBus):
    """Concrete implementation of AbstractBus for unit testing."""

    def __init__(self, channel_id: str = "dummy0", bitrate: int = 500000, is_fd: bool = False) -> None:
        super().__init__(channel_id=channel_id, bitrate=bitrate, is_fd=is_fd)
        self.sent_frames: list[CanFrame] = []
        self.recv_queue: list[CanFrame] = []

    def connect(self) -> None:
        self.is_connected = True
        self.metrics.state = BusState.ACTIVE

    def disconnect(self) -> None:
        self.is_connected = False
        self.metrics.state = BusState.DISCONNECTED

    def send(self, frame: CanFrame) -> None:
        self.sent_frames.append(frame)
        self.metrics.tx_frames += 1

    def recv(self, timeout_s: float | None = 0.1) -> CanFrame | None:
        if self.recv_queue:
            frame = self.recv_queue.pop(0)
            self.metrics.rx_frames += 1
            return frame
        return None


def test_bus_state_enum_values() -> None:
    assert BusState.ACTIVE.value == "active"
    assert BusState.PASSIVE.value == "passive"
    assert BusState.BUS_OFF.value == "bus_off"
    assert BusState.DISCONNECTED.value == "disconnected"
    assert BusState.ERROR.value == "error"


def test_bus_state_string_comparisons() -> None:
    # Verify string conversion, value match, and lookup from string
    assert BusState("active") is BusState.ACTIVE
    assert BusState("passive") is BusState.PASSIVE
    assert BusState("bus_off") is BusState.BUS_OFF
    assert BusState("disconnected") is BusState.DISCONNECTED
    assert BusState("error") is BusState.ERROR
    assert str(BusState.ACTIVE) == "active"


def test_bus_state_json_serialization() -> None:
    payload = {
        "channel": "can0",
        "state": BusState.ACTIVE,
    }
    dumped = json.dumps(payload)
    assert dumped == '{"channel": "can0", "state": "active"}'

    loaded = json.loads(dumped)
    assert loaded["state"] == BusState.ACTIVE


def test_bus_metrics_initialization() -> None:
    metrics = BusMetrics(channel_id="can0", bitrate=500000)
    assert metrics.channel_id == "can0"
    assert metrics.state == BusState.ACTIVE
    assert metrics.rx_frames == 0
    assert metrics.tx_frames == 0
    assert metrics.error_frames == 0
    assert metrics.bus_load_percent == 0.0


def test_bus_metrics_state_transition() -> None:
    metrics = BusMetrics(channel_id="can0")
    assert metrics.state == BusState.ACTIVE

    metrics.state = BusState.PASSIVE
    assert metrics.state == BusState.PASSIVE

    metrics.state = BusState.BUS_OFF
    assert metrics.state == BusState.BUS_OFF

    metrics.state = BusState.DISCONNECTED
    assert metrics.state == BusState.DISCONNECTED

    metrics.state = BusState.ERROR
    assert metrics.state == BusState.ERROR


def test_abstract_bus_lifecycle_and_context_manager() -> None:
    bus = DummyTestBus("test_vcan0", bitrate=250000)
    assert not bus.is_connected

    with bus:
        assert bus.is_connected
        assert bus.metrics.state == BusState.ACTIVE

        frame = CanFrame.create(
            channel_id="test_vcan0",
            arbitration_id=0x123,
            data=b"\x01\x02\x03\x04",
            source="virtual",
        )
        bus.send(frame)
        assert bus.metrics.tx_frames == 1
        assert len(bus.sent_frames) == 1

        bus.recv_queue.append(frame)
        received = bus.recv()
        assert received is not None
        assert received.arbitration_id == 0x123
        assert bus.metrics.rx_frames == 1

    assert not bus.is_connected
    assert bus.metrics.state == BusState.DISCONNECTED
