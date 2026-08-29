"""Unit tests for WindowsPowerManager and KeepSystemAwake."""

from src.hal.power.win32_power import KeepSystemAwake, WindowsPowerManager


def test_win32_power_manager_calls() -> None:
    # Test execution across platforms (graceful fallback on non-Windows / no crash on Win32)
    assert WindowsPowerManager.prevent_sleep(keep_display_on=True) is True
    assert WindowsPowerManager.restore_sleep() is True

    # Test context manager
    with KeepSystemAwake(keep_display_on=False):
        pass
