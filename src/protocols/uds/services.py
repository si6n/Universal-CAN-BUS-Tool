"""ISO 14229-1 Unified Diagnostic Services (UDS) Message Builders and Parsers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from src.protocols.uds.nrc import NRC_DESCRIPTIONS, UdsNrc


class UdsServiceId(IntEnum):
    """ISO 14229-1 Service Identifiers (SID)."""

    DIAGNOSTIC_SESSION_CONTROL = 0x10
    ECU_RESET = 0x11
    SECURITY_ACCESS = 0x27
    COMMUNICATION_CONTROL = 0x28
    TESTER_PRESENT = 0x3E
    READ_DATA_BY_IDENTIFIER = 0x22
    WRITE_DATA_BY_IDENTIFIER = 0x2E
    CLEAR_DIAGNOSTIC_INFORMATION = 0x14
    READ_DTC_INFORMATION = 0x19
    ROUTINE_CONTROL = 0x31
    REQUEST_DOWNLOAD = 0x34
    TRANSFER_DATA = 0x36
    REQUEST_TRANSFER_EXIT = 0x37
    NEGATIVE_RESPONSE = 0x7F


class DiagnosticSessionType(IntEnum):
    """0x10 Diagnostic Session Types."""

    DEFAULT_SESSION = 0x01
    PROGRAMMING_SESSION = 0x02
    EXTENDED_DIAGNOSTIC_SESSION = 0x03
    SAFETY_SYSTEM_DIAGNOSTIC_SESSION = 0x04


class RoutineControlType(IntEnum):
    """0x31 Routine Control Sub-functions."""

    START_ROUTINE = 0x01
    STOP_ROUTINE = 0x02
    REQUEST_ROUTINE_RESULTS = 0x03


@dataclass(slots=True)
class UdsResponse:
    """Parsed ISO 14229 UDS response message."""

    service_id: int
    is_positive: bool
    data: bytes
    nrc: UdsNrc = UdsNrc.POSITIVE_RESPONSE

    @property
    def nrc_description_en(self) -> str:
        return NRC_DESCRIPTIONS.get(self.nrc, (f"NRC 0x{self.nrc:02X}", f"NRC 0x{self.nrc:02X}"))[0]

    @property
    def nrc_description_tr(self) -> str:
        return NRC_DESCRIPTIONS.get(self.nrc, (f"NRC 0x{self.nrc:02X}", f"NRC 0x{self.nrc:02X}"))[1]


class UdsServiceBuilder:
    """Builds raw payload bytes for UDS diagnostic requests."""

    @classmethod
    def build_diagnostic_session_control(cls, session_type: DiagnosticSessionType) -> bytes:
        return bytes([UdsServiceId.DIAGNOSTIC_SESSION_CONTROL, session_type])

    @classmethod
    def build_tester_present(cls, suppress_positive_response: bool = False) -> bytes:
        sub_fn = 0x80 if suppress_positive_response else 0x00
        return bytes([UdsServiceId.TESTER_PRESENT, sub_fn])

    @classmethod
    def build_read_data_by_identifier(cls, did: int) -> bytes:
        return bytes([UdsServiceId.READ_DATA_BY_IDENTIFIER, (did >> 8) & 0xFF, did & 0xFF])

    @classmethod
    def build_write_data_by_identifier(cls, did: int, data: bytes) -> bytes:
        return bytes([UdsServiceId.WRITE_DATA_BY_IDENTIFIER, (did >> 8) & 0xFF, did & 0xFF]) + data

    @classmethod
    def build_security_access_request_seed(cls, level: int = 1) -> bytes:
        return bytes([UdsServiceId.SECURITY_ACCESS, level])

    @classmethod
    def build_security_access_send_key(cls, level: int, key: bytes) -> bytes:
        return bytes([UdsServiceId.SECURITY_ACCESS, level + 1]) + key

    @classmethod
    def build_routine_control(
        cls,
        control_type: RoutineControlType,
        routine_id: int,
        option_bytes: bytes = b"",
    ) -> bytes:
        header = bytes([
            UdsServiceId.ROUTINE_CONTROL,
            control_type,
            (routine_id >> 8) & 0xFF,
            routine_id & 0xFF,
        ])
        return header + option_bytes

    @classmethod
    def build_request_download(
        cls,
        memory_address: int,
        memory_size: int,
        data_format_identifier: int = 0x00,
        address_and_length_format_identifier: int = 0x44,
    ) -> bytes:
        addr_bytes = memory_address.to_bytes(4, byteorder="big")
        size_bytes = memory_size.to_bytes(4, byteorder="big")
        return bytes([
            UdsServiceId.REQUEST_DOWNLOAD,
            data_format_identifier,
            address_and_length_format_identifier,
        ]) + addr_bytes + size_bytes

    @classmethod
    def build_transfer_data(cls, block_sequence: int, data: bytes) -> bytes:
        return bytes([UdsServiceId.TRANSFER_DATA, block_sequence & 0xFF]) + data

    @classmethod
    def build_request_transfer_exit(cls) -> bytes:
        return bytes([UdsServiceId.REQUEST_TRANSFER_EXIT])

    @classmethod
    def build_ecu_reset(cls, reset_type: int = 0x01) -> bytes:
        return bytes([UdsServiceId.ECU_RESET, reset_type & 0xFF])

    @classmethod
    def parse_response(cls, payload: bytes) -> UdsResponse:
        """Parse raw diagnostic response payload."""
        if not payload:
            raise ValueError("Empty UDS payload")

        sid = payload[0]

        # Negative Response (0x7F, Rejected SID, NRC)
        if sid == UdsServiceId.NEGATIVE_RESPONSE:
            if len(payload) < 3:
                raise ValueError("Negative response requires at least 3 bytes")
            rejected_sid = payload[1]
            nrc_val = payload[2]
            return UdsResponse(
                service_id=rejected_sid,
                is_positive=False,
                data=payload[3:],
                nrc=UdsNrc(nrc_val) if nrc_val in UdsNrc._value2member_map_ else UdsNrc.GENERAL_REJECT,
            )

        # Positive Response (SID + 0x40)
        orig_sid = sid - 0x40 if sid >= 0x40 else sid
        return UdsResponse(
            service_id=orig_sid,
            is_positive=True,
            data=payload[1:],
            nrc=UdsNrc.POSITIVE_RESPONSE,
        )
