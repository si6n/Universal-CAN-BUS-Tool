"""Unit Test Suite for ActiveDiagnosticPoller Multi-Rate Scheduler & State Machine."""

from __future__ import annotations

import pytest

from src.core.contracts.ports import InMemoryTxPort, QueueRxSubscription
from src.core.errors import ProtocolError
from src.core.models.can_frame import CanFrame
from src.protocols.obd.models import ObdPidResult, UdsDidResult
from src.protocols.obd.poller import (
    ActiveDiagnosticPoller,
    PollerJob,
    PollerState,
)


class FakeClock:
    """Controllable monotonic clock for deterministic scheduler testing."""

    def __init__(self, start_time: float = 100.0) -> None:
        self._time = start_time

    def now_monotonic(self) -> float:
        return self._time

    def now_monotonic_ns(self) -> int:
        return int(self._time * 1_000_000_000)

    def advance(self, seconds: float) -> None:
        self._time += seconds


def test_poller_registration_lifecycle() -> None:
    """Test registering, querying, and unregistering OBD PIDs and UDS DIDs."""
    tx_port = InMemoryTxPort()
    poller = ActiveDiagnosticPoller(tx_port=tx_port)

    pid_results = []
    did_results = []

    poller.register_pid(0x0C, rate_hz=10.0, callback=lambda r: pid_results.append(r), priority=8)
    poller.register_did(0xF190, rate_hz=1.0, callback=lambda r: did_results.append(r), priority=2)

    jobs = poller.get_registered_jobs()
    assert len(jobs) == 2

    # Verify unregister
    assert poller.unregister_pid(0x0C) is True
    assert poller.unregister_pid(0x0C) is False
    assert len(poller.get_registered_jobs()) == 1

    assert poller.unregister_did(0xF190) is True
    assert len(poller.get_registered_jobs()) == 0


def test_poller_build_request_frames() -> None:
    """Test standard ISO-TP / CAN request frame construction."""
    tx_port = InMemoryTxPort()
    poller = ActiveDiagnosticPoller(tx_port=tx_port, tx_id=0x7DF, rx_id=0x7E8)

    # OBD PID 0x0C (Engine RPM)
    job_rpm = PollerJob(
        kind="obd_pid",
        identifier=0x0C,
        rate_hz=10.0,
        callback=lambda r: None,
        tx_id=0x7DF,
        rx_id=0x7E8,
    )
    frame_rpm = poller.build_request_frame(job_rpm)
    assert frame_rpm.arbitration_id == 0x7DF
    assert frame_rpm.data[:3] == bytes([0x02, 0x01, 0x0C])

    # UDS DID 0xF190 (VIN)
    job_vin = PollerJob(
        kind="uds_did",
        identifier=0xF190,
        rate_hz=1.0,
        callback=lambda r: None,
        tx_id=0x7E0,
        rx_id=0x7E8,
    )
    frame_vin = poller.build_request_frame(job_vin)
    assert frame_vin.arbitration_id == 0x7E0
    assert frame_vin.data[:4] == bytes([0x03, 0x22, 0xF1, 0x90])


def test_poller_priority_scheduler_step() -> None:
    """Test deterministic priority queue dispatch and rate limiting."""
    tx_port = InMemoryTxPort()
    clock = FakeClock(start_time=1000.0)
    poller = ActiveDiagnosticPoller(tx_port=tx_port, clock_provider=clock, max_rate_hz=50.0)

    # Low priority job (VIN: priority 1) and High priority job (RPM: priority 10)
    poller.register_did(0xF190, rate_hz=1.0, callback=lambda r: None, priority=1)
    poller.register_pid(0x0C, rate_hz=10.0, callback=lambda r: None, priority=10)

    # First step: highest priority (RPM 0x0C) should be dispatched first
    step1_job = poller.step()
    assert step1_job is not None
    assert step1_job.identifier == 0x0C
    assert len(tx_port.sent_frames) == 1
    assert tx_port.sent_frames[0].data[:3] == bytes([0x02, 0x01, 0x0C])

    # Immediate step without advancing clock should be rate-limited (max 50Hz = 20ms)
    step2_job = poller.step()
    assert step2_job is None

    # Advance clock by 25ms -> Low priority VIN job should now dispatch
    clock.advance(0.025)
    step3_job = poller.step()
    assert step3_job is not None
    assert step3_job.identifier == 0xF190
    assert len(tx_port.sent_frames) == 2


