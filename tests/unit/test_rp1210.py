"""Unit tests for RP1210 client wrapper and error codes."""

import pytest

from src.core.errors import HardwareError
from src.hal.rp1210.client import RP1210Client
from src.hal.rp1210.types import RP1210ErrorCode


def test_rp1210_error_code_descriptions() -> None:
    assert RP1210ErrorCode.get_description(0) == "No Errors"
    assert RP1210ErrorCode.get_description(128) == "Dll Not Found"
    assert RP1210ErrorCode.get_description(145) == "Bus Off"
    assert RP1210ErrorCode.get_description(155) == "Address Lost"
    assert "Unknown" in RP1210ErrorCode.get_description(9999)


def test_rp1210_missing_dll_raises_hardware_error() -> None:
    # Attempting to load non-existent vendor DLL must raise structured HardwareError
    with pytest.raises(HardwareError) as exc_info:
        RP1210Client(dll_name="NON_EXISTENT_ADAPTER_12345.DLL")

    assert exc_info.value.code == "HARDWARE_DLL_NOT_FOUND"
    assert "NON_EXISTENT_ADAPTER_12345.DLL" in exc_info.value.message
    assert "dll_name" in exc_info.value.details


class _FakeRP1210Dll:
    """Test double exposing only RP1210_ReadMessage with a scripted return value."""

    def __init__(self, read_return_value: int) -> None:
        self._read_return_value = read_return_value

    def RP1210_ReadMessage(self, client_id: int, rx_buffer: object, buf_size: int, block: int) -> int:
        return self._read_return_value


def _make_client_with_fake_dll(read_return_value: int) -> RP1210Client:
    client = RP1210Client.__new__(RP1210Client)
    client.dll_name = "FAKE.DLL"
    client.device_id = 1
    client.protocol = "J1939"
    client.client_id = 1
    client._dll = _FakeRP1210Dll(read_return_value)  # type: ignore[assignment]
    return client


def test_rp1210_read_error_code_is_not_returned_as_data() -> None:
    # D2 regression: RP1210 error codes start at 128. ret=129 (INVALID_CLIENT_ID)
    # must be treated as an error, never as "129 bytes of received data".
    client = _make_client_with_fake_dll(129)
    with pytest.raises(HardwareError) as exc_info:
        client.read_message()
    assert exc_info.value.code == "HARDWARE_READ_FAILED"


def test_rp1210_read_rx_queue_full_returns_none() -> None:
    # D2 regression: ret=136 (ERR_RX_QUEUE_FULL) is an error code, handled
    # gracefully as None (drop warning), not returned as 136 bytes of data.
    client = _make_client_with_fake_dll(RP1210ErrorCode.ERR_RX_QUEUE_FULL)
    assert client.read_message() is None


def test_rp1210_read_empty_queue_returns_none() -> None:
    client = _make_client_with_fake_dll(0)
    assert client.read_message() is None


def test_rp1210_read_positive_byte_count_returns_data() -> None:
    # Genuine byte counts (1..127) still return payload bytes.
    client = _make_client_with_fake_dll(8)
    result = client.read_message()
    assert result is not None
    assert len(result) == 8
