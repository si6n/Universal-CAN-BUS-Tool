"""Native Windows Desktop WebView2 Application Bridge for Universal CAN-Bus Diagnostic v13.0."""

from __future__ import annotations

import math
import sys
import threading
import time
from pathlib import Path
from typing import Any

import webview

from src.core.logging import get_logger
from src.engine.ai.diagnostic_copilot import AiDiagnosticCopilot
from src.hal.drivers.pcan_kvaser import PythonCanBus
from src.safety.estop import EmergencyStopSystem, EStopTriggerSource
from src.safety.gateway import TxSafetyGateway
from src.safety.state_machine import SafetyState, SafetySupervisor
from src.safety.watchdog import TxWatchdogSupervisor

logger = get_logger("app.desktop")


class DesktopApiBridge:
    """Bidirectional API bridge exposed to React JavaScript window via window.pywebview.api."""

    def __init__(self, app: UniversalCanDesktopApp) -> None:
        self.app = app

    def trigger_estop(self) -> None:
        logger.warning("Emergency Stop Triggered from Desktop UI Button!")
        self.app.trigger_estop()

    def toggle_simulator(self) -> bool:
        return self.app.toggle_simulator()

    def select_scenario(self, scenario_name: str) -> None:
        self.app.set_scenario(scenario_name)

    def ask_copilot(self, query: str) -> str:
        return self.app.query_copilot(query)

    def export_logs(self, fmt: str) -> bool:
        return True

    def save_settings(self, settings: dict[str, Any]) -> None:
        self.app.update_settings(settings)

    def heartbeat(self) -> bool:
        """Periodic UI lease heartbeat to satisfy TX Watchdog."""
        self.app.watchdog.heartbeat()
        return True

    def get_safety_state(self) -> str:
        return self.app.supervisor.current_state.value


