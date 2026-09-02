"""Unit tests for Phase 1 Core Port Contracts and Formal Exception Taxonomy.

Tests runtime protocol compliance, default contract implementations,
exception inheritance hierarchies, attribute propagation, and serialization.
"""

from __future__ import annotations

import time

import pytest

from src.core.contracts import (
    ClockProvider,
    InMemorySecretProvider,
    InMemoryTxPort,
    QueueRxSubscription,
    RxSubscription,
    SecretProvider,
    SystemClockProvider,
    TxPort,
)
from src.core.errors import PlatformError, TransportError
from src.core.exceptions import (
    IsoTpBufferOverflowError,
    IsoTpError,
    IsoTpFlowControlError,
    IsoTpInvalidPduError,
    IsoTpSequenceError,
    IsoTpTimeoutError,
    J1939SequenceError,
    J1939SessionCollisionError,
    J1939TpAbortError,
    J1939TpError,
    J1939TpTimeoutError,
)
from src.core.models.can_frame import CanFrame

# ============================================================================
# Protocol & Port Contract Tests
# ============================================================================


class DummyNonConformingObject:
    """Object that does not implement port protocols."""

    pass


class CustomClock:
    """Mock clock satisfying ClockProvider protocol."""

    def __init__(self, start_time: float = 100.0) -> None:
        self.current_time = start_time

    def advance(self, delta_s: float) -> None:
        self.current_time += delta_s

    def now_monotonic(self) -> float:
        return self.current_time

    def now_monotonic_ns(self) -> int:
        return int(self.current_time * 1_000_000_000)

    def now_wall_ns(self) -> int:
        return int(self.current_time * 1_000_000_000)


class CustomSecretProvider:
    """Mock secret provider satisfying SecretProvider protocol."""

    def __init__(self) -> None:
        self.storage: dict[str, bytes] = {}

    def get_secret(self, key_name: str) -> bytes:
        return self.storage.get(key_name, b"")


class TestPortContractsRuntimeCheckable:
    """Verify runtime type verification for all core Protocol definitions."""

    def test_tx_port_protocol_conformance(self) -> None:
        tx_port = InMemoryTxPort()
        assert isinstance(tx_port, TxPort)
        assert not isinstance(DummyNonConformingObject(), TxPort)

    def test_rx_subscription_protocol_conformance(self) -> None:
        rx_sub = QueueRxSubscription()
        assert isinstance(rx_sub, RxSubscription)
        assert not isinstance(DummyNonConformingObject(), RxSubscription)

    def test_clock_provider_protocol_conformance(self) -> None:
        sys_clock = SystemClockProvider()
        custom_clock = CustomClock()
        assert isinstance(sys_clock, ClockProvider)
        assert isinstance(custom_clock, ClockProvider)
        assert not isinstance(DummyNonConformingObject(), ClockProvider)

    def test_secret_provider_protocol_conformance(self) -> None:
        mem_secrets = InMemorySecretProvider()
        custom_secrets = CustomSecretProvider()
        assert isinstance(mem_secrets, SecretProvider)
        assert isinstance(custom_secrets, SecretProvider)
        assert not isinstance(DummyNonConformingObject(), SecretProvider)


class TestInMemoryTxPort:
    """Verify behavior of InMemoryTxPort test utility."""

    @pytest.mark.asyncio
    async def test_async_and_sync_send_recording(self) -> None:
        port = InMemoryTxPort()
        frame1 = CanFrame.create(channel_id="ch0", arbitration_id=0x7E0, data=b"\x02\x10\x01\x00\x00\x00\x00\x00")
        frame2 = CanFrame.create(channel_id="ch0", arbitration_id=0x7E8, data=b"\x02\x50\x01\x00\x00\x00\x00\x00")

        # Async send
        await port.send(frame1)
        assert len(port.sent_frames) == 1
        assert port.sent_frames[0] == frame1

        # Sync send
        port.send_sync(frame2)
        assert len(port.sent_frames) == 2
        assert port.sent_frames[1] == frame2

        # Clear
        port.clear()
        assert len(port.sent_frames) == 0


