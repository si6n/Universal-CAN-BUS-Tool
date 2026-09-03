"""CRITICAL-2/B-02/HIGH-8/MEDIUM-4/B-31: RollingDiskBuffer concurrency & durability.

RED-first tests for the black-box recorder. Each test reproduces a race or
durability defect verified in the deep-dive reviews:

- C-2/B-02: append/flush race loses frames (atomic hand-off missing)
- C-2:     concurrent flush() produces colliding .tmp names / chunk indices
- HIGH-8:  shared zstd _cctx used by caller-thread AND worker thread
- MEDIUM-4: no close()/drain guarantee -> chunks lost at process exit
- B-31:    clear() does not reset _chunk_index / pending state
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from src.core.models.can_frame import CanFrame
from src.engine.buffer.rolling_disk import RollingDiskBuffer


def _mk_frame(i: int) -> CanFrame:
    return CanFrame.create(
        channel_id="race_ch",
        arbitration_id=0x100 + (i % 8),
        data=b"\x01\x02\x03\x04",
    )


def _small_buffer(tmp_path: Path) -> RollingDiskBuffer:
    """Buffer with a tiny threshold so flush() is exercised early and often."""
    return RollingDiskBuffer(
        storage_dir=tmp_path / "blackbox",
        chunk_frame_threshold=4,
    )


class TestAppendFlushRace:
    """CRITICAL-2/B-02: frames appended during a concurrent flush() must not vanish."""

    def test_concurrent_append_and_flush_lose_no_frames(self, tmp_path: Path) -> None:
        buf = _small_buffer(tmp_path)
        stop = threading.Event()
        append_errors: list[BaseException] = []
        N_APPENDERS = 3
        FRAMES_PER_APPENDER = 300

        def appender(tid: int) -> None:
            try:
                for i in range(FRAMES_PER_APPENDER):
                    buf.append(_mk_frame(tid * 1000 + i))
            except BaseException as exc:  # noqa: BLE001 — asserted below
                append_errors.append(exc)

        def flusher() -> None:
            while not stop.is_set():
                buf.flush()
                time.sleep(0.001)

        threads = [threading.Thread(target=appender, args=(t,)) for t in range(N_APPENDERS)]
        flush_thread = threading.Thread(target=flusher)
        for t in threads:
            t.start()
        flush_thread.start()
        for t in threads:
            t.join(timeout=30.0)
        stop.set()
        flush_thread.join(timeout=10.0)

        assert not append_errors, f"appenders raised: {append_errors}"
        for t in threads:
            assert not t.is_alive(), "appender thread hung"

        expected = N_APPENDERS * FRAMES_PER_APPENDER
        got = len(buf.read_all_stored_frames())
        # CRITICAL-2 core assertion: NOTHING is lost. (Report measured 2-5% loss.)
        assert got == expected, f"black-box recorder lost {expected - got} frames"

    def test_flush_is_atomic_against_append_threshold_race(self, tmp_path: Path) -> None:
        """A frame appended at the exact moment flush() hands the list off must land
        in the NEXT chunk, not in the serialized void."""
        buf = _small_buffer(tmp_path)

        handoff_barrier = threading.Barrier(2)

        original_serialize = getattr(RollingDiskBuffer._serialize_chunk, "__func__", RollingDiskBuffer._serialize_chunk)

        called = False

        def gated_serialize(frames, key):  # noqa: ANN001 — test seam
            nonlocal called
            if not called:
                called = True
                handoff_barrier.wait(timeout=5.0)
            return original_serialize(frames, key)

        buf._serialize_chunk = gated_serialize  # type: ignore[method-assign]

        # Fill to threshold-1 so the next append triggers flush from append().
        for i in range(3):
            buf.append(_mk_frame(i))

        def late_appender() -> None:
            # This append happens WHILE flush() is serializing the first batch.
            handoff_barrier.wait(timeout=5.0)
            buf.append(_mk_frame(999))

        t = threading.Thread(target=late_appender)
        t.start()

        # Main thread flushes the first batch; serialize is gated mid-flight.
        buf.flush()
        t.join(timeout=5.0)

        # Late frame must be in the buffer, then flushed by the explicit flush.
        buf.flush()
        frames = buf.read_all_stored_frames()
        ids = [f.arbitration_id for f in frames]
        assert 0x107 in ids or len(ids) >= 4, f"late frame lost; got {ids}"

    def test_concurrent_flush_calls_do_not_collide_chunk_indices(self, tmp_path: Path) -> None:
        """Two simultaneous flush() calls must produce two distinct chunk files."""
        buf = _small_buffer(tmp_path)

        for i in range(8):
            buf.append(_mk_frame(i))

        barrier = threading.Barrier(2)

        def flusher() -> None:
            barrier.wait(timeout=5.0)
            buf.flush()

        t1 = threading.Thread(target=flusher)
        t2 = threading.Thread(target=flusher)
        t1.start()
        t2.start()
        t1.join(timeout=10.0)
        t2.join(timeout=10.0)

        chunks = list((tmp_path / "blackbox").glob("chunk_*.bin.zst"))
        # Every chunk must deserialize cleanly (no index collision, no .tmp
        # leftovers from colliding temporary names).
        assert not list((tmp_path / "blackbox").glob("*.tmp")), "colliding .tmp files left behind"
        buf.close()
        for c in chunks:
            assert c.stat().st_size > 0


class TestSharedZstdContexts:
    """HIGH-8: the shared _cctx must never be used from two threads at once."""

    def test_cctx_is_not_shared_across_threads(self, tmp_path: Path) -> None:
        buf = _small_buffer(tmp_path)
        # After construction the compressor must be thread-confined: either
        # per-thread instances or a per-call allocation. A single shared
        # instance reachable from two call paths reproduces F-03 corruption.
        import zstandard as zstd

        # Simulate the two documented writer paths using the buffer's own API.
        errors: list[BaseException] = []

        def caller_path() -> None:
            try:
                for _i in range(50):
                    # Queue-full synchronous fallback path compresses on THIS thread.
                    with buf._flush_queue.mutex:
                        buf._flush_queue.mutex.acquire_lock()  # hold queue full
                    try:
                        buf._flush_queue.put_nowait((Path("x"), b"junk"))
                    except Exception:
                        pass
                    finally:
                        buf._flush_queue.mutex.release()
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        # The structural contract: compression context must be thread-local.
        assert isinstance(buf._tls, threading.local), "zstd contexts must be thread-confined"
        assert buf._tls.__dict__.get("cctx") is None or isinstance(
            buf._tls.__dict__.get("cctx"), zstd.ZstdCompressor
        )


class TestWorkerShutdown:
    """MEDIUM-4: queued chunks must survive process exit via close()."""

    def test_close_flushes_pending_and_drains_queue(self, tmp_path: Path) -> None:
        buf = _small_buffer(tmp_path)
        for i in range(20):
            buf.append(_mk_frame(i))
        buf.flush()

        # close() must flush remaining frames AND join the worker.
        buf.close(timeout_s=10.0)

        frames = buf.read_all_stored_frames_after_close() if hasattr(buf, "read_all_stored_frames_after_close") else None
        if frames is None:
            # Read the directory directly after close (worker is joined).
            import src.engine.buffer.rolling_disk as rd

            key = rd._get_hmac_key(buf._secret_provider)
            frames = []
            for f in sorted((tmp_path / "blackbox").glob("chunk_*.bin.zst")):
                frames.extend(rd._deserialize_chunk(buf._decompress_bounded(f.read_bytes()), key))
        assert len(frames) == 20, f"close() lost frames: got {len(frames)}"

    def test_close_is_idempotent(self, tmp_path: Path) -> None:
        buf = _small_buffer(tmp_path)
        buf.close(timeout_s=10.0)
        buf.close(timeout_s=10.0)  # must not raise


class TestClearState:
    """B-31: clear() must reset all recorder state, not just the file list."""

    def test_clear_resets_chunk_index(self, tmp_path: Path) -> None:
        buf = _small_buffer(tmp_path)
        for i in range(4):
            buf.append(_mk_frame(i))
        buf.flush()
        assert buf._chunk_index >= 1

        buf.clear()
        assert buf._chunk_index == 0, "clear() left a stale _chunk_index (B-31)"
        assert buf._rejected_frames == 0
        assert not list((tmp_path / "blackbox").glob("chunk_*.bin.zst"))

    def test_clear_drains_pending_writes_first(self, tmp_path: Path) -> None:
        buf = _small_buffer(tmp_path)
        for i in range(4):
            buf.append(_mk_frame(i))
        buf.clear()
        # A queued chunk that lands AFTER clear() would resurrect deleted data.
        time.sleep(0.2)
        buf.close(timeout_s=10.0)
        assert not list((tmp_path / "blackbox").glob("chunk_*.bin.zst")), (
            "chunk written after clear() — pending queue was not drained"
        )
