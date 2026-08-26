"""High-Level ISO 14229 UDS Diagnostic Client Engine."""

from __future__ import annotations

import concurrent.futures
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from src.core.errors import ProtocolError
from src.core.logging import get_logger
from src.protocols.uds.isotp import IsoTpTransport
from src.protocols.uds.services import (
    DiagnosticSessionType,
    RoutineControlType,
    UdsResponse,
    UdsServiceBuilder,
)

if TYPE_CHECKING:
    from src.hal.base import AbstractBus

logger = get_logger("protocols.uds.client")


class UdsClient:
    """Synchronous / Non-blocking ISO 14229 Diagnostic Client over ISO-TP."""

    def __init__(
        self,
        bus: AbstractBus,
        tx_id: int = 0x7E0,
        rx_id: int = 0x7E8,
        channel_id: str = "uds_ch0",
        max_workers: int = 4,
    ) -> None:
        self.bus = bus
        self.tx_id = tx_id
        self.rx_id = rx_id
        self.channel_id = channel_id
        self.transport = IsoTpTransport(tx_id=tx_id, rx_id=rx_id, channel_id=channel_id)
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="uds_client"
        )

    def execute_async(
        self,
        fn: Callable[..., Any],
        *args: Any,
        callback: Callable[[Any], None] | None = None,
        error_callback: Callable[[Exception], None] | None = None,
        **kwargs: Any,
    ) -> concurrent.futures.Future[Any]:
        """Execute a diagnostic routine asynchronously in the background thread pool."""

        def _worker() -> Any:
            try:
                result = fn(*args, **kwargs)
                if callback is not None:
                    try:
                        callback(result)
                    except Exception as cb_err:
                        logger.error("Error in UdsClient async callback", extra={"error": str(cb_err)})
                return result
            except Exception as exc:
                if error_callback is not None:
                    try:
                        error_callback(exc)
                    except Exception as err_cb_err:
                        logger.error("Error in UdsClient async error_callback", extra={"error": str(err_cb_err)})
                raise

        return self._executor.submit(_worker)

    def close(self) -> None:
        """Close client and terminate worker threads."""
        self.shutdown(wait=True)

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown underlying thread pool executor."""
        self._executor.shutdown(wait=wait)

    def change_session(self, session_type: DiagnosticSessionType) -> UdsResponse:
        """Switch diagnostic session (0x10)."""
        req_payload = UdsServiceBuilder.build_diagnostic_session_control(session_type)
        return self._send_and_receive(req_payload)

    def security_access_request_seed(self, level: int = 1) -> UdsResponse:
        """Request Security Access Seed (0x27)."""
        req_payload = UdsServiceBuilder.build_security_access_request_seed(level=level)
        return self._send_and_receive(req_payload)

    def security_access_send_key(self, level: int, key: bytes) -> UdsResponse:
        """Send Security Access Key (0x27)."""
        req_payload = UdsServiceBuilder.build_security_access_send_key(level=level, key=key)
        return self._send_and_receive(req_payload)

    def read_did(self, did: int) -> UdsResponse:
        """Read Data Identifier (0x22)."""
        req_payload = UdsServiceBuilder.build_read_data_by_identifier(did)
        return self._send_and_receive(req_payload)

    def write_did(self, did: int, data: bytes) -> UdsResponse:
        """Write Data Identifier (0x2E)."""
        req_payload = UdsServiceBuilder.build_write_data_by_identifier(did, data)
        return self._send_and_receive(req_payload)

    def request_download(
        self,
        memory_address: int,
        memory_size: int,
        data_format_identifier: int = 0x00,
        address_and_length_format_identifier: int = 0x44,
    ) -> UdsResponse:
        """Request Download (0x34)."""
        req_payload = UdsServiceBuilder.build_request_download(
            memory_address=memory_address,
            memory_size=memory_size,
            data_format_identifier=data_format_identifier,
            address_and_length_format_identifier=address_and_length_format_identifier,
        )
        return self._send_and_receive(req_payload)

    def transfer_data(self, block_sequence: int, data: bytes) -> UdsResponse:
        """Transfer Data Block (0x36)."""
        req_payload = UdsServiceBuilder.build_transfer_data(block_sequence=block_sequence, data=data)
        return self._send_and_receive(req_payload)

    def request_transfer_exit(self) -> UdsResponse:
        """Request Transfer Exit (0x37)."""
        req_payload = UdsServiceBuilder.build_request_transfer_exit()
        return self._send_and_receive(req_payload)

    def ecu_reset(self, reset_type: int = 0x01) -> UdsResponse:
        """ECU Reset (0x11)."""
        req_payload = UdsServiceBuilder.build_ecu_reset(reset_type=reset_type)
        return self._send_and_receive(req_payload)

    def start_routine(self, routine_id: int, options: bytes = b"") -> UdsResponse:
        """Start ECU Routine (0x31)."""
        req_payload = UdsServiceBuilder.build_routine_control(
            RoutineControlType.START_ROUTINE, routine_id, options
        )
        return self._send_and_receive(req_payload)

    def stop_routine(self, routine_id: int) -> UdsResponse:
        """Stop ECU Routine (0x31)."""
        req_payload = UdsServiceBuilder.build_routine_control(
            RoutineControlType.STOP_ROUTINE, routine_id
        )
        return self._send_and_receive(req_payload)

    def request_routine_results(self, routine_id: int) -> UdsResponse:
        """Query ECU Routine Results (0x31)."""
        req_payload = UdsServiceBuilder.build_routine_control(
            RoutineControlType.REQUEST_ROUTINE_RESULTS, routine_id
        )
        return self._send_and_receive(req_payload)

    def tester_present(self, suppress_response: bool = False) -> UdsResponse | None:
        """Send Tester Present keep-alive (0x3E)."""
        req_payload = UdsServiceBuilder.build_tester_present(suppress_response)
        if suppress_response:
            self._send_payload(req_payload)
            return None
        return self._send_and_receive(req_payload)

    def _send_payload(self, payload: bytes) -> None:
        frames = self.transport.segment_message(payload)
        for frame in frames:
            self.bus.send(frame)

    def _send_and_receive(self, payload: bytes, timeout_s: float = 2.0) -> UdsResponse:
        """Send segmented UDS request and wait for complete ISO-TP reassembled response."""
        self._send_payload(payload)

        start_time = time.monotonic()

        while (time.monotonic() - start_time) < timeout_s:
            rx_frame = self.bus.recv(timeout_s=0.1)
            if rx_frame is not None and rx_frame.arbitration_id == self.rx_id:
                completed_data, resp_frame = self.transport.handle_rx_frame(rx_frame)
                if resp_frame is not None:
                    # Flow control frame response
                    self.bus.send(resp_frame)
                if completed_data is not None:
                    return UdsServiceBuilder.parse_response(completed_data)

        raise ProtocolError(
            f"UDS Request timed out waiting for response from ECU (0x{self.rx_id:03X})",
            code="UDS_TIMEOUT",
            details={"tx_id": hex(self.tx_id), "rx_id": hex(self.rx_id)},
        )
