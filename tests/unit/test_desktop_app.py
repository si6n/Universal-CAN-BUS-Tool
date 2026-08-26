"""Unit tests for Universal CAN Desktop Application Bridge and Lifecycle."""

from __future__ import annotations

from src.ui.desktop_app import DesktopApiBridge, UniversalCanDesktopApp


def test_desktop_api_bridge_estop() -> None:
    """Verify DesktopApiBridge triggers emergency stop on the app."""
    app = UniversalCanDesktopApp(channel="vcan0", bitrate=250000)
    bridge = DesktopApiBridge(app)

    assert app._is_estop is False
    bridge.toggle_simulator()
    assert app._is_simulating is True

    bridge.trigger_estop()

    assert app._is_estop is True
    assert app._is_simulating is False
    assert app._bus_load == 0


def test_desktop_api_bridge_toggle_simulator() -> None:
    """Verify simulator toggle functionality."""
    app = UniversalCanDesktopApp(channel="vcan0", bitrate=250000)
    bridge = DesktopApiBridge(app)

    initial_state = app._is_simulating
    new_state = bridge.toggle_simulator()
    assert new_state != initial_state
    assert app._is_simulating == new_state


def test_desktop_api_bridge_scenario_selection() -> None:
    """Verify setting fault scenarios via bridge."""
    app = UniversalCanDesktopApp(channel="vcan0", bitrate=250000)
    bridge = DesktopApiBridge(app)

    bridge.select_scenario("misfire_p0300")
    assert app._active_scenario == "misfire_p0300"
    assert app._is_estop is False


def test_desktop_api_bridge_settings_update() -> None:
    """Verify updating channel, baudrate, and API key."""
    app = UniversalCanDesktopApp(channel="vcan0", bitrate=250000)
    bridge = DesktopApiBridge(app)

    bridge.save_settings({
        "channel": "can0",
        "baudRate": "500 kbps",
        "apiKey": "test-mock-api-key-12345",
    })

    assert app.channel_name == "can0"
    assert app.bitrate_val == 500000
    assert app.copilot.gemini_api_key == "test-mock-api-key-12345"


def test_desktop_api_copilot_query() -> None:
    """Verify copilot querying through bridge."""
    app = UniversalCanDesktopApp(channel="vcan0", bitrate=250000)
    bridge = DesktopApiBridge(app)

    res = bridge.ask_copilot("P0300")
    assert "P0300" in res
