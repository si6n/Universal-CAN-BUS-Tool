"""Unit and integration tests for application entry point and lifecycle (src/main.py)."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from src.core.models.can_frame import CanFrame
from src.main import UniversalCanMainWindow, main


def test_main_cli_mode_lifecycle() -> None:
    """Verify CLI execution mode properly connects and disconnects bus."""
    mock_bus = MagicMock()
    mock_bus.recv.side_effect = [
        CanFrame.create(channel_id="vcan0", arbitration_id=0x100, data=b"\x01\x02"),
        KeyboardInterrupt(),
    ]

    with (
        patch.object(sys, "argv", ["main.py", "--cli", "--interface", "virtual", "--channel", "vcan0"]),
        patch("src.main.PythonCanBus", return_value=mock_bus),
    ):
        ret = main()
        assert ret == 0
        mock_bus.connect.assert_called_once()
        mock_bus.disconnect.assert_called_once()


def test_main_cli_keyboard_interrupt_graceful_shutdown() -> None:
    """Verify KeyboardInterrupt in CLI mode exits cleanly with code 0 and disconnects bus."""
    mock_bus = MagicMock()
    mock_bus.recv.side_effect = KeyboardInterrupt()

    with (
        patch.object(sys, "argv", ["main.py", "--cli"]),
        patch("src.main.PythonCanBus", return_value=mock_bus),
    ):
        ret = main()
        assert ret == 0
        mock_bus.disconnect.assert_called_once()


def test_window_close_event_cleans_resources() -> None:
    """Verify closeEvent stops worker thread and disconnects hardware bus."""
    mock_bus = MagicMock()
    mock_bus.is_connected = True

    window = UniversalCanMainWindow(bus=mock_bus)
    window.show()

    # Trigger close
    window.close()

    mock_bus.disconnect.assert_called()


def test_main_gui_mode_lifecycle_bus_disconnect() -> None:
    """Verify main() GUI execution wraps app.exec() in try/finally calling bus.disconnect()."""
    mock_bus = MagicMock()
    mock_app = MagicMock()
    mock_app.exec.return_value = 0
    mock_window = MagicMock()

    with (
        patch.object(sys, "argv", ["main.py"]),
        patch("src.main.QApplication", return_value=mock_app),
        patch("src.main.PythonCanBus", return_value=mock_bus),
        patch("src.main.UniversalCanMainWindow", return_value=mock_window),
    ):
        ret = main()
        assert ret == 0
        mock_bus.disconnect.assert_called_once()