def test_poller_obd_response_processing_and_callback() -> None:
    """Test feeding positive OBD-II Single Frame response and callback execution."""
    tx_port = InMemoryTxPort()
    poller = ActiveDiagnosticPoller(tx_port=tx_port)

    received_results: list[ObdPidResult] = []
    poller.register_pid(0x0C, rate_hz=10.0, callback=lambda r: received_results.append(r))

    # Dispatch request
    job = poller.step()
    assert job is not None
    assert poller.current_state == PollerState.WAITING_FOR_RESPONSE

    # Simulate ECU response: Single Frame (PCI 0x04), SID 0x41, PID 0x0C, Data [0x1F, 0x40] (2000 rpm)
    resp_frame = CanFrame.create(
        channel_id="obd_ch0",
        arbitration_id=0x7E8,
        data=bytes([0x04, 0x41, 0x0C, 0x1F, 0x40, 0xAA, 0xAA, 0xAA]),
        direction="rx",
    )

    result, fc = poller.process_rx_frame(resp_frame)
    assert fc is None
    assert result is not None
    assert isinstance(result, ObdPidResult)
    assert result.pid == 0x0C
    assert result.value == 2000.0
    assert poller.current_state == PollerState.COMPLETED

    assert len(received_results) == 1
    assert received_results[0].value == 2000.0


def test_poller_uds_did_response_processing() -> None:
    """Test feeding positive UDS Service 0x22 response for Battery Voltage (DID 0x0100)."""
    tx_port = InMemoryTxPort()
    poller = ActiveDiagnosticPoller(tx_port=tx_port)

    did_results: list[UdsDidResult] = []
    poller.register_did(0x0100, rate_hz=5.0, callback=lambda r: did_results.append(r))

    # Dispatch request
    poller.step()

    # Response: Single Frame (PCI 0x05), SID 0x62, DID 0x0100, Data [0x04, 0xE2] (12.50 V)
    resp_frame = CanFrame.create(
        channel_id="obd_ch0",
        arbitration_id=0x7E8,
        data=bytes([0x05, 0x62, 0x01, 0x00, 0x04, 0xE2, 0x55, 0x55]),
        direction="rx",
    )

    result, fc = poller.process_rx_frame(resp_frame)
    assert result is not None
    assert isinstance(result, UdsDidResult)
    assert result.did == 0x0100
    assert result.value == 12.50
    assert len(did_results) == 1


def test_poller_nrc_78_response_pending_arms_p2_star() -> None:
    """Test receiving NRC 0x78 (Response Pending) arms extended P2* window."""
    tx_port = InMemoryTxPort()
    clock = FakeClock(start_time=100.0)
    poller = ActiveDiagnosticPoller(tx_port=tx_port, clock_provider=clock)

    poller.register_did(0xF190, rate_hz=1.0, callback=lambda r: None)
    job = poller.step()
    assert poller.current_state == PollerState.WAITING_FOR_RESPONSE

    # ECU sends Negative Response: NRC 0x78 (Response Pending) for SID 0x22
    nrc_frame = CanFrame.create(
        channel_id="obd_ch0",
        arbitration_id=0x7E8,
        data=bytes([0x03, 0x7F, 0x22, 0x78, 0x55, 0x55, 0x55, 0x55]),
        direction="rx",
    )

    res, fc = poller.process_rx_frame(nrc_frame)
    assert res is None
    assert poller.current_state == PollerState.WAITING_P2_STAR
    assert job.response_deadline_s == 100.0 + 5.0  # Extended P2* window armed (105.0s)


def test_poller_nrc_21_busy_repeat_request_retry_backoff() -> None:
    """Test NRC 0x21 (Busy Repeat Request) triggers exponential backoff."""
    tx_port = InMemoryTxPort()
    clock = FakeClock(start_time=50.0)
    poller = ActiveDiagnosticPoller(tx_port=tx_port, clock_provider=clock)

    poller.register_pid(0x0C, rate_hz=10.0, callback=lambda r: None)
    job = poller.step()

    # ECU sends NRC 0x21 (Busy)
    nrc_busy = CanFrame.create(
        channel_id="obd_ch0",
        arbitration_id=0x7E8,
        data=bytes([0x03, 0x7F, 0x01, 0x21, 0x55, 0x55, 0x55, 0x55]),
        direction="rx",
    )

    poller.process_rx_frame(nrc_busy)
    assert poller.current_state == PollerState.RETRY_BACKOFF
    assert job.retry_count == 1
    assert job.next_run_s > 50.0  # Rescheduled after backoff


