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

    def _send_raw(self, frame: CanFrame) -> None:
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
        # CAN-02: AbstractBus exposes no public send(); the HAL primitive is
        # _send_raw() and only TxSafetyGateway may reach it in production.
        bus._send_raw(frame)
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
        def _send_raw(self, frame: CanFrame) -> None: pass

    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IncompleteBus(channel_id="incomplete_0")  # type: ignore[abstract]


def test_abstract_bus_has_no_public_send_bypass() -> None:
    """CAN-02 regression: the legacy public send() choke-point bypass is gone.

    ``AbstractBus.send()`` let UDS, demo, UI and replay callers transmit around
    the 6-stage safety pipeline, and its ``_send_raw -> send()`` re-entry
    fallback let subclasses override ``send()`` to silently bypass the gateway.
    Neither may come back.
    """
    assert not hasattr(AbstractBus, "send")
    assert "_send_raw" in AbstractBus.__abstractmethods__


def test_abstract_bus_without_send_raw_fails_at_construction() -> None:
    """A bus with no TX primitive must fail closed at construction, not at first TX."""
    class DummyNoSendRawBus(AbstractBus):
        def connect(self) -> None: pass
        def disconnect(self) -> None: pass
        def recv(self, timeout_s: float | None = 0.1) -> CanFrame | None: return None

    with pytest.raises(TypeError, match="abstract method.*_send_raw"):
        DummyNoSendRawBus("no_send_raw_0")  # type: ignore[abstract]


def test_virtual_bus_implementation() -> None:
    """Verify VirtualBus connect, disconnect, _send_raw, recv, and inject_rx."""
    vbus = VirtualBus(channel_id="vcan99", bitrate=500000)
    assert not vbus.is_connected

    # Cannot send/receive before connecting
    frame = CanFrame.create(channel_id="vcan99", arbitration_id=0x700, data=b"\x11\x22")
    with pytest.raises(HardwareError, match="Cannot send"):
        vbus._send_raw(frame)

    with pytest.raises(HardwareError, match="Cannot receive"):
        vbus.recv()

    with vbus:
        assert vbus.is_connected
        assert vbus.metrics.state == BusState.ACTIVE

        # Transmit frame via the protected HAL primitive (gateway-owned in prod)
        vbus._send_raw(frame)
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
