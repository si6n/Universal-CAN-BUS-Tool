"""Session-wide pytest tuning (imported once, no fixtures)."""

from __future__ import annotations

import ctypes
import sys


def _enable_windows_high_resolution_timer() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.winmm.timeBeginPeriod(1)
    except Exception:
        pass


_enable_windows_high_resolution_timer()
