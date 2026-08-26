"""TMC RP1210 (A/B/C) 64-Bit Isolated Ctypes Client Wrapper.

Matches MASTER_PLAN.md Section 8.1 / 19.2 (Task 0.3).
"""

from __future__ import annotations

import ctypes
import os
import sys
from types import TracebackType
from typing import Self

from src.core.errors import HardwareError, TransportError
from src.core.logging import get_logger
from src.hal.rp1210.types import RP1210ErrorCode

logger = get_logger("hal.rp1210")


class RP1210Client:
    """Standard-compliant TMC RP1210 client wrapper supporting NEXIQ, DPA5, Noregon adapters."""

    def __init__(self, dll_name: str, device_id: int = 1, protocol: str = "J1939") -> None:
        self.dll_name = dll_name
        self.device_id = device_id
        self.protocol = protocol
        self.client_id: int | None = None
        self._dll: ctypes.CDLL | None = None

        self._load_dll()

    def _load_dll(self) -> None:
        """Dynamically load RP1210 64-bit or 32-bit DLL with safe error wrapping."""
        # Find DLL in System32 / SysWOW64 or local paths
        dll_candidates = [
            self.dll_name,
            os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "System32", self.dll_name),
            os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "SysWOW64", self.dll_name),
        ]

        loaded = False
        last_err: Exception | None = None

        for path in dll_candidates:
            try:
                # Use WinDLL on Windows for stdcall convention
                if sys.platform == "win32":
                    self._dll = ctypes.WinDLL(path)
                else:
                    self._dll = ctypes.CDLL(path)
                loaded = True
                logger.info("Loaded RP1210 DLL successfully", extra={"path": path})
                break
            except (OSError, FileNotFoundError) as exc:
                last_err = exc

        if not loaded or self._dll is None:
            raise HardwareError(
                f"RP1210 DLL '{self.dll_name}' could not be loaded. Please ensure the vendor driver is installed.",
                code="HARDWARE_DLL_NOT_FOUND",
                details={"dll_name": self.dll_name, "candidates": dll_candidates},
                cause=last_err,
            )

        # Setup ctypes function signatures
        self._setup_signatures()

    def _setup_signatures(self) -> None:
        """Define strict C argument and return types for RP1210 API functions."""
        if not self._dll:
            return

        # RP1210_ClientConnect(hwnd, nDeviceID, fpchProtocol, lTxBuf, lRxBuf, nBlockOnSend) -> short
        if hasattr(self._dll, "RP1210_ClientConnect"):
            self._dll.RP1210_ClientConnect.argtypes = [
                ctypes.c_long,
                ctypes.c_short,
                ctypes.c_char_p,
                ctypes.c_long,
                ctypes.c_long,
                ctypes.c_short,
            ]
            self._dll.RP1210_ClientConnect.restype = ctypes.c_short

        # RP1210_ClientDisconnect(nClientID) -> short
        if hasattr(self._dll, "RP1210_ClientDisconnect"):
            self._dll.RP1210_ClientDisconnect.argtypes = [ctypes.c_short]
            self._dll.RP1210_ClientDisconnect.restype = ctypes.c_short

        # RP1210_SendMessage(nClientID, fpchMsg, nMsgSize, nNotify, nBlock) -> short
        if hasattr(self._dll, "RP1210_SendMessage"):
            self._dll.RP1210_SendMessage.argtypes = [
                ctypes.c_short,
                ctypes.c_char_p,
                ctypes.c_short,
                ctypes.c_short,
                ctypes.c_short,
            ]
            self._dll.RP1210_SendMessage.restype = ctypes.c_short

        # RP1210_ReadMessage(nClientID, fpchRxBuf, nBufSize, nBlock) -> short
        if hasattr(self._dll, "RP1210_ReadMessage"):
            self._dll.RP1210_ReadMessage.argtypes = [
                ctypes.c_short,
                ctypes.c_char_p,
                ctypes.c_short,
                ctypes.c_short,
            ]
            self._dll.RP1210_ReadMessage.restype = ctypes.c_short

        # RP1210_GetErrorMsg(nErrorCode, fpchDescription) -> short
        if hasattr(self._dll, "RP1210_GetErrorMsg"):
            self._dll.RP1210_GetErrorMsg.argtypes = [ctypes.c_short, ctypes.c_char_p]
            self._dll.RP1210_GetErrorMsg.restype = ctypes.c_short

    def connect(self, tx_buffer_size: int = 8000, rx_buffer_size: int = 8000) -> int:
        """Establish client connection to the RP1210 adapter."""
        if not self._dll:
            raise HardwareError("DLL not loaded")

        proto_bytes = self.protocol.encode("ascii")
        client_id = self._dll.RP1210_ClientConnect(
            0,
            ctypes.c_short(self.device_id),
            proto_bytes,
            ctypes.c_long(tx_buffer_size),
            ctypes.c_long(rx_buffer_size),
            0,
        )

        if client_id < 0 or client_id > 127:
            err_desc = self.get_error_message(client_id)
            raise HardwareError(
                f"RP1210_ClientConnect failed with error code {client_id}: {err_desc}",
                code="HARDWARE_CONNECT_FAILED",
                details={"error_code": client_id, "description": err_desc},
            )

        self.client_id = int(client_id)
        logger.info("Connected to RP1210 adapter", extra={"client_id": client_id, "device_id": self.device_id})
        return int(client_id)

    def disconnect(self) -> None:
        """Gracefully disconnect from the RP1210 adapter."""
        if self.client_id is not None and self._dll:
            ret = self._dll.RP1210_ClientDisconnect(ctypes.c_short(self.client_id))
            if ret != RP1210ErrorCode.NO_ERRORS:
                logger.warning("RP1210_ClientDisconnect returned error", extra={"error_code": ret})
            self.client_id = None

    def send_message(self, message_bytes: bytes, block: bool = False) -> None:
        """Transmit raw frame through RP1210 bus."""
        if self.client_id is None or not self._dll:
            raise HardwareError("RP1210 client is not connected")

        ret = self._dll.RP1210_SendMessage(
            ctypes.c_short(self.client_id),
            message_bytes,
            ctypes.c_short(len(message_bytes)),
            0,
            1 if block else 0,
        )

        if ret != RP1210ErrorCode.NO_ERRORS:
            err_desc = self.get_error_message(ret)
            raise TransportError(
                f"RP1210_SendMessage failed: {err_desc}",
                code="TRANSPORT_TX_FAILED",
                details={"error_code": ret, "description": err_desc},
            )

    def read_message(self, buffer_size: int = 2048, block: bool = False) -> bytes | None:
        """Read received packet from RP1210 queue. Returns None if queue is empty."""
        if self.client_id is None or not self._dll:
            raise HardwareError("RP1210 client is not connected")

        rx_buffer = ctypes.create_string_buffer(buffer_size)
        ret = self._dll.RP1210_ReadMessage(
            ctypes.c_short(self.client_id),
            rx_buffer,
            ctypes.c_short(buffer_size),
            1 if block else 0,
        )

        if ret > 0:
            return bytes(rx_buffer.raw[:ret])
        if ret == 0:
            return None  # Queue empty

        # Error code returned (ret < 0 or ret >= 128)
        err_code = abs(ret)
        if err_code == RP1210ErrorCode.ERR_RX_QUEUE_FULL:
            logger.warning("RP1210 RX Queue is full; frame drops may occur")
            return None

        err_desc = self.get_error_message(err_code)
        raise HardwareError(
            f"RP1210_ReadMessage failed: {err_desc}",
            code="HARDWARE_READ_FAILED",
            details={"error_code": err_code, "description": err_desc},
        )

    def get_error_message(self, error_code: int) -> str:
        """Fetch descriptive error string from RP1210 DLL or fallback dictionary."""
        if self._dll and hasattr(self._dll, "RP1210_GetErrorMsg"):
            desc_buf = ctypes.create_string_buffer(256)
            ret = self._dll.RP1210_GetErrorMsg(ctypes.c_short(error_code), desc_buf)
            if ret == 0:
                raw_str = desc_buf.value.decode("ascii", errors="ignore").strip()
                if raw_str:
                    return raw_str

        return RP1210ErrorCode.get_description(error_code)

    def __enter__(self) -> Self:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.disconnect()
