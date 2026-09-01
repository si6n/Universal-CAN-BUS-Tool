"""Unit tests for python-can driver wrapper."""

import pytest

from src.core.errors import HardwareError
from src.core.models.can_frame import CanFrame
from src.hal.drivers.pcan_kvaser import PythonCanBus


def test_virtual_bus_connect_send_recv() -> None:
    bus1 = PythonCanBus(interface="virtual", channel="vchan0")
    bus2 = PythonCanBus(interface="virtual", channel="vchan0")

    bus1.connect()
    bus2.connect()

    try:
        assert bus1.is_connected is True
        assert bus2.is_connected is True

        tx_frame = CanFrame.create(
            channel_id="vchan0",
            arbitration_id=0x18FEEE00,
            data=b"\x01\x02\x03\x04\x05\x06\x07\x08",
        )

        bus1.send(tx_frame)
        rx_frame = bus2.recv(timeout_s=0.5)

        assert rx_frame is not None
        assert rx_frame.arbitration_id == 0x18FEEE00
        assert rx_frame.data == b"\x01\x02\x03\x04\x05\x06\x07\x08"
        assert rx_frame.is_extended is True

        # Check metrics
        assert bus1.metrics.tx_frames == 1
        assert bus2.metrics.rx_frames == 1
    finally:
        bus1.disconnect()
        bus2.disconnect()


def test_listen_only_mode_blocks_tx() -> None:
    bus = PythonCanBus(interface="virtual", channel="vchan_passive", listen_only=True)
    bus.connect()

    try:
        frame = CanFrame.create(channel_id="vchan", arbitration_id=0x123, data=b"\x00")
        with pytest.raises(HardwareError, match="Listen-Only"):
            bus.send(frame)
    finally:
        bus.disconnect()


def test_listen_only_passes_busstate_enum_to_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    # D1 regression: vendor drivers check `state in [BusState.ACTIVE, BusState.PASSIVE]`;
    # BusState is a plain Enum, so the former string "PASSIVE" raised ValueError
    # and silently broke listen-only connections and bitrate scanning.
    import can as can_module

    captured: dict[str, object] = {}

    class _FakeBus:
        def shutdown(self) -> None:
            pass

    def _fake_bus_factory(**kwargs: object) -> _FakeBus:
        captured.update(kwargs)
        return _FakeBus()

    monkeypatch.setattr(can_module, "Bus", _fake_bus_factory)

    bus = PythonCanBus(interface="pcan", channel="PCAN_USBBUS1", listen_only=True)
    bus.connect()

    assert bus.is_connected is True
    assert captured["state"] is can_module.BusState.PASSIVE
    assert not isinstance(captured["state"], str)