@pytest.mark.asyncio
async def test_poller_async_poll_pid_once() -> None:
    """Test asynchronous one-shot query for an OBD PID."""
    tx_port = InMemoryTxPort()
    rx_sub = QueueRxSubscription()
    poller = ActiveDiagnosticPoller(tx_port=tx_port, rx_subscription=rx_sub)

    # Queue response: PID 0x0D (Vehicle Speed 100 km/h)
    resp_frame = CanFrame.create(
        channel_id="obd_ch0",
        arbitration_id=0x7E8,
        data=bytes([0x03, 0x41, 0x0D, 100, 0x55, 0x55, 0x55, 0x55]),
        direction="rx",
    )
    rx_sub.put_nowait(resp_frame)

    result = await poller.poll_pid_once(pid=0x0D, timeout_s=1.0)
    assert result.pid == 0x0D
    assert result.name == "VEHICLE_SPEED"
    assert result.value == 100


@pytest.mark.asyncio
async def test_poller_async_poll_did_once() -> None:
    """Test asynchronous one-shot query for a UDS DID."""
    tx_port = InMemoryTxPort()
    rx_sub = QueueRxSubscription()
    poller = ActiveDiagnosticPoller(tx_port=tx_port, rx_subscription=rx_sub)

    # Queue response: DID 0x0100 (Battery 12.00 V)
    resp_frame = CanFrame.create(
        channel_id="obd_ch0",
        arbitration_id=0x7E8,
        data=bytes([0x05, 0x62, 0x01, 0x00, 0x04, 0xB0, 0x55, 0x55]),  # 1200 = 0x04B0
        direction="rx",
    )
    rx_sub.put_nowait(resp_frame)

    result = await poller.poll_did_once(did=0x0100, timeout_s=1.0)
    assert result.did == 0x0100
    assert result.value == 12.0


@pytest.mark.asyncio
async def test_poller_async_poll_pid_rejected_nrc() -> None:
    """Test ProtocolError raised when PID query is rejected with NRC."""
    tx_port = InMemoryTxPort()
    rx_sub = QueueRxSubscription()
    poller = ActiveDiagnosticPoller(tx_port=tx_port, rx_subscription=rx_sub)

    # Queue NRC 0x12 (Sub-function not supported)
    nrc_frame = CanFrame.create(
        channel_id="obd_ch0",
        arbitration_id=0x7E8,
        data=bytes([0x03, 0x7F, 0x01, 0x12, 0x55, 0x55, 0x55, 0x55]),
        direction="rx",
    )
    rx_sub.put_nowait(nrc_frame)

    with pytest.raises(ProtocolError, match="rejected with NRC 0x12"):
        await poller.poll_pid_once(pid=0x0C, timeout_s=1.0)


@pytest.mark.asyncio
async def test_poller_async_timeout_raises_error() -> None:
    """Test TimeoutError raised when no response arrives within deadline."""
    tx_port = InMemoryTxPort()
    rx_sub = QueueRxSubscription()
    poller = ActiveDiagnosticPoller(tx_port=tx_port, rx_subscription=rx_sub)

    with pytest.raises(TimeoutError, match="Timeout"):
        await poller.poll_pid_once(pid=0x0C, timeout_s=0.05)


def test_poller_start_and_stop_lifecycle() -> None:
    """Test start() and stop() methods safely manage background state."""
    tx_port = InMemoryTxPort()
    poller = ActiveDiagnosticPoller(tx_port=tx_port)

    assert poller.is_running is False
    poller.start()
    assert poller.is_running is True
    poller.stop()
    assert poller.is_running is False


