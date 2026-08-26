"""Unit tests for RollingDiskBuffer."""

import tempfile

from src.core.models.can_frame import CanFrame
from src.engine.buffer.rolling_disk import RollingDiskBuffer


def test_rolling_disk_append_flush_read() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        disk_buf = RollingDiskBuffer(storage_dir=tmpdir, chunk_frame_threshold=5)

        for i in range(12):
            frame = CanFrame.create(
                channel_id="ch0",
                arbitration_id=i,
                data=bytes([i, i + 1]),
                timestamp_ns=i * 1000,
            )
            disk_buf.append(frame)

        # 12 frames with threshold 5 will produce 2 flushed chunks + 2 pending
        # read_all_stored_frames() flushes pending and returns all 12
        stored_frames = disk_buf.read_all_stored_frames()
        assert len(stored_frames) == 12
        assert [f.arbitration_id for f in stored_frames] == list(range(12))

        disk_buf.clear()
        assert len(disk_buf.read_all_stored_frames()) == 0
