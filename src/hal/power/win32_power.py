"""Windows 10/11 x64 Power Management & USB Sleep Prevention.

Prevents laptop USB selective suspend and system sleep during high-speed telemetry recording.
Complies with MASTER_PLAN.md Section 9.
"""

from __future__ import annotations

import ctypes
import sys
from typing import ClassVar, Self

from src.core.logging import get_logger

logger = get_logger("hal.power")

# Windows Execution State Flags
ES_SYSTEM_REQUIRED: int = 0x00000001
ES_DISPLAY_REQUIRED: int = 0x00000002
ES_AWAYMODE_REQUIRED: int = 0x00000040
ES_CONTINUOUS: int = 0x80000000


class WindowsPowerManager:
    """Controls Windows kernel thread execution state to prevent USB and system sleep."""

    _is_active: ClassVar[bool] = False

    @classmethod
    def prevent_sleep(cls, keep_display_on: bool = False) -> bool:
        """Tell Windows kernel to keep system awake and USB controllers powered."""
        if sys.platform != "win32":
            return True

        windll = getattr(ctypes, "windll", None)
        if windll is None:
            return False

        flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
        if keep_display_on:
            flags |= ES_DISPLAY_REQUIRED

        try:
            prev_state = windll.kernel32.SetThreadExecutionState(flags)
            if prev_state != 0:
                cls._is_active = True
                logger.info("SetThreadExecutionState: System Sleep Prevention ACTIVATED")
                return True
        except (AttributeError, OSError, RuntimeError) as exc:
            logger.warning("Failed to invoke SetThreadExecutionState", extra={"error": str(exc)})

        return False

    @classmethod
    def restore_sleep(cls) -> bool:
        """Restore normal Windows power management behavior."""
        if sys.platform != "win32":
            return True

        windll = getattr(ctypes, "windll", None)
        if windll is None:
            return False

        try:
            prev_state = windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
            if prev_state != 0:
                cls._is_active = False
                logger.info("SetThreadExecutionState: Normal Power Management RESTORED")
                return True
        except (AttributeError, OSError, RuntimeError) as exc:
            logger.warning("Failed to restore SetThreadExecutionState", extra={"error": str(exc)})

        return False

    @classmethod
    def is_active(cls) -> bool:
        return cls._is_active


class KeepSystemAwake:
    """Context manager for scoped sleep prevention during diagnostics and flashing."""

    def __init__(self, keep_display_on: bool = False) -> None:
        self.keep_display_on = keep_display_on

    def __enter__(self) -> Self:
        WindowsPowerManager.prevent_sleep(keep_display_on=self.keep_display_on)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        WindowsPowerManager.restore_sleep()
