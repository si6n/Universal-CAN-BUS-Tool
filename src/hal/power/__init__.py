"""Windows Power Management and Sleep Prevention."""

from src.hal.power.win32_power import KeepSystemAwake, WindowsPowerManager

__all__ = ["KeepSystemAwake", "WindowsPowerManager"]
