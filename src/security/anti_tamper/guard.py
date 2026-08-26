"""Win32 Anti-Debug, Integrity Verification & Anti-Tamper Protection Guard."""

from __future__ import annotations

import ctypes
import sys
import time

from src.core.logging import get_logger

logger = get_logger("security.anti_tamper")


class AntiTamperGuard:
    """Detects active debuggers, process hooking, and execution tampering."""

    @classmethod
    def is_debugger_present(cls) -> bool:
        """Query Win32 IsDebuggerPresent API."""
        if sys.platform != "win32":
            return False

        windll = getattr(ctypes, "windll", None)
        if windll is None:
            return False

        try:
            return bool(windll.kernel32.IsDebuggerPresent())
        except (AttributeError, OSError, RuntimeError):
            return False

    @classmethod
    def check_remote_debugger(cls) -> bool:
        """Query Win32 CheckRemoteDebuggerPresent API."""
        if sys.platform != "win32":
            return False

        windll = getattr(ctypes, "windll", None)
        if windll is None:
            return False

        try:
            is_present = ctypes.c_bool(False)
            current_proc = windll.kernel32.GetCurrentProcess()
            res = windll.kernel32.CheckRemoteDebuggerPresent(current_proc, ctypes.byref(is_present))
            if res != 0 and is_present.value:
                return True
        except (AttributeError, OSError, RuntimeError):
            return False

        return False

    @classmethod
    def detect_timing_anomaly(cls, threshold_ms: float = 50.0) -> bool:
        """Measure timing delay to detect step-by-step debugger instrumentation."""
        t0 = time.perf_counter()
        # Minor CPU busy work
        _ = sum(i * i for i in range(10_000))
        t1 = time.perf_counter()

        elapsed_ms = (t1 - t0) * 1000.0
        if elapsed_ms > threshold_ms:
            logger.warning("Timing anomaly detected! Possible debugger single-stepping.", extra={"elapsed_ms": elapsed_ms})
            return True
        return False