class TestQueueRxSubscription:
    """Verify behavior of QueueRxSubscription async receiver."""

    @pytest.mark.asyncio
    async def test_put_and_recv_with_timeout(self) -> None:
        sub = QueueRxSubscription()
        frame = CanFrame.create(channel_id="ch0", arbitration_id=0x18DAF110, data=b"\x01\x02\x03\x04", is_extended=True)

        # Test timeout on empty queue
        res = await sub.recv(timeout_s=0.01)
        assert res is None

        # Test non-blocking immediate recv (timeout_s=0) on empty queue
        res_immediate = await sub.recv(timeout_s=0.0)
        assert res_immediate is None

        # Synchronous put and recv
        sub.put_nowait(frame)
        recvd = await sub.recv(timeout_s=0.1)
        assert recvd == frame

        # Asynchronous put and recv
        await sub.put(frame)
        recvd2 = await sub.recv(timeout_s=None)
        assert recvd2 == frame

    @pytest.mark.asyncio
    async def test_unsubscribe_behavior(self) -> None:
        sub = QueueRxSubscription()
        frame = CanFrame.create(channel_id="ch0", arbitration_id=0x100, data=b"\x11\x22")
        sub.put_nowait(frame)

        assert not sub.is_unsubscribed
        sub.unsubscribe()
        assert sub.is_unsubscribed

        # Subsequent recv returns None immediately
        assert await sub.recv(timeout_s=0.1) is None
        assert await sub.recv(timeout_s=None) is None


class TestClockProviders:
    """Verify behavior of ClockProvider implementations."""

    def test_system_clock_provider(self) -> None:
        clock = SystemClockProvider()
        t1 = clock.now_monotonic()
        t1_ns = clock.now_monotonic_ns()

        assert isinstance(t1, float)
        assert isinstance(t1_ns, int)
        assert t1 > 0
        assert t1_ns > 0

        time.sleep(0.005)
        t2 = clock.now_monotonic()
        t2_ns = clock.now_monotonic_ns()

        assert t2 >= t1
        assert t2_ns >= t1_ns

    def test_custom_clock_provider(self) -> None:
        clock = CustomClock(start_time=50.0)
        assert clock.now_monotonic() == 50.0
        assert clock.now_monotonic_ns() == 50_000_000_000

        clock.advance(1.5)
        assert clock.now_monotonic() == 51.5
        assert clock.now_monotonic_ns() == 51_500_000_000


class TestSecretProviders:
    """Verify behavior of SecretProvider implementations."""

    def test_in_memory_secret_provider(self) -> None:
        provider = InMemorySecretProvider({"aes_key": b"\x01" * 16})
        assert provider.get_secret("aes_key") == b"\x01" * 16

        provider.set_secret("hmac_secret", b"super_secret_token")
        assert provider.get_secret("hmac_secret") == b"super_secret_token"

        with pytest.raises(KeyError, match="not found"):
            provider.get_secret("nonexistent_key")


# ============================================================================
# ISO 15765-2 Exception Taxonomy Tests
# ============================================================================


