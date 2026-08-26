"""Rolling Compressed Disk Buffer for Telemetry Blackbox Recording.

Writes 5 MB compressed zstandard chunks with strict max retention (10 mins / 100 MB).
Matches MASTER_PLAN.md Section 10 & 19.2 (Task 1.1).
"""

from __future__ import annotations

import pickle
import time
from pathlib import Path
from typing import ClassVar

import zstandard as zstd

from src.core.logging import get_logger
from src.core.models.can_frame import CanFrame

logger = get_logger("engine.buffer.disk")


class RollingDiskBuffer:
    """Rolling compressed chunk buffer with time and storage bounds."""

    CHUNK_THRESHOLD_FRAMES: ClassVar[int] = 25_000  # ~2-3 MB uncompressed
    MAX_RETENTION_SEC: ClassVar[int] = 600  # 10 minutes
    MAX_DISK_BYTES: ClassVar[int] = 100 * 1024 * 1024  # 100 MB

    def __init__(
        self,
        storage_dir: str | Path,
        max_retention_sec: int = MAX_RETENTION_SEC,
        max_disk_bytes: int = MAX_DISK_BYTES,
        chunk_frame_threshold: int = CHUNK_THRESHOLD_FRAMES,
    ) -> None:
        self.storage_dir = Path(storage_dir)
        self.max_retention_sec = max_retention_sec
        self.max_disk_bytes = max_disk_bytes
        self.chunk_frame_threshold = chunk_frame_threshold

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._current_chunk_frames: list[CanFrame] = []
        self._cctx = zstd.ZstdCompressor(level=3)
        self._dctx = zstd.ZstdDecompressor()
        self._chunk_index = 0

    def append(self, frame: CanFrame) -> None:
        """Add frame to current pending chunk. Flushes to disk if threshold reached."""
        self._current_chunk_frames.append(frame)
        if len(self._current_chunk_frames) >= self.chunk_frame_threshold:
            self.flush()

    def flush(self) -> Path | None:
        """Compress and write current pending chunk to disk."""
        if not self._current_chunk_frames:
            return None

        ts_ns = self._current_chunk_frames[0].timestamp_ns
        # Zero-padded index and timestamp ensures perfect alphabetical sorting
        chunk_file = self.storage_dir / f"chunk_{self._chunk_index:08d}_{ts_ns:020d}.bin.zst"

        # Serialize frames and compress
        raw_bytes = pickle.dumps(self._current_chunk_frames)
        compressed_bytes = self._cctx.compress(raw_bytes)

        with open(chunk_file, "wb") as f:
            f.write(compressed_bytes)

        logger.debug(
            "Flushed rolling disk chunk",
            extra={
                "file": chunk_file.name,
                "frames": len(self._current_chunk_frames),
                "uncompressed_kb": len(raw_bytes) // 1024,
                "compressed_kb": len(compressed_bytes) // 1024,
            },
        )

        self._current_chunk_frames = []
        self._chunk_index += 1

        # Enforce retention policy
        self._enforce_retention()
        return chunk_file

    def _enforce_retention(self) -> None:
        """Purge chunks exceeding max time retention or total disk byte budget."""
        now = time.time()
        cutoff_time = now - self.max_retention_sec

        chunk_files = sorted(self.storage_dir.glob("chunk_*.bin.zst"))
        total_bytes = 0

        # Pass 1: Remove expired chunks based on file modification time
        valid_files: list[Path] = []
        for file in chunk_files:
            try:
                mtime = file.stat().st_mtime
                if mtime < cutoff_time:
                    file.unlink(missing_ok=True)
                else:
                    valid_files.append(file)
                    total_bytes += file.stat().st_size
            except OSError:
                continue

        # Pass 2: If total disk bytes exceed limit, remove oldest chunks
        while total_bytes > self.max_disk_bytes and valid_files:
            oldest = valid_files.pop(0)
            try:
                size = oldest.stat().st_size
                oldest.unlink(missing_ok=True)
                total_bytes -= size
            except OSError:
                continue

    def read_all_stored_frames(self) -> list[CanFrame]:
        """Read and decompress all stored chunks in chronological order."""
        self.flush()  # Ensure pending frames are on disk

        chunk_files = sorted(self.storage_dir.glob("chunk_*.bin.zst"))
        all_frames: list[CanFrame] = []

        for file in chunk_files:
            try:
                with open(file, "rb") as f:
                    compressed_bytes = f.read()
                raw_bytes = self._dctx.decompress(compressed_bytes)
                frames: list[CanFrame] = pickle.loads(raw_bytes)
                all_frames.extend(frames)
            except (zstd.ZstdError, pickle.PickleError, OSError) as exc:
                logger.error("Failed to read chunk file", extra={"file": str(file), "error": str(exc)})
                continue

        return all_frames

    def clear(self) -> None:
        """Delete all chunk files in storage directory."""
        self._current_chunk_frames = []
        for file in self.storage_dir.glob("chunk_*.bin.zst"):
            file.unlink(missing_ok=True)
