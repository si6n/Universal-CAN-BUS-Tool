"""Unit tests for Hardware Abstraction Layer (HAL) base classes and BusState enum."""

import asyncio
import json

import pytest

from src.core.contracts.ports import InMemoryTxPort, TxPort
from src.core.errors import HardwareError
from src.core.models.can_frame import CanFrame
from src.hal import AbstractBus, BusMetrics, BusState
from src.hal.virtual import VirtualBus


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


def test_abstract_bus_requires_send_raw_implementation() -> None:
    """Verify that instantiating AbstractBus without connect/disconnect/recv raises TypeError."""
    class IncompleteBus(AbstractBus):
        def send(self, frame: CanFrame) -> None: pass

    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IncompleteBus(channel_id="incomplete_0")  # type: ignore[abstract]


def test_abstract_bus_unimplemented_send_raw_raises_not_implemented() -> None:
    """D8: `send` is the abstract canonical TX method — a concrete bus that
    leaves it unimplemented cannot even be instantiated (stricter and
    recursion-proof, replacing the old runtime NotImplementedError path)."""
    class DummyNoSendBus(AbstractBus):
        def connect(self) -> None: pass
        def disconnect(self) -> None: pass
        def recv(self, timeout_s: float | None = 0.1) -> CanFrame | None: return None

    with pytest.raises(TypeError, match="Can't instantiate abstract class.*send"):
        DummyNoSendBus("no_send_0")  # type: ignore[abstract]


def test_abstract_bus_privileged_send_routes_through_send() -> None:
    """D8: the explicit gateway port dispatches via the canonical send()."""
    class RecordingBus(AbstractBus):
        def connect(self) -> None: pass
        def disconnect(self) -> None: pass
        def recv(self, timeout_s: float | None = 0.1) -> CanFrame | None: return None
        def send(self, frame: CanFrame) -> None:
            self.sent = frame

    bus = RecordingBus("rec_0")
    frame = CanFrame.create(channel_id="c0", arbitration_id=0x123, data=b"\x01")
    bus.privileged_send(frame)
    assert bus.sent is frame  # type: ignore[attr-defined]


def test_virtual_bus_implementation() -> None:
    """Verify VirtualBus connect, disconnect, _send_raw, recv, and inject_rx."""
    vbus = VirtualBus(channel_id="vcan99", bitrate=500000)
    assert not vbus.is_connected

    # Cannot send/receive before connecting
    frame = CanFrame.create(channel_id="vcan99", arbitration_id=0x700, data=b"\x11\x22")
    with pytest.raises(HardwareError, match="Cannot send"):
        vbus.send(frame)

    with pytest.raises(HardwareError, match="Cannot receive"):
        vbus.recv()

    with vbus:
        assert vbus.is_connected
        assert vbus.metrics.state == BusState.ACTIVE

        # Transmit frame via send() -> _send_raw()
        vbus.send(frame)
        assert len(vbus.sent_frames) == 1
        assert vbus.sent_frames[0].arbitration_id == 0x700
        assert vbus.metrics.tx_frames == 1

        # Receive frame via inject_rx()
        rx_frame = CanFrame.create(channel_id="vcan99", arbitration_id=0x708, data=b"\x33\x44")
        vbus.inject_rx(rx_frame)
        received = vbus.recv(timeout_s=0.05)
        assert received is not None
        assert received.arbitration_id == 0x708
        assert vbus.metrics.rx_frames == 1

        # Empty queue returns None on timeout
        assert vbus.recv(timeout_s=0.01) is None

    assert not vbus.is_connected


def test_tx_port_contract_and_in_memory_tx_port() -> None:
    """Verify TxPort protocol and InMemoryTxPort implementation."""
    tx_port: TxPort = InMemoryTxPort()
    frame = CanFrame.create(channel_id="test_c0", arbitration_id=0x555, data=b"\xAA\xBB")

    # Synchronous send
    tx_port.send_sync(frame)
    assert len(tx_port.sent_frames) == 1  # type: ignore[attr-defined]

    # Asynchronous send
    asyncio.run(tx_port.send(frame))
    assert len(tx_port.sent_frames) == 2  # type: ignore[attr-defined]