class TestIsoTpExceptions:
    """Verify ISO-TP exception hierarchy, attribute binding, and serialization."""

    def test_isotp_base_error_inheritance(self) -> None:
        err = IsoTpError("Base ISO-TP failure")
        assert isinstance(err, TransportError)
        assert isinstance(err, PlatformError)
        assert isinstance(err, Exception)
        assert err.code == "ISOTP_ERROR"
        assert err.message == "Base ISO-TP failure"

    def test_isotp_timeout_error(self) -> None:
        err = IsoTpTimeoutError(
            message="N_Bs timer expired awaiting FC",
            timeout_type="N_Bs",
            elapsed_ms=1050.5,
            limit_ms=1000.0,
            details={"session_id": 42},
        )
        assert isinstance(err, IsoTpError)
        assert isinstance(err, TransportError)
        assert err.timeout_type == "N_Bs"
        assert err.elapsed_ms == 1050.5
        assert err.limit_ms == 1000.0
        assert err.code == "ISOTP_TIMEOUT_N_Bs"

        d = err.to_dict()
        assert d["code"] == "ISOTP_TIMEOUT_N_Bs"
        assert d["details"]["timeout_type"] == "N_Bs"
        assert d["details"]["elapsed_ms"] == 1050.5
        assert d["details"]["limit_ms"] == 1000.0
        assert d["details"]["session_id"] == 42
        assert "timestamp_ns" in d

    def test_isotp_flow_control_error(self) -> None:
        err = IsoTpFlowControlError(
            message="WFTmax exceeded: received 17 consecutive WAIT frames",
            flow_status=1,
            wft_count=17,
            reason="WFTMAX_EXCEEDED",
            details={"peer_node": 0x7E0},
        )
        assert isinstance(err, IsoTpError)
        assert err.flow_status == 1
        assert err.wft_count == 17
        assert err.reason == "WFTMAX_EXCEEDED"
        assert err.code == "ISOTP_FLOW_CONTROL_ERROR"

        d = err.to_dict()
        assert d["details"]["flow_status"] == 1
        assert d["details"]["wft_count"] == 17
        assert d["details"]["reason"] == "WFTMAX_EXCEEDED"
        assert d["details"]["peer_node"] == 0x7E0

    def test_isotp_buffer_overflow_error(self) -> None:
        err = IsoTpBufferOverflowError(
            message="Receiver buffer capacity exceeded by First Frame",
            requested_length=65536,
            max_buffer_size=4096,
        )
        assert isinstance(err, IsoTpError)
        assert err.requested_length == 65536
        assert err.max_buffer_size == 4096
        assert err.code == "ISOTP_BUFFER_OVERFLOW"

        d = err.to_dict()
        assert d["details"]["requested_length"] == 65536
        assert d["details"]["max_buffer_size"] == 4096

    def test_isotp_sequence_error_positional_and_kwargs(self) -> None:
        # Instantiation with integers: IsoTpSequenceError(expected_sn=3, actual_sn=4)
        err1 = IsoTpSequenceError(3, 4)
        assert isinstance(err1, IsoTpError)
        assert err1.expected_sn == 3
        assert err1.actual_sn == 4
        assert "expected 3, got 4" in err1.message
        assert err1.code == "ISOTP_SEQUENCE_ERROR"

        # Instantiation with kwargs
        err2 = IsoTpSequenceError(expected_sn=7, actual_sn=9)
        assert err2.expected_sn == 7
        assert err2.actual_sn == 9

        # Instantiation with custom message
        err3 = IsoTpSequenceError("Custom sequence mismatch message", expected_sn=1, actual_sn=2)
        assert err3.message == "Custom sequence mismatch message"
        assert err3.expected_sn == 1
        assert err3.actual_sn == 2

    def test_isotp_invalid_pdu_error(self) -> None:
        raw = b"\x00\x11\x22\x33"
        err = IsoTpInvalidPduError(
            message="Classic Single Frame with SF_DL == 0 is invalid",
            pci_type=0,
            raw_data=raw,
            details={"channel": "can0"},
        )
        assert isinstance(err, IsoTpError)
        assert err.pci_type == 0
        assert err.raw_data == raw
        assert err.code == "ISOTP_INVALID_PDU"

        d = err.to_dict()
        assert d["details"]["pci_type"] == 0
        assert d["details"]["raw_data_hex"] == raw.hex()
        assert d["details"]["channel"] == "can0"


# ============================================================================
# SAE J1939 Exception Taxonomy Tests
# ============================================================================