class UniversalCanDesktopApp:
    """Master native desktop container running the modern React+Tailwind UI with full CAN engine."""

    def __init__(self, channel: str = "vcan0", bitrate: int = 250000) -> None:
        self.channel_name = channel
        self.bitrate_val = bitrate

        # Safety & HAL Architecture
        self.bus = PythonCanBus(interface="virtual", channel=self.channel_name, bitrate=self.bitrate_val)
        self.estop = EmergencyStopSystem()
        self.supervisor = SafetySupervisor(initial_state=SafetyState.STARTUP)
        self.watchdog = TxWatchdogSupervisor(supervisor=self.supervisor, estop=self.estop, timeout_ms=500.0)
        self.gateway = TxSafetyGateway(
            bus=self.bus,
            estop=self.estop,
            supervisor=self.supervisor,
            watchdog=self.watchdog,
        )
        self.copilot = AiDiagnosticCopilot()

        # Initialize to PASSIVE (Listen-Only) by default
        self.supervisor.transition_to(SafetyState.SAFE, reason="Hardware stack initialized")
        self.supervisor.transition_to(SafetyState.PASSIVE, reason="Default PASSIVE listen-only mode active")

        self._is_simulating = False
        self._is_estop = False
        self._active_scenario = "nominal"
        self._sim_time = 0.0
        self._total_packets = 0
        self._bus_load = 0
        self._current_rpm = 0.0
        self._current_boost = 0.0
        self._current_temp = 0.0
        self._window: webview.Window | None = None
        self._thread: threading.Thread | None = None
        self._running = True

    def trigger_estop(self) -> None:
        self._is_estop = True
        self._is_simulating = False
        self._bus_load = 0
        self.estop.trigger(EStopTriggerSource.USER_UI_BUTTON, "Operator Pressed E-STOP")
        self.supervisor.trigger_fault("Operator Pressed E-STOP button in desktop interface")

    def toggle_simulator(self) -> bool:
        if self._is_estop:
            self._is_estop = False
            if self.supervisor.is_fault:
                self.supervisor.transition_to(SafetyState.PASSIVE, reason="Operator resumed simulator in PASSIVE mode")

        self._is_simulating = not self._is_simulating
        if not self._is_simulating:
            self._bus_load = 0
        else:
            self._bus_load = 40
        return self._is_simulating

    def set_scenario(self, scenario: str) -> None:
        self._active_scenario = scenario
        self._is_estop = False

    def query_copilot(self, query: str) -> str:
        dtc_list: list[str] = []
        if self._active_scenario == "misfire_p0300":
            dtc_list.append("P0300")
        elif self._active_scenario == "overboost":
            dtc_list.append("P0234")
        elif self._active_scenario == "overheat":
            dtc_list.append("P0115")
        elif self._active_scenario == "bus_surge":
            dtc_list.append("U0100")

        prompt_res = self.copilot.analyze_live_telemetry(
            rpm=self._current_rpm,
            boost_bar=self._current_boost,
            coolant_temp=self._current_temp,
            dtc_codes=dtc_list,
            user_prompt=query,
        )
        return prompt_res

    def update_settings(self, settings: dict[str, Any]) -> None:
        if "channel" in settings:
            self.channel_name = settings["channel"]
        if "baudRate" in settings:
            try:
                self.bitrate_val = int(settings["baudRate"].split()[0]) * 1000
            except Exception:
                pass
        if "apiKey" in settings and settings["apiKey"]:
            self.copilot.gemini_api_key = settings["apiKey"]

    def _telemetry_loop(self) -> None:
        """High-speed background telemetry loop feeding the frontend."""
        while self._running:
            time.sleep(0.05)
            self.watchdog.heartbeat()

            if not self._is_simulating or self._is_estop:
                continue

            self._sim_time += 0.05
            t = self._sim_time
            self._total_packets += 1

            rpm = 2381.0 + 80.0 * math.sin(t * 0.8) + 30.0 * math.cos(t * 1.5)
            boost = 1.66 + 0.12 * math.sin(t * 0.5) + 0.05 * math.cos(t * 1.1)
            temp = 85.0 + 2.0 * math.sin(t * 0.2)

            if self._active_scenario == "misfire_p0300":
                if math.sin(t * 3.0) > 0.4:
                    rpm -= 300.0
                self._bus_load = 48
            elif self._active_scenario == "overboost":
                boost = 2.45 + 0.2 * math.sin(t * 1.2)
                self._bus_load = 52
            elif self._active_scenario == "overheat":
                temp = 108.5 + 4.0 * math.sin(t * 0.3)
                self._bus_load = 45
            elif self._active_scenario == "bus_surge":
                self._bus_load = 78
            else:
                self._bus_load = 40 + int(3 * math.sin(t))

            self._current_rpm = rpm
            self._current_boost = boost
            self._current_temp = temp

            # Push tick to JavaScript if window is active
            if self._window is not None:
                try:
                    js_code = (
                        f"if (window.onTelemetryTick) window.onTelemetryTick({{"
                        f"timeSec: {t:.2f}, timeFormatted: '{t:.2f}s', rpm: {int(rpm)}, "
                        f"turboBoostBar: {boost:.2f}, coolantTempC: {int(temp)}, "
                        f"oilPressureBar: 4.2, busLoadPercent: {self._bus_load}, errorCount: 0}});"
                    )
                    self._window.evaluate_js(js_code)
                except Exception:
                    pass

    def _resolve_dist_html(self) -> Path:
        """Resolve frontend dist path supporting both raw Python and PyInstaller frozen .EXE bundle."""
        if getattr(sys, "frozen", False):
            base_dir = Path(getattr(sys, "_MEIPASS", sys.executable)).resolve()
            dist_path = base_dir / "src" / "ui" / "frontend" / "dist" / "index.html"
            if dist_path.exists():
                return dist_path

        root_dir = Path(__file__).parent.parent.parent
        return root_dir / "src" / "ui" / "frontend" / "dist" / "index.html"

    def run(self) -> None:
        dist_html = self._resolve_dist_html()

        if not dist_html.exists():
            logger.error(f"Frontend dist not found at {dist_html}. Please run 'npm run build' in src/ui/frontend.")
            return

        api = DesktopApiBridge(self)

        self.watchdog.start()
        self._thread = threading.Thread(target=self._telemetry_loop, daemon=True)
        self._thread.start()

        self._window = webview.create_window(
            title="Universal CAN-Bus Diagnostic & Telemetry Tool v13.0",
            url=str(dist_html.resolve()),
            js_api=api,
            width=1400,
            height=900,
            min_size=(1100, 700),
            background_color="#F8FAFC",
            text_select=True,
        )

        try:
            webview.start(debug=False)
        finally:
            self._running = False
            self.watchdog.stop()
