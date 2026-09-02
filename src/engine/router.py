"""High-Performance Multiplexed CAN Frame Router and Dispatcher.

Implements the Observer / Pub-Sub pattern to distribute incoming CAN frames
to multiple protocol engines (UDS, J1939, NMEA2000, DBC decoders, and UI)
without single-consumer starvation or frame stealing.
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

from src.core.logging import get_logger
from src.core.models.can_frame import CanFrame

logger = get_logger("engine.router")


@dataclass(slots=True)
class Subscription:
    """Active subscriber registration handle."""

    sub_id: int
    callback: Callable[[CanFrame], None] | None = None
    frame_queue: queue.Queue[CanFrame] | None = None
    filter_ids: set[int] | None = None  # None = accept all arbitration IDs
    channel_id: str | None = None  # None = accept all channels


class FrameRouter:
    """Centralized thread-safe message router and dispatcher for CAN bus streams."""

    MAX_QUEUE_SIZE: ClassVar[int] = 10_000

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscriptions: dict[int, Subscription] = {}
        self._next_sub_id: int = 1
        self._total_routed: int = 0
        self._total_dropped: int = 0

    def subscribe(
        self,
        callback: Callable[[CanFrame], None] | None = None,
        filter_ids: set[int] | None = None,
        channel_id: str | None = None,
        use_queue: bool = False,
        queue_maxsize: int = MAX_QUEUE_SIZE,
    ) -> tuple[int, queue.Queue[CanFrame] | None]:
        """Register a new consumer subscription.

        Returns (subscription_id, queue_instance_or_None).
        """
        fq: queue.Queue[CanFrame] | None = None
        if use_queue:
            fq = queue.Queue(maxsize=queue_maxsize)

        with self._lock:
            sub_id = self._next_sub_id
            self._next_sub_id += 1
            sub = Subscription(
                sub_id=sub_id,
                callback=callback,
                frame_queue=fq,
                filter_ids=set(filter_ids) if filter_ids is not None else None,
                channel_id=channel_id,
            )
            self._subscriptions[sub_id] = sub

        return sub_id, fq

    def unsubscribe(self, sub_id: int) -> bool:
        """Remove an existing subscription by ID."""
        with self._lock:
            return self._subscriptions.pop(sub_id, None) is not None

    def route_frame(self, frame: CanFrame) -> int:
        """Dispatch an ingested frame to all matching subscribers.

        Returns the number of subscribers that accepted the frame.
        """
        with self._lock:
            subscribers = list(self._subscriptions.values())
            self._total_routed += 1

        matched_count = 0
        for sub in subscribers:
            # Check channel filter
            if sub.channel_id is not None and frame.channel_id != sub.channel_id:
                continue

            # Check arbitration ID filter
            if sub.filter_ids is not None and frame.arbitration_id not in sub.filter_ids:
                continue

            matched_count += 1

            # Dispatch to callback
            if sub.callback is not None:
                try:
                    sub.callback(frame)
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "Error in FrameRouter subscriber callback",
                        extra={"sub_id": sub.sub_id, "error": str(exc)},
                    )

            # Dispatch to queue (non-blocking with drop on full)
            if sub.frame_queue is not None:
                try:
                    sub.frame_queue.put_nowait(frame)
                except queue.Full:
                    with self._lock:
                        self._total_dropped += 1
                    logger.warning(
                        "FrameRouter subscriber queue full, dropping frame",
                        extra={"sub_id": sub.sub_id, "arbitration_id": hex(frame.arbitration_id)},
                    )

        return matched_count

    def clear(self) -> None:
        """Remove all active subscriptions."""
        with self._lock:
            self._subscriptions.clear()

    @property
    def subscription_count(self) -> int:
        with self._lock:
            return len(self._subscriptions)

    @property
    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "active_subscriptions": len(self._subscriptions),
                "total_routed": self._total_routed,
                "total_dropped": self._total_dropped,
            }