class TestJ1939Exceptions:
    """Verify SAE J1939 exception hierarchy, attribute binding, and serialization."""

    def test_j1939_tp_base_error_inheritance(self) -> None:
        err = J1939TpError("Base J1939 failure")
        assert isinstance(err, TransportError)
        assert isinstance(err, PlatformError)
        assert isinstance(err, Exception)
        assert err.code == "J1939_TP_ERROR"

    def test_j1939_tp_abort_error(self) -> None:
        err = J1939TpAbortError(
            message="Connection aborted: Reason 1 (Sequence Error)",
            reason=1,
            target_pgn=65226,
            sa=0x00,
            da=0xF9,
        )
        assert isinstance(err, J1939TpError)
        assert isinstance(err, TransportError)
        assert err.reason == 1
        assert err.target_pgn == 65226
        assert err.sa == 0x00
        assert err.da == 0xF9
        assert err.code == "J1939_TP_ABORT"

        d = err.to_dict()
        assert d["details"]["reason"] == 1
        assert d["details"]["target_pgn"] == 65226
        assert d["details"]["sa"] == 0x00
        assert d["details"]["da"] == 0xF9

    def test_j1939_session_collision_error(self) -> None:
        err = J1939SessionCollisionError(
            message="Active RTS collision on node pair (0x00, 0xF9)",
            sa=0x00,
            da=0xF9,
            old_pgn=65226,
            new_pgn=65227,
        )
        assert isinstance(err, J1939TpError)
        assert err.sa == 0x00
        assert err.da == 0xF9
        assert err.old_pgn == 65226
        assert err.new_pgn == 65227
        assert err.code == "J1939_SESSION_COLLISION"

        d = err.to_dict()
        assert d["details"]["old_pgn"] == 65226
        assert d["details"]["new_pgn"] == 65227

    def test_j1939_sequence_error(self) -> None:
        err = J1939SequenceError(
            message="Out-of-order TP.DT packet received",
            expected_seq=3,
            received_seq=5,
            sa=0x10,
            da=0xF9,
        )
        assert isinstance(err, J1939TpError)
        assert err.expected_seq == 3
        assert err.received_seq == 5
        assert err.sa == 0x10
        assert err.da == 0xF9
        assert err.code == "J1939_SEQUENCE_ERROR"

        d = err.to_dict()
        assert d["details"]["expected_seq"] == 3
        assert d["details"]["received_seq"] == 5

    def test_j1939_tp_timeout_error(self) -> None:
        err = J1939TpTimeoutError(
            message="T1 timeout waiting for TP.DT data packet",
            timeout_type="T1",
            elapsed_ms=755.0,
            limit_ms=750.0,
            sa=0x20,
            da=0xF9,
            target_pgn=61444,
        )
        assert isinstance(err, J1939TpError)
        assert err.timeout_type == "T1"
        assert err.elapsed_ms == 755.0
        assert err.limit_ms == 750.0
        assert err.sa == 0x20
        assert err.da == 0xF9
        assert err.target_pgn == 61444
        assert err.code == "J1939_TIMEOUT_T1"

        d = err.to_dict()
        assert d["details"]["timeout_type"] == "T1"
        assert d["details"]["target_pgn"] == 61444


# ============================================================================
# Polymorphism & Error Handling Backward Compatibility Tests
# ============================================================================


class TestPolymorphismAndErrorCatching:
    """Verify that existing TransportError and PlatformError catch blocks work as expected."""

    def test_catch_all_isotp_under_transport_error(self) -> None:
        caught = False
        try:
            raise IsoTpTimeoutError("Timeout", timeout_type="N_Cr")
        except TransportError as ex:
            caught = True
            assert isinstance(ex, IsoTpError)
            assert ex.code == "ISOTP_TIMEOUT_N_Cr"
        assert caught

    def test_catch_all_j1939_under_transport_error(self) -> None:
        caught = False
        try:
            raise J1939SessionCollisionError("Collision", sa=1, da=2, old_pgn=100, new_pgn=200)
        except TransportError as ex:
            caught = True
            assert isinstance(ex, J1939TpError)
            assert ex.code == "J1939_SESSION_COLLISION"
        assert caught

    def test_exception_chaining_cause_propagation(self) -> None:
        original = ValueError("Underlying raw parse fault")
        err = IsoTpInvalidPduError("Malformed frame", pci_type=1, raw_data=b"\x12\x34", cause=original)

        assert err.cause is original
        d = err.to_dict()
        assert "Underlying raw parse fault" in d["cause"]
