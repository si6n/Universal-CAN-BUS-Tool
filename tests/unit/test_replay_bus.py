import tempfile
import threading
import time
from pathlib import Path

import pytest

from src.core.models.can_frame import CanFrame
from src.hal.replay.parsers import VectorAscParser
from src.hal.replay.player import ReplayBus

SAMPLE_ASC_CONTENT = """date Mon Aug 24 12:00:00 2026
base hex  timestamps absolute
internal events logged
// Sample CAN traffic
   0.000000 1  18FEEE00x       Rx   d 8 01 02 03 04 05 06 07 08
   0.050000 1  18FEF200x       Rx   d 8 10 20 30 40 50 60 70 80
   0.100000 CANFD 1 Rx 123 1 0 12 12 01 02 03 04 05 06 07 08 09 0A 0B 0C
"""


def test_vector_asc_parser() -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".asc", delete=False) as tmp:
        tmp.write(SAMPLE_ASC_CONTENT)
        tmp_path = Path(tmp.name)

    try:
        frames = VectorAscParser.parse_file(tmp_path)
        assert len(frames) == 3

        # Frame 1: Classic CAN J1939 (Engine Temp)
        f1 = frames[0]
        assert f1.channel_id == "ch1"
        assert f1.arbitration_id == 0x18FEEE00
        assert f1.is_extended is True
        assert f1.is_fd is False
        assert f1.dlc == 8
        assert f1.data == b"\x01\x02\x03\x04\x05\x06\x07\x08"
        assert f1.timestamp_ns == 0

        # Frame 2: Classic CAN J1939 (Fuel Economy)
        f2 = frames[1]
        assert f2.arbitration_id == 0x18FEF200
        assert f2.timestamp_ns == 50_000_000  # 50ms = 50,000,000ns

        # Frame 3: CAN-FD frame
        f3 = frames[2]
        assert f3.arbitration_id == 0x123
        assert f3.is_extended is False
        assert f3.is_fd is True
        assert f3.brs is True
        assert f3.dlc == 12
        assert len(f3.data) == 12
        assert f3.timestamp_ns == 100_000_000
    finally:
        tmp_path.unlink(missing_ok=True)


def test_replay_bus_step_and_reset() -> None:
    frames = [
        CanFrame.create(channel_id="ch1", arbitration_id=0x100, data=b"\x01", timestamp_ns=0),
        CanFrame.create(channel_id="ch1", arbitration_id=0x200, data=b"\x02", timestamp_ns=1000),
    ]
    bus = ReplayBus(frames)
    assert bus.frame_count == 2
    assert bus.has_next is True

    f1 = bus.step()
    assert f1 is not None
    assert f1.arbitration_id == 0x100

    f2 = bus.step()
    assert f2 is not None
    assert f2.arbitration_id == 0x200

    assert bus.step() is None
    assert bus.has_next is False

    bus.reset()
    assert bus.has_next is True
    assert bus.step() == f1


def test_replay_bus_play() -> None:
    frames = [
        CanFrame.create(channel_id="ch1", arbitration_id=0x100, data=b"\x01", timestamp_ns=0),
        CanFrame.create(channel_id="ch1", arbitration_id=0x200, data=b"\x02", timestamp_ns=10_000),
    ]
    bus = ReplayBus(frames)
    received: list[CanFrame] = []

    bus.play(callback=lambda f: received.append(f), speed=100.0)
    assert len(received) == 2
    assert received[0].arbitration_id == 0x100
    assert received[1].arbitration_id == 0x200


def test_replay_bus_timing_accuracy() -> None:
    """Verify master clock synchronization with 10ms intervals."""
    # 3 frames separated by 10ms: 0ms, 10ms, 20ms
    frames = [
        CanFrame.create(channel_id="ch1", arbitration_id=0x100, data=b"\x01", timestamp_ns=0),
        CanFrame.create(channel_id="ch1", arbitration_id=0x200, data=b"\x02", timestamp_ns=10_000_000),
        CanFrame.create(channel_id="ch1", arbitration_id=0x300, data=b"\x03", timestamp_ns=20_000_000),
    ]
    bus = ReplayBus(frames)
    received: list[tuple[CanFrame, float]] = []

    t_start = time.perf_counter()
    bus.play(callback=lambda f: received.append((f, time.perf_counter())), speed=1.0)
    t_elapsed = time.perf_counter() - t_start

    assert len(received) == 3
    # Total duration should be ~20ms (0.020s) with tight tolerance
    assert 0.015 <= t_elapsed <= 0.050


def test_replay_bus_stop_event_cancellation() -> None:
    """Verify playback terminates immediately when stop_event is triggered."""
    frames = [
        CanFrame.create(channel_id="ch1", arbitration_id=0x100 + i, data=b"\x00", timestamp_ns=i * 20_000_000)
        for i in range(10)
    ]
    bus = ReplayBus(frames)
    stop_event = threading.Event()
    received: list[CanFrame] = []

    def on_frame(f: CanFrame) -> None:
        received.append(f)
        if len(received) == 2:
            stop_event.set()

    bus.play(callback=on_frame, speed=1.0, stop_event=stop_event)
    assert len(received) == 2


def test_replay_bus_invalid_speed_and_empty() -> None:
    bus = ReplayBus([])
    bus.play(callback=lambda f: None)  # Empty play should return immediately

    bus_with_frames = ReplayBus([CanFrame.create(channel_id="ch0", arbitration_id=0x100, data=b"")])
    with pytest.raises(ValueError, match="Replay speed must be positive"):
        bus_with_frames.play(callback=lambda f: None, speed=0.0)

    with pytest.raises(ValueError, match="Replay speed must be positive"):
        bus_with_frames.play(callback=lambda f: None, speed=-1.0)


def test_replay_bus_load_frames() -> None:
    bus = ReplayBus()
    assert bus.frame_count == 0
    f1 = CanFrame.create(channel_id="ch1", arbitration_id=0x555, data=b"\x01")
    bus.load_frames([f1])
    assert bus.frame_count == 1
    assert bus.step() == f1
    assert bus.has_next is False
