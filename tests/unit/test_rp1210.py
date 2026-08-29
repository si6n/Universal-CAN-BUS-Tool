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