def test_poller_multi_frame_isotp_vin_reassembly() -> None:
    """Test reassembling a multi-frame UDS response for DID 0xF190 (VIN 17 bytes)."""
    tx_port = InMemoryTxPort()
    poller = ActiveDiagnosticPoller(tx_port=tx_port)

    decoded_results: list[UdsDidResult] = []
    poller.register_did(0xF190, rate_hz=1.0, callback=lambda r: decoded_results.append(r))

    # Trigger request
    poller.step()

    # Response payload: SID 0x62, DID 0xF190 (3 bytes) + 17 bytes VIN "1M8GDM9A_KP042788" = 20 bytes total
    # First Frame (PCI 0x10 0x14 = 20 bytes):
    # Data: [0x10, 0x14, 0x62, 0xF1, 0x90, ord('1'), ord('M'), ord('8')]
    ff_frame = CanFrame.create(
        channel_id="obd_ch0",
        arbitration_id=0x7E8,
        data=bytes([0x10, 0x14, 0x62, 0xF1, 0x90, ord("1"), ord("M"), ord("8")]),
        direction="rx",
    )

    res_ff, fc = poller.process_rx_frame(ff_frame)
    assert res_ff is None
    assert fc is not None
    assert fc.data[0] == 0x30  # Flow Control CTS (PCI 0x3, FS 0)

    # Consecutive Frame 1 (PCI 0x21): 7 bytes: "GDM9A_K"
    cf1_frame = CanFrame.create(
        channel_id="obd_ch0",
        arbitration_id=0x7E8,
        data=bytes([0x21, ord("G"), ord("D"), ord("M"), ord("9"), ord("A"), ord("_"), ord("K")]),
        direction="rx",
    )
    res_cf1, fc1 = poller.process_rx_frame(cf1_frame)
    assert res_cf1 is None
    assert fc1 is None

    # Consecutive Frame 2 (PCI 0x22): 7 bytes: "P042788"
    cf2_frame = CanFrame.create(
        channel_id="obd_ch0",
        arbitration_id=0x7E8,
        data=bytes([0x22, ord("P"), ord("0"), ord("4"), ord("2"), ord("7"), ord("8"), ord("8")]),
        direction="rx",
    )
    res_cf2, fc2 = poller.process_rx_frame(cf2_frame)
    assert fc2 is None
    assert res_cf2 is not None
    assert isinstance(res_cf2, UdsDidResult)
    assert res_cf2.did == 0xF190
    assert res_cf2.value == "1M8GDM9A_KP042788"
    assert len(decoded_results) == 1
    assert decoded_results[0].value == "1M8GDM9A_KP042788"


def test_poller_retry_exhaustion_transitions_to_failed() -> None:
    """Test exceeding MAX_RETRIES marks job as FAILED and sets next_run to regular interval.

    P5-corrected behavior: each timeout schedules a backoff retry and releases
    the active slot; once the backoff elapses the job is genuinely
    retransmitted. The budget is exhausted after MAX_RETRIES+1 timeouts.
    """
    tx_port = InMemoryTxPort()
    clock = FakeClock(start_time=100.0)
    poller = ActiveDiagnosticPoller(tx_port=tx_port, clock_provider=clock)

    poller.register_pid(0x0C, rate_hz=1.0, callback=lambda r: None)
    job = poller.step()
    assert job is not None

    # Drive alternating timeout/retransmission steps until the retry budget
    # is exhausted (bounded to avoid an unbounded loop in the test itself).
    for _ in range(20):
        if job.state == PollerState.FAILED:
            break
        clock.advance(2.5)  # past the 2.0 s response deadline
        poller.step()  # times out the active job OR retransmits a due one

    assert job.state == PollerState.FAILED
    assert job.consecutive_failures > 0


def test_poller_retry_retransmits_after_backoff() -> None:
    """P5 regression: a timed-out job is actually retransmitted after backoff.

    Before the fix, the job stayed in the active slot with a stale deadline,
    so every step() re-triggered _schedule_retry and burned the whole retry
    budget in milliseconds without a single retransmission.
    """
    tx_port = InMemoryTxPort()
    clock = FakeClock(start_time=100.0)
    poller = ActiveDiagnosticPoller(tx_port=tx_port, clock_provider=clock)

    poller.register_pid(0x0C, rate_hz=1.0, callback=lambda r: None)
    poller.step()  # first transmission
    assert len(tx_port.sent_frames) == 1
    assert poller._active_job is not None

    # Time out the first attempt -> retry scheduled, active slot released
    clock.advance(2.5)
    poller.step()
    assert poller._active_job is None  # released into backoff
    assert poller.current_state == PollerState.RETRY_BACKOFF

    # Advance past the backoff; the job must be retransmitted for real.
    clock.advance(2.5)
    poller.step()
    assert len(tx_port.sent_frames) == 2  # genuine retransmission occurred
    assert poller.current_state == PollerState.WAITING_FOR_RESPONSE


def test_poller_callback_exception_isolation() -> None:
    """Test that an exception inside user callback does not crash poller."""
    tx_port = InMemoryTxPort()
    poller = ActiveDiagnosticPoller(tx_port=tx_port)

    def faulty_callback(res: ObdPidResult) -> None:
        raise RuntimeError("Bug in user listener")

    poller.register_pid(0x0D, rate_hz=10.0, callback=faulty_callback)
    poller.step()

    resp_frame = CanFrame.create(
        channel_id="obd_ch0",
        arbitration_id=0x7E8,
        data=bytes([0x03, 0x41, 0x0D, 80, 0x55, 0x55, 0x55, 0x55]),
        direction="rx",
    )

    # Should not raise exception
    res, fc = poller.process_rx_frame(resp_frame)
    assert res is not None
    assert res.value == 80
    assert poller.current_state == PollerState.COMPLETED
