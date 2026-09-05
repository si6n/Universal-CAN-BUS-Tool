"""Active Diagnostic Poller & Multi-Rate Scheduler Engine.

Provides deterministic, thread-safe, and asynchronous polling for SAE J1979 OBD-II Mode 01
PIDs and ISO 14229 UDS DIDs (Service 0x22) over CAN and ISO-TP.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.core.contracts.ports import ClockProvider, RxSubscription, SystemClockProvider, TxPort
from src.core.errors import ProtocolError
from src.core.logging import get_logger
from src.core.models.can_frame import CanFrame
from src.protocols.obd.models import ObdPidResult, UdsDidResult
from src.protocols.obd.pids import OBD_PID_REGISTRY, ObdPidRegistry
from src.protocols.uds.did_database import UDS_DID_REGISTRY, UdsDidRegistry
from src.protocols.uds.isotp import IsoTpTransport
from src.protocols.uds.nrc import UdsNrc

logger = get_logger("protocols.obd.poller")

# Timing Constants (ISO 14229 / SAE J1979)
DEFAULT_P2_TIMEOUT_S: float = 2.0
P2_STAR_TIMEOUT_S: float = 5.0
DEFAULT_MAX_RATE_HZ: float = 40.0
DEFAULT_MAX_RETRIES: int = 3
BASE_BACKOFF_S: float = 0.050


class PollerState(str, Enum):
    """Diagnostic transaction finite state machine states."""

    IDLE = "IDLE"
    ENQUEUED = "ENQUEUED"
    ISO_TP_TRANSMIT = "ISO_TP_TRANSMIT"
    WAITING_FOR_RESPONSE = "WAITING_FOR_RESPONSE"
    WAITING_P2_STAR = "WAITING_P2_STAR"
    PROCESSING_PAYLOAD = "PROCESSING_PAYLOAD"
    RETRY_BACKOFF = "RETRY_BACKOFF"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(slots=True)
class PollerJob:
    """Registered diagnostic polling job descriptor."""

    kind: str  # "obd_pid" | "uds_did"
    identifier: int  # PID (0x00..0xFF) or DID (0x0000..0xFFFF)
    rate_hz: float  # Polling rate in Hertz
    callback: Callable[[Any], None]
    priority: int = 5  # Higher number = higher execution priority (1..10)
    tx_id: int = 0x7DF
    rx_id: int = 0x7E8
    next_run_s: float = 0.0
    last_run_s: float = 0.0
    consecutive_failures: int = 0
    state: PollerState = PollerState.IDLE
    retry_count: int = 0
    response_deadline_s: float = 0.0

    @property
    def interval_s(self) -> float:
        """Sampling interval in fractional seconds."""
        return 1.0 / self.rate_hz if self.rate_hz > 0 else 1.0

    # P-e: the priority-heap __lt__ was removed — scheduling uses an explicit
    # sort key (priority, next_run_s) in step(), no heap ordering remains.


class ActiveDiagnosticPoller:
    """Multi-Rate Diagnostic Poller Scheduler & Request/Response State Machine.

    Schedules periodic OBD-II and UDS queries across Fast (50Hz), Medium (10Hz),
    and Slow (1Hz) telemetry bands while routing frames strictly through TxPort.
    """

    def __init__(
        self,
        tx_port: TxPort,
        rx_subscription: RxSubscription | None = None,
        isotp_transport: IsoTpTransport | None = None,
        clock_provider: ClockProvider | None = None,
        channel_id: str = "obd_ch0",
        tx_id: int = 0x7DF,
        rx_id: int = 0x7E8,
        max_rate_hz: float = DEFAULT_MAX_RATE_HZ,
        obd_registry: ObdPidRegistry | None = None,
        uds_registry: UdsDidRegistry | None = None,
    ) -> None:
        self.tx_port = tx_port
        self.rx_subscription = rx_subscription
        self.channel_id = channel_id
        self.default_tx_id = tx_id
        self.default_rx_id = rx_id
        self.max_rate_hz = max(1.0, max_rate_hz)
        self.min_tx_interval_s = 1.0 / self.max_rate_hz

        self.clock: ClockProvider = clock_provider or SystemClockProvider()
        self.obd_registry: ObdPidRegistry = obd_registry or OBD_PID_REGISTRY
        self.uds_registry: UdsDidRegistry = uds_registry or UDS_DID_REGISTRY

        self.isotp = isotp_transport or IsoTpTransport(
            tx_id=tx_id,
            rx_id=rx_id,
            channel_id=channel_id,
        )

        self._lock = threading.Lock()
        self._jobs: dict[tuple[str, int], PollerJob] = {}
        self._last_tx_time_s: float = 0.0

        # State tracking for active transaction
        self._active_job: PollerJob | None = None
        self._state: PollerState = PollerState.IDLE

        # Background async task management
        self._running: bool = False
        self._loop_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    @property
    def is_running(self) -> bool:
        """Return True if background async polling loop is active."""
        return self._running

    @property
    def current_state(self) -> PollerState:
        """Return the current diagnostic state machine state."""
        return self._state

    def register_pid(
        self,
        pid: int,
        rate_hz: float,
        callback: Callable[[ObdPidResult], None],
        priority: int = 5,
        tx_id: int | None = None,
        rx_id: int | None = None,
    ) -> None:
        """Register a periodic OBD-II Mode 01 PID polling job."""
        with self._lock:
            key = ("obd_pid", pid)
            now = self.clock.now_monotonic()
            job = PollerJob(
                kind="obd_pid",
                identifier=pid,
                rate_hz=rate_hz,
                callback=callback,
                priority=priority,
                tx_id=tx_id if tx_id is not None else self.default_tx_id,
                rx_id=rx_id if rx_id is not None else self.default_rx_id,
                next_run_s=now,
                state=PollerState.IDLE,
            )
            self._jobs[key] = job
            logger.info("Registered OBD PID job", extra={"pid": hex(pid), "rate_hz": rate_hz})

    def register_did(
        self,
        did: int,
        rate_hz: float,
        callback: Callable[[UdsDidResult], None],
        priority: int = 5,
        tx_id: int | None = None,
        rx_id: int | None = None,
    ) -> None:
        """Register a periodic ISO 14229 UDS DID (Service 0x22) polling job."""
        with self._lock:
            key = ("uds_did", did)
            now = self.clock.now_monotonic()
            job = PollerJob(
                kind="uds_did",
                identifier=did,
                rate_hz=rate_hz,
                callback=callback,
                priority=priority,
                tx_id=tx_id if tx_id is not None else 0x7E0,  # Default physical UDS request
                rx_id=rx_id if rx_id is not None else self.default_rx_id,
                next_run_s=now,
                state=PollerState.IDLE,
            )
            self._jobs[key] = job
            logger.info("Registered UDS DID job", extra={"did": hex(did), "rate_hz": rate_hz})

    def unregister_pid(self, pid: int) -> bool:
        """Unregister an OBD-II PID job. Returns True if job was found and removed."""
        with self._lock:
            key = ("obd_pid", pid)
            if key in self._jobs:
                del self._jobs[key]
                return True
            return False

    def unregister_did(self, did: int) -> bool:
        """Unregister a UDS DID job. Returns True if job was found and removed."""
        with self._lock:
            key = ("uds_did", did)
            if key in self._jobs:
                del self._jobs[key]
                return True
            return False

    def get_registered_jobs(self) -> list[PollerJob]:
        """Return list of all currently registered polling jobs."""
        with self._lock:
            return list(self._jobs.values())

    def build_request_frame(self, job: PollerJob) -> CanFrame:
        """Construct standard CAN request frame for an OBD PID or UDS DID job."""
        if job.kind == "obd_pid":
            # SAE J1979 Mode 01 Request: [0x02, 0x01, PID, 0x55, 0x55, 0x55, 0x55, 0x55]
            payload = bytes([0x02, 0x01, job.identifier & 0xFF, 0x55, 0x55, 0x55, 0x55, 0x55])
            return CanFrame.create(
                channel_id=self.channel_id,
                arbitration_id=job.tx_id,
                data=payload,
                is_extended=job.tx_id > 0x7FF,
                direction="tx",
            )
        elif job.kind == "uds_did":
            # ISO 14229 Service 0x22 (ReadDataByIdentifier): [0x03, 0x22, DID_HI, DID_LO, 0x55, 0x55, 0x55, 0x55]
            did = job.identifier
            payload = bytes([0x03, 0x22, (did >> 8) & 0xFF, did & 0xFF, 0x55, 0x55, 0x55, 0x55])
            return CanFrame.create(
                channel_id=self.channel_id,
                arbitration_id=job.tx_id,
                data=payload,
                is_extended=job.tx_id > 0x7FF,
                direction="tx",
            )
        else:
            raise ValueError(f"Unknown job kind: {job.kind}")

    def process_rx_frame(
        self, frame: CanFrame
    ) -> tuple[ObdPidResult | UdsDidResult | None, CanFrame | None]:
        """Process incoming CAN frame against the active job or registered listeners.

        Returns: (DecodedResult, OptionalFlowControlFrame)
        """
        with self._lock:
            active = self._active_job

        # Filter by channel if applicable
        if frame.channel_id != self.channel_id and self.channel_id:
            return None, None

        # Reassemble using IsoTpTransport
        completed_payload, fc_frame = self.isotp.handle_rx_frame(frame)

        if completed_payload is None:
            return None, fc_frame

        # We have a reassembled diagnostic payload
        decoded_result: ObdPidResult | UdsDidResult | None = None
        now = self.clock.now_monotonic()

        if len(completed_payload) < 2:
            return None, fc_frame

        sid = completed_payload[0]
        cb_to_dispatch = None

        with self._lock:
            active = self._active_job

            # --------------------------------------------------------------------
            # 1. Negative Response Handling (SID 0x7F)
            # --------------------------------------------------------------------
            if sid == 0x7F and len(completed_payload) >= 3:
                nrc = completed_payload[2]

                if nrc == UdsNrc.REQUEST_CORRECTLY_RECEIVED_RESPONSE_PENDING:  # NRC 0x78
                    if active is not None:
                        active.state = PollerState.WAITING_P2_STAR
                        active.response_deadline_s = now + P2_STAR_TIMEOUT_S
                        self._state = PollerState.WAITING_P2_STAR
                        logger.info("Received NRC 0x78 (Response Pending) — extended P2* armed")
                    return None, fc_frame

                elif nrc == UdsNrc.BUSY_REPEAT_REQUEST:  # NRC 0x21
                    if active is not None:
                        active.state = PollerState.RETRY_BACKOFF
                        self._schedule_retry(active, now)
                    return None, fc_frame

                else:
                    # Other Negative Response
                    if active is not None:
                        active.state = PollerState.FAILED
                        active.consecutive_failures += 1
                        self._state = PollerState.FAILED
                    return None, fc_frame

            # --------------------------------------------------------------------
            # 2. Positive OBD Mode 01 Response (SID 0x41)
            # --------------------------------------------------------------------
            if sid == 0x41:
                pid = completed_payload[1]
                raw_data = completed_payload[2:]
                result = self.obd_registry.decode(pid, raw_data)
                decoded_result = result

                if active is not None and active.kind == "obd_pid" and active.identifier == pid:
                    active.state = PollerState.COMPLETED
                    active.consecutive_failures = 0
                    active.retry_count = 0
                    self._state = PollerState.COMPLETED
                    self._active_job = None
                    cb_to_dispatch = (active.callback, result)

            # --------------------------------------------------------------------
            # 3. Positive UDS Service 0x22 Response (SID 0x62)
            # --------------------------------------------------------------------
            elif sid == 0x62 and len(completed_payload) >= 3:
                did = (completed_payload[1] << 8) | completed_payload[2]
                raw_data = completed_payload[3:]
                result = self.uds_registry.decode(did, raw_data)
                decoded_result = result

                if active is not None and active.kind == "uds_did" and active.identifier == did:
                    active.state = PollerState.COMPLETED
                    active.consecutive_failures = 0
                    active.retry_count = 0
                    self._state = PollerState.COMPLETED
                    self._active_job = None
                    cb_to_dispatch = (active.callback, result)

        if cb_to_dispatch is not None:
            cb, res = cb_to_dispatch
            try:
                cb(res)
            except Exception as cb_err:
                logger.error("Error in poller callback", extra={"error": str(cb_err)})

        return decoded_result, fc_frame

    def _schedule_retry(self, job: PollerJob, now: float) -> None:
        """Schedule exponential backoff retry for a failed or busy job."""
        job.retry_count += 1
        if job.retry_count > DEFAULT_MAX_RETRIES:
            job.state = PollerState.FAILED
            job.consecutive_failures += 1
            job.next_run_s = now + job.interval_s
            self._state = PollerState.FAILED
            self._active_job = None
        else:
            backoff_delay = BASE_BACKOFF_S * (2 ** (job.retry_count - 1))
            job.next_run_s = now + backoff_delay
            job.state = PollerState.RETRY_BACKOFF
            self._state = PollerState.RETRY_BACKOFF
            # Release the active slot: while parked in backoff the job is not
            # "awaiting a response", and step() must be free to reselect it
            # (with a fresh response deadline) once the backoff elapses.
            self._active_job = None

    def step(self, current_time: float | None = None) -> PollerJob | None:
        """Perform a single deterministic scheduling and execution step.

        Selects the highest priority due job, enforces rate limits, constructs
        the request frame, and sends it synchronously/asynchronously via TxPort.
        """
        now = current_time if current_time is not None else self.clock.now_monotonic()

        with self._lock:
            # Check timeout on current active job
            if self._active_job is not None:
                if now >= self._active_job.response_deadline_s:
                    logger.warning("Diagnostic request timed out", extra={"id": hex(self._active_job.identifier)})
                    self._schedule_retry(self._active_job, now)

            # Check rate limiter
            if (now - self._last_tx_time_s) < self.min_tx_interval_s:
                return None

            # Find candidate jobs that are due
            due_jobs: list[PollerJob] = [
                j for j in self._jobs.values() if j.next_run_s <= now and j != self._active_job
            ]

            if not due_jobs:
                return None

            # Sort by priority descending, then next_run_s ascending
            due_jobs.sort(key=lambda j: (-j.priority, j.next_run_s))
            selected_job = due_jobs[0]

            self._active_job = selected_job
            selected_job.state = PollerState.ENQUEUED
            selected_job.last_run_s = now
            selected_job.next_run_s = now + selected_job.interval_s
            selected_job.response_deadline_s = now + DEFAULT_P2_TIMEOUT_S
            self._state = PollerState.ENQUEUED
            self._last_tx_time_s = now

        # Transmit request frame
        req_frame = self.build_request_frame(selected_job)
        selected_job.state = PollerState.ISO_TP_TRANSMIT
        self._state = PollerState.WAITING_FOR_RESPONSE

        # Send via TxPort
        try:
            self.tx_port.send_sync(req_frame)
        except Exception as exc:
            logger.error("Failed to send diagnostic frame", extra={"error": str(exc)})
            selected_job.state = PollerState.FAILED
            self._state = PollerState.FAILED
            self._active_job = None
            return selected_job

        selected_job.state = PollerState.WAITING_FOR_RESPONSE
        return selected_job

    async def poll_pid_once(
        self,
        pid: int,
        tx_id: int | None = None,
        rx_id: int | None = None,
        timeout_s: float = DEFAULT_P2_TIMEOUT_S,
    ) -> ObdPidResult:
        """Perform a one-shot asynchronous query for an OBD-II Mode 01 PID."""
        target_tx_id = tx_id if tx_id is not None else self.default_tx_id
        target_rx_id = rx_id if rx_id is not None else self.default_rx_id

        payload = bytes([0x02, 0x01, pid & 0xFF, 0x55, 0x55, 0x55, 0x55, 0x55])
        req_frame = CanFrame.create(
            channel_id=self.channel_id,
            arbitration_id=target_tx_id,
            data=payload,
            is_extended=target_tx_id > 0x7FF,
            direction="tx",
        )

        await self.tx_port.send(req_frame)

        if self.rx_subscription is None:
            raise ProtocolError(
                "RxSubscription is required for asynchronous one-shot diagnostic queries",
                code="OBD_NO_SUBSCRIPTION",
                details={"protocol": "OBD"},
            )

        start_time = self.clock.now_monotonic()
        deadline = start_time + timeout_s

        while self.clock.now_monotonic() < deadline:
            remaining = deadline - self.clock.now_monotonic()
            if remaining <= 0:
                break
            frame = await self.rx_subscription.recv(timeout_s=remaining)
            if frame is None:
                break

            if frame.arbitration_id != target_rx_id or len(frame.data) < 3:
                continue

            # Process payload
            completed, fc = self.isotp.handle_rx_frame(frame)
            if fc is not None:
                await self.tx_port.send(fc)

            if completed is not None:
                if completed[0] == 0x41 and completed[1] == pid:
                    return self.obd_registry.decode(pid, completed[2:])
                elif completed[0] == 0x7F and completed[1] == 0x01:
                    nrc = completed[2]
                    if nrc == UdsNrc.REQUEST_CORRECTLY_RECEIVED_RESPONSE_PENDING:
                        deadline = self.clock.now_monotonic() + P2_STAR_TIMEOUT_S
                        continue
                    raise ProtocolError(
                        f"OBD PID 0x{pid:02X} rejected with NRC 0x{nrc:02X}",
                        code="OBD_NEGATIVE_RESPONSE",
                        details={"pid": pid, "nrc": nrc},
                    )

        raise TimeoutError(f"Timeout ({timeout_s}s) waiting for response to OBD PID 0x{pid:02X}")

    async def poll_did_once(
        self,
        did: int,
        tx_id: int | None = None,
        rx_id: int | None = None,
        timeout_s: float = DEFAULT_P2_TIMEOUT_S,
    ) -> UdsDidResult:
        """Perform a one-shot asynchronous query for an ISO 14229 UDS DID."""
        target_tx_id = tx_id if tx_id is not None else 0x7E0
        target_rx_id = rx_id if rx_id is not None else self.default_rx_id

        payload = bytes([0x03, 0x22, (did >> 8) & 0xFF, did & 0xFF, 0x55, 0x55, 0x55, 0x55])
        req_frame = CanFrame.create(
            channel_id=self.channel_id,
            arbitration_id=target_tx_id,
            data=payload,
            is_extended=target_tx_id > 0x7FF,
            direction="tx",
        )

        await self.tx_port.send(req_frame)

        if self.rx_subscription is None:
            raise ProtocolError(
                "RxSubscription is required for asynchronous one-shot diagnostic queries",
                code="UDS_NO_SUBSCRIPTION",
                details={"protocol": "UDS"},
            )

        start_time = self.clock.now_monotonic()
        deadline = start_time + timeout_s

        while self.clock.now_monotonic() < deadline:
            remaining = deadline - self.clock.now_monotonic()
            if remaining <= 0:
                break
            frame = await self.rx_subscription.recv(timeout_s=remaining)
            if frame is None:
                break

            if frame.arbitration_id != target_rx_id or len(frame.data) < 3:
                continue

            # Process payload
            completed, fc = self.isotp.handle_rx_frame(frame)
            if fc is not None:
                await self.tx_port.send(fc)

            if completed is not None:
                if completed[0] == 0x62 and len(completed) >= 3:
                    resp_did = (completed[1] << 8) | completed[2]
                    if resp_did == did:
                        return self.uds_registry.decode(did, completed[3:])
                elif completed[0] == 0x7F and completed[1] == 0x22:
                    nrc = completed[2]
                    if nrc == UdsNrc.REQUEST_CORRECTLY_RECEIVED_RESPONSE_PENDING:
                        deadline = self.clock.now_monotonic() + P2_STAR_TIMEOUT_S
                        continue
                    raise ProtocolError(
                        f"UDS DID 0x{did:04X} rejected with NRC 0x{nrc:02X}",
                        code="UDS_NEGATIVE_RESPONSE",
                        details={"did": did, "nrc": nrc},
                    )

        raise TimeoutError(f"Timeout ({timeout_s}s) waiting for response to UDS DID 0x{did:04X}")

    async def _async_polling_loop(self) -> None:
        """Internal asynchronous worker loop running periodic polling steps."""
        while self._running:
            self.step()

            # If an Rx subscription is available, check for incoming frames
            if self.rx_subscription is not None:
                try:
                    frame = await self.rx_subscription.recv(timeout_s=0.005)
                    if frame is not None:
                        result, fc = self.process_rx_frame(frame)
                        if fc is not None:
                            await self.tx_port.send(fc)
                except Exception as rx_err:
                    logger.warning("Error receiving frame in poller loop", extra={"error": str(rx_err)})

            await asyncio.sleep(min(0.010, self.min_tx_interval_s))

    def start(self) -> None:
        """Start the active diagnostic poller background async task."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        try:
            loop = asyncio.get_running_loop()
            self._loop_task = loop.create_task(self._async_polling_loop())
        except RuntimeError:
            # No running event loop in current thread
            pass

    def stop(self) -> None:
        """Stop the active diagnostic poller background task."""
        self._running = False
        self._stop_event.set()
        if self._loop_task is not None:
            self._loop_task.cancel()
            self._loop_task = None
