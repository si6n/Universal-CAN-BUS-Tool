"""Native Windows Desktop WebView2 Application Bridge for Universal CAN-Bus Diagnostic v13.0."""

from __future__ import annotations

import base64
import concurrent.futures
import json
import math
import sys
import threading
import time
from concurrent.futures import TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any

import webview
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.core.errors import PlatformError
from src.core.logging import get_logger
from src.core.models.can_frame import CanFrame, length_to_dlc
from src.engine.ai.diagnostic_copilot import AiDiagnosticCopilot
from src.engine.buffer.ring_buffer import BinaryRingBuffer
from src.engine.router import FrameRouter
from src.hal.drivers.pcan_kvaser import PythonCanBus
from src.protocols.j1939.diagnostics import J1939DiagnosticService
from src.protocols.j1939.transport import J1939TransportProtocol
from src.protocols.nmea2000.fast_packet import Nmea2000FastPacketDecoder
from src.safety.estop import EmergencyStopSystem, EStopTriggerSource
from src.safety.gateway import TxSafetyGateway
from src.safety.secret_provider import get_default_secret_provider
from src.safety.state_machine import SafetyState, SafetySupervisor
from src.safety.watchdog import TxWatchdogSupervisor
from src.security.cloud.client import CloudClient, CloudConfig
from src.security.cloud.license_flow import LicenseFlow
from src.security.cloud.telemetry_uploader import TelemetryUploader, UploadProgress
from src.security.hwid.collector import generate_hardware_fingerprint

logger = get_logger("app.desktop")

DEFAULT_EMBEDDED_CLOUD_PUBLIC_KEY_B64 = "eX3vJQWpo/pKrkpi5Y+f7m5ooUCRbCyY201DTnAjz/Q="


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

    def inject_fault(self, fault_type: str) -> None:
        self.app.inject_fault(fault_type)

    def set_simulation_speed(self, speed: float) -> None:
        self.app.set_simulation_speed(speed)

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

    # ------------------------------------------------------------------
    # Cloud & SaaS Bridge APIs (Universal-CAN-Cloud)
    # ------------------------------------------------------------------
    def cloud_test_connection(self, url: str | None = None, session_token: str | None = None) -> dict[str, Any]:
        try:
            if url:
                self.app.cloud_client.config.base_url = url.rstrip("/")
            resp = self.app.cloud_client.request("GET", "/health", health_endpoint=True)
            if resp.status == 200:
                user_info = None
                if session_token:
                    test_resp = self.app.cloud_client.request(
                        "GET", "/auth/me", extra_headers={"Cookie": f"ucan_session={session_token.strip()}"}
                    )
                    if test_resp.status == 200:
                        user_info = test_resp.json()
                elif self.app.cloud_client.has_session_token():
                    test_resp = self.app.cloud_client.request("GET", "/auth/me")
                    if test_resp.status == 200:
                        user_info = test_resp.json()
                return {"success": True, "status": resp.status, "user": user_info}
            return {"success": False, "error": f"Sağlık kontrolü başarısız (HTTP {resp.status})"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def cloud_save_config(self, url: str, session_token: str | None = None) -> dict[str, Any]:
        try:
            if url:
                self.app.cloud_client.config.base_url = url.rstrip("/")
            if session_token is not None:
                if session_token.strip():
                    self.app.cloud_client.store_session_token(session_token.strip())
                else:
                    self.app.cloud_client.clear_session_token()
            return {"success": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def cloud_get_status(self) -> dict[str, Any]:
        try:
            hwid = generate_hardware_fingerprint()
            has_session = self.app.cloud_client.has_session_token()
            device_token = self.app.cloud_client.get_device_token()
            license_claims = None
            if self.app._secret_provider.has_secret("CLOUD_LICENSE_TICKET") and self.app.license_flow:
                ticket_str = self.app._secret_provider.get_secret("CLOUD_LICENSE_TICKET").decode("utf-8")
                try:
                    claims = self.app.license_flow.verify_cloud_ticket(ticket_str)
                    license_claims = {
                        "licenseId": claims.license_id,
                        "tier": claims.tier,
                        "features": list(claims.features),
                        "expiresAt": claims.expires_at,
                        "offlineUntil": claims.offline_until,
                        "issuedAt": claims.issued_at,
                    }
                except Exception:
                    pass

            return {
                "success": True,
                "baseUrl": self.app.cloud_client.config.base_url,
                "hasSessionToken": has_session,
                "hasDeviceToken": bool(device_token),
                "hwid": hwid,
                "license": license_claims,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def cloud_register_device(self, device_name: str = "Desktop Diagnostic Tool") -> dict[str, Any]:
        try:
            if not self.app.license_flow:
                return {"success": False, "error": "Lisans akışı başlatılamadı"}
            reg = self.app.license_flow.register_device(device_name=device_name)
            return {
                "success": True,
                "deviceId": reg.device_id,
                "resetsRemaining": reg.hwid_resets_remaining,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def cloud_activate_license(self, license_ref: str) -> dict[str, Any]:
        try:
            if not self.app.license_flow:
                return {"success": False, "error": "Lisans akışı başlatılamadı"}
            claims = self.app.license_flow.activate_license(license_ref.strip())
            return {
                "success": True,
                "licenseId": claims.license_id,
                "tier": claims.tier,
                "features": list(claims.features),
                "expiresAt": claims.expires_at,
                "offlineUntil": claims.offline_until,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def cloud_upload_session(self, file_path: str, vehicle_vin: str | None = None) -> dict[str, Any]:
        try:
            result = self.app.telemetry_uploader.upload_file(file_path=file_path, vehicle_vin=vehicle_vin)
            return {
                "success": True,
                "sessionId": result.session_id,
                "status": result.status,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def cloud_upload_raw_content(self, filename: str, content: str, vehicle_vin: str | None = None) -> dict[str, Any]:
        import tempfile
        try:
            with tempfile.NamedTemporaryFile(suffix=f"_{filename}", delete=False, mode="wb") as tf:
                tf.write(content.encode("utf-8"))
                temp_path = tf.name
            try:
                result = self.app.telemetry_uploader.upload_file(file_path=temp_path, vehicle_vin=vehicle_vin)
                return {
                    "success": True,
                    "sessionId": result.session_id,
                    "status": result.status,
                }
            finally:
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except Exception:
                    pass
        except Exception as exc:
            return {"success": False, "error": str(exc)}


class UniversalCanDesktopApp:
    """Master native desktop container running the modern React+Tailwind UI with full CAN engine."""

    def __init__(
        self,
        channel: str = "vcan0",
        bitrate: int = 250000,
        bus: PythonCanBus | None = None,
        interface: str = "virtual",
    ) -> None:
        self.channel_name = channel
        self.bitrate_val = bitrate
        self.interface_val = interface

        # Safety & HAL Architecture
        # F-30: composition root owns exactly ONE bus instance — injected when
        # available, created once otherwise. Settings changes reconnect it.
        # K4-a: rp1210 goes through the RP1210Bus adapter; the rest python-can.
        if bus is not None:
            self.bus = bus
        elif interface == "rp1210":
            from src.main import build_bus

            self.bus = build_bus(interface=interface, channel=channel, bitrate=bitrate)
        else:
            self.bus = PythonCanBus(
                interface=self.interface_val, channel=self.channel_name, bitrate=self.bitrate_val
            )
        self.estop = EmergencyStopSystem()
        self.supervisor = SafetySupervisor(initial_state=SafetyState.STARTUP)
        self.watchdog = TxWatchdogSupervisor(supervisor=self.supervisor, estop=self.estop, timeout_ms=800.0)
        self.gateway = TxSafetyGateway(
            bus=self.bus,
            estop=self.estop,
            supervisor=self.supervisor,
            watchdog=self.watchdog,
        )
        self.copilot = AiDiagnosticCopilot()
        self._secret_provider = get_default_secret_provider()
        # F-32: copilot LLM calls run off the UI/bridge thread
        self._copilot_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="copilot_query"
        )

        # Cloud Subsystem (Universal-CAN-Cloud)
        self._cloud_config = CloudConfig(base_url="http://127.0.0.1:8000")
        self.cloud_client = CloudClient(config=self._cloud_config, secret_provider=self._secret_provider)
        try:
            pub_bytes = base64.b64decode(DEFAULT_EMBEDDED_CLOUD_PUBLIC_KEY_B64)
            self._cloud_pubkey = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
        except Exception:
            self._cloud_pubkey = None
        self.license_flow = LicenseFlow(self.cloud_client, self._cloud_pubkey) if self._cloud_pubkey else None
        self.telemetry_uploader = TelemetryUploader(self.cloud_client, progress_callback=self._on_upload_progress)

        # F-28: real CAN ingestion pipeline — bus -> FrameRouter -> decoders -> UI
        self.router = FrameRouter()
        self.ring_buffer = BinaryRingBuffer()
        self.j1939_tp = J1939TransportProtocol(my_address=0xF9, channel_id=self.channel_name)
        self.n2k_fp = Nmea2000FastPacketDecoder()
        self._rx_sub_id, self._rx_queue = self.router.subscribe(use_queue=True)
        self._last_dm1: dict[str, object] = {}

        # Initialize to PASSIVE (Listen-Only) by default
        self.supervisor.transition_to(SafetyState.SAFE, reason="Hardware stack initialized")
        self.supervisor.transition_to(SafetyState.PASSIVE, reason="Default PASSIVE listen-only mode active")

        self._is_simulating = False
        self._is_estop = False
        self._active_scenario = "nominal"
        self._speed_mult = 1.0
        self._sim_time = 0.0
        self._total_packets = 0
        self._bus_load = 0
        self._error_count = 0
        self._current_rpm = 0.0
        self._current_boost = 0.0
        self._current_temp = 0.0
        self._pack_voltage = 398.4
        self._battery_soc = 78.4
        self._pack_current = 42.5
        self._sog_knots = 18.6
        self._depth_meters = 24.8
        self._propeller_slip = 11.2
        self._window: webview.Window | None = None
        self._thread: threading.Thread | None = None
        self._running = True
        # E14/E15: bridge thread (JS calls) and telemetry thread mutate the
        # same flags and counters — plain `+=` across threads loses updates.
        # One small lock guards writes; reads of single attributes remain
        # lock-free (atomic in CPython).
        self._ui_state_lock = threading.Lock()

    def _on_upload_progress(self, progress: UploadProgress) -> None:
        if self._window is None:
            return
        try:
            progress_data = {
                "sessionId": progress.session_id,
                "totalChunks": progress.total_chunks,
                "uploadedChunks": progress.uploaded_chunks,
                "bytesSent": progress.bytes_sent,
                "totalBytes": progress.total_bytes,
                "percent": progress.percent,
                "status": progress.status,
                "error": progress.error,
            }
            js = f"if (window.onCloudUploadProgress) window.onCloudUploadProgress({json.dumps(progress_data)});"
            self._window.evaluate_js(js)
        except Exception as exc:
            logger.debug("Upload progress UI push failed", extra={"error": str(exc)})

    def _bump_stat(self, attr: str, delta: int) -> None:
        """Thread-safe stat increment (E15)."""
        with self._ui_state_lock:
            setattr(self, attr, getattr(self, attr) + delta)

    def _set_ui_state(self, **kwargs) -> None:  # noqa: ANN001 — narrow helper
        """Thread-safe UI state flag writes (E14)."""
        with self._ui_state_lock:
            for key, value in kwargs.items():
                setattr(self, key, value)

    def trigger_estop(self) -> None:
        self._set_ui_state(_is_estop=True, _is_simulating=False, _bus_load=0)
        self.estop.trigger(EStopTriggerSource.USER_UI_BUTTON, "Operator Pressed E-STOP")
        self.supervisor.trigger_fault("Operator Pressed E-STOP button in desktop interface")

    def toggle_simulator(self) -> bool:
        if self._is_estop:
            # F-17: leaving FAULT requires the cryptographic reset challenge —
            # no tokenless escape hatch.
            # K2 classification: the token is minted and consumed by the same
            # process, so this is a LOCAL RECOVERY flow, not multi-operator
            # authorization. An independent verifier (UI challenge issued by
            # a separate component/operator) is planned.
            token = self.estop.create_reset_token()
            if token is None:
                logger.error("E-Stop reset challenge unavailable; refusing to leave FAULT")
                return self._is_simulating
            self.estop.reset(token)
            self._set_ui_state(_is_estop=False)
            if self.supervisor.is_fault:
                self.supervisor.transition_to(
                    SafetyState.PASSIVE, reason="E-Stop cryptographically reset — PASSIVE"
                )

        # E14: toggle under one lock so two rapid JS clicks cannot read the
        # same stale value and both flip it the same way.
        with self._ui_state_lock:
            self._is_simulating = not self._is_simulating
            self._bus_load = 0 if not self._is_simulating else 40
            return self._is_simulating

    def set_scenario(self, scenario: str) -> None:
        self._active_scenario = scenario
        # Scenario switch may not silently clear a latched E-Stop either (F-17)
        if self._is_estop:
            token = self.estop.create_reset_token()
            if token is None:
                logger.error("E-Stop reset challenge unavailable; refusing to leave FAULT")
                return
            self.estop.reset(token)
        self._set_ui_state(_is_estop=False)

    def set_simulation_speed(self, speed: float) -> None:
        self._set_ui_state(_speed_mult=max(0.25, min(10.0, float(speed))))

    def inject_fault(self, fault_type: str) -> None:
        if fault_type == "error_frame":
            self._bump_stat("_error_count", 5)
        elif fault_type == "wiring_dropout":
            self._bump_stat("_error_count", 12)
            self._set_ui_state(_bus_load=88)

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
        elif self._active_scenario == "ev_bms_telemetry":
            dtc_list.append("P0A0B")
        elif self._active_scenario == "marine_vessel_n2k":
            dtc_list.append("SPN 520201")
        elif self._active_scenario == "j1939_multi_ecu_fleet":
            dtc_list.append("SPN 1087")
        elif self._active_scenario == "can_fd_adas_vision":
            dtc_list.append("C1A00")
        elif self._active_scenario == "intermittent_wiring_fault":
            dtc_list.append("U0100")

        # F-32: the LLM call (urlopen) runs in a dedicated worker with a hard
        # timeout so a slow cloud response can never freeze the JS bridge.
        def _run_query() -> str:
            return self.copilot.analyze_live_telemetry(
                rpm=self._current_rpm,
                boost_bar=self._current_boost,
                coolant_temp=self._current_temp,
                dtc_codes=dtc_list,
                user_prompt=query,
            )

        try:
            return self._copilot_executor.submit(_run_query).result(timeout=15.0)
        except FuturesTimeoutError:
            logger.warning("Copilot query timed out", extra={"query": query[:50]})
            return "⚠️ AI yanıtı zaman aşımına uğradı (15 s). Lütfen tekrar deneyin."

    def update_settings(self, settings: dict[str, Any]) -> None:
        reconnect_needed = False
        if "interface" in settings and settings["interface"] != self.interface_val:
            self.interface_val = settings["interface"]
            reconnect_needed = True
        if "channel" in settings and settings["channel"] != self.channel_name:
            self.channel_name = settings["channel"]
            reconnect_needed = True
        if "baudRate" in settings:
            try:
                new_bitrate = int(settings["baudRate"].split()[0]) * 1000
            except (ValueError, IndexError) as exc:
                logger.warning(
                    "Ignoring unparseable baud rate setting",
                    extra={"value": settings["baudRate"], "error": str(exc)},
                )
            else:
                if new_bitrate != self.bitrate_val:
                    self.bitrate_val = new_bitrate
                    reconnect_needed = True
        if reconnect_needed:
            # F-30: single composition root — the one bus instance is recreated
            # on settings change via reconnect, no second bus is ever created.
            self._reconnect_bus()
        if "apiKey" in settings and settings["apiKey"]:
            # F-08: the key is stored in the secret vault, never a plain attribute
            self._secret_provider.store_secret("GEMINI_API_KEY", settings["apiKey"].encode("utf-8"))
            self.copilot.set_key_provider(self._secret_provider)
        if "cloudBaseUrl" in settings and settings["cloudBaseUrl"]:
            self.cloud_client.config.base_url = settings["cloudBaseUrl"].rstrip("/")
        if "cloudSessionToken" in settings:
            tok = settings["cloudSessionToken"]
            if tok and str(tok).strip():
                self.cloud_client.store_session_token(str(tok).strip())
            elif tok == "":
                self.cloud_client.clear_session_token()

    def _reconnect_bus(self) -> None:
        """Rebind the single bus instance to the new interface/channel/bitrate (F-30).

        Driver validation can reject the new combination as early as the
        constructor (e.g. kvaser demands an integer channel); the previous bus
        stays bound in that case so a bad settings change never kills the app.
        K4-a: rp1210 reconnects through the shared build_bus factory.
        """
        try:
            self.bus.disconnect()
        except (OSError, RuntimeError) as exc:
            logger.debug("Bus disconnect during reconnect failed", extra={"error": str(exc)})
        try:
            if self.interface_val == "rp1210":
                from src.main import build_bus

                new_bus = build_bus(
                    interface=self.interface_val, channel=self.channel_name, bitrate=self.bitrate_val
                )
            else:
                new_bus = PythonCanBus(
                    interface=self.interface_val, channel=self.channel_name, bitrate=self.bitrate_val
                )
        except (OSError, RuntimeError, ValueError, PlatformError) as exc:
            logger.warning(
                "CAN bus reconnect rejected the new settings; keeping previous bus",
                extra={"interface": self.interface_val, "channel": self.channel_name, "error": str(exc)},
            )
            return
        self.bus = new_bus
        self.gateway.bus = self.bus
        try:
            self.bus.connect()
            logger.info(
                "CAN bus reconnected",
                extra={"interface": self.interface_val, "channel": self.channel_name, "bitrate": self.bitrate_val},
            )
        except (OSError, RuntimeError, PlatformError) as exc:
            logger.warning("CAN bus reconnect failed; DEMO-only mode", extra={"error": str(exc)})

    def _decode_j1939_signal(self, frame: object) -> None:
        """Extract live telemetry from a routed J1939 frame (F-28)."""
        try:
            arb = frame.arbitration_id  # type: ignore[attr-defined]
            data = frame.data  # type: ignore[attr-defined]
            pf = (arb >> 16) & 0xFF
            ps = (arb >> 8) & 0xFF
            sa = arb & 0xFF

            # EEC1 (PGN 61444 / PF=0xF0, PS=source): engine speed + torque
            if pf == 0xF0 and ps == 0x04 and len(data) >= 5:
                raw_rpm = data[3] | (data[4] << 8)
                self._current_rpm = raw_rpm * 0.125
            # ET1 (PGN 65249 / PF=0xFE, PS=0xE1): coolant temperature
            elif pf == 0xFE and ps == 0xE1 and len(data) >= 1:
                self._current_temp = float(data[0]) - 40.0
            # DM1 (PGN 65226 / PF=0xFE, PS=0xCA): active diagnostic message
            elif pf == 0xFE and ps == 0xCA and len(data) >= 2:
                dm = J1939DiagnosticService.parse_dm1_or_dm2(
                    bytes(data), pgn=65226, source_address=sa, timestamp_ns=time.time_ns()
                )
                self._last_dm1 = {
                    "source": dm.source_address,
                    "dtc_count": len(dm.dtcs),
                    "lamps": bytes(data[:1]).hex(),
                }
                self._error_count = len(dm.dtcs)
        except (IndexError, ValueError, AttributeError) as exc:
            logger.debug("J1939 live decode failed", extra={"error": str(exc)})

    def _ingest_live_frame(self, frame: object) -> None:
        """Feed one live frame through the router into decoders and UI (F-28)."""
        # Router fans out to protocol engines (J1939 TP, N2K Fast Packet)
        self.router.route_frame(frame)
        self.ring_buffer.append(frame)  # type: ignore[arg-type]
        self._decode_j1939_signal(frame)

        # J1939 transport protocol reassembly (multi-packet)
        completed, _ = self.j1939_tp.handle_rx_frame(frame)  # type: ignore[arg-type]
        if completed is not None:
            # Reassembled payloads can exceed a single CAN frame; cap the
            # synthetic frame at 64 bytes with a valid DLC so oversized
            # messages can never crash the telemetry thread.
            synth_data = completed.data[:64]
            try:
                synth_frame: CanFrame | None = CanFrame(
                    channel_id=completed.channel_id,
                    arbitration_id=((completed.pgn << 8) | completed.source_address) & 0x1FFFFFFF,
                    dlc=length_to_dlc(len(synth_data)),
                    data=synth_data,
                    is_extended=True,
                )
            except ValueError as exc:
                logger.debug("Synthetic reassembly frame rejected", extra={"error": str(exc)})
                synth_frame = None
            if synth_frame is not None:
                self._decode_j1939_signal(synth_frame)

        # N2K Fast Packet reassembly — PGN 127488 engine rapid / 128267 depth
        n2k_msg = self.n2k_fp.handle_rx_frame(frame)  # type: ignore[arg-type]
        if n2k_msg is not None:
            if n2k_msg.pgn == 127488 and len(n2k_msg.data) >= 3:
                self._current_rpm = float(int.from_bytes(n2k_msg.data[1:3], "little")) * 0.25
            elif n2k_msg.pgn == 128267 and len(n2k_msg.data) >= 5:
                self._depth_meters = int.from_bytes(n2k_msg.data[1:5], "little") * 0.01

        self._bump_stat("_total_packets", 1)

    def _push_frames_to_ui_batch(self, frames: list[object]) -> None:
        """Stream a tick's frames to the frontend in ONE evaluate_js call (E13).

        Per-frame JS evaluation (up to 200 frames / 50 ms tick) flooded the
        WebView2 bridge; batching mirrors the frontend's own F-35 pattern
        (single state update per batch). Falls back to nothing on a closed
        window; each frame's payload is json.dumps-escaped (E2).
        """
        if self._window is None or not frames:
            return
        payloads: list[str] = []
        for frame in frames:
            try:
                data_hex = bytes(frame.data).hex()  # type: ignore[attr-defined]
                payloads.append(
                    json.dumps(
                        {
                            "id": f"0x{frame.arbitration_id:03X}",  # type: ignore[attr-defined]
                            "timestamp": round((frame.timestamp_ns or 0) / 1e9,  # type: ignore[attr-defined]
                                                3),
                            "channel": frame.channel_id,  # type: ignore[attr-defined]
                            "dlc": frame.dlc,  # type: ignore[attr-defined]
                            "data": data_hex,
                            "isExtended": frame.is_extended,  # type: ignore[attr-defined]
                            "isFd": frame.is_fd,  # type: ignore[attr-defined]
                            "source": getattr(frame, "source", "physical"),
                        }
                    )
                )
            except (AttributeError, OSError, RuntimeError) as exc:
                logger.debug("Frame serialization for UI batch failed", extra={"error": str(exc)})
        if not payloads:
            return
        batch_js = "[" + ",".join(payloads) + "]"
        try:
            self._window.evaluate_js(f"if (window.onNewCanFrames) window.onNewCanFrames({batch_js});")
        except (AttributeError, OSError, RuntimeError) as exc:
            logger.debug("Batched frame UI push failed", extra={"error": str(exc)})

    def _telemetry_loop(self) -> None:
        """Background loop: live CAN ingestion when connected, synthetic values in DEMO mode.

        Live path (F-28): bus -> FrameRouter -> decoders (J1939 / N2K) -> JS bridge.
        The watchdog heartbeat is NOT driven from here (F-16/E-11): the UI
        lease is only refreshed by the frontend render/rAF pulse.
        """
        while self._running:
            time.sleep(0.05 / max(0.5, self._speed_mult))

            if self._is_estop:
                continue

            # ── LIVE path: real frames off the bus (F-28) ──────────────
            if not self._is_simulating:
                drained = 0
                tick_frames: list[object] = []
                while drained < 200:
                    frame = self.bus.recv(timeout_s=0.01)
                    if frame is None:
                        break
                    self._ingest_live_frame(frame)
                    tick_frames.append(frame)
                    drained += 1
                if drained == 0:
                    continue
                # E13: one JS evaluation per tick for the whole batch
                self._push_frames_to_ui_batch(tick_frames)
                # Live bus load estimate from routed frame rate
                self._bus_load = min(100, int(drained / 2))
                self._push_telemetry_tick()
                continue

            # ── DEMO path: synthetic scenario values (F-29: single module) ──
            self._sim_time += 0.05 * self._speed_mult
            t = self._sim_time
            self._bump_stat("_total_packets", 1)

            rpm = 2381.0 + 80.0 * math.sin(t * 0.8) + 30.0 * math.cos(t * 1.5)
            boost = 1.66 + 0.12 * math.sin(t * 0.5) + 0.05 * math.cos(t * 1.1)
            temp = 85.0 + 2.0 * math.sin(t * 0.2)
            pack_volt = 398.4
            soc = 78.4
            current = 42.5
            sog = 18.6
            depth = 24.8
            slip = 11.2

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
                self._bus_load = 84
            elif self._active_scenario == "ev_bms_telemetry":
                current = 45.0 + 35.0 * math.sin(t * 1.5)
                pack_volt = 398.0 - (current * 0.08)
                soc = 78.4 - (t * 0.01)
                self._bus_load = 34
            elif self._active_scenario == "marine_vessel_n2k":
                sog = 18.6 + 2.0 * math.sin(t * 0.5)
                depth = 24.8 + 5.0 * math.sin(t * 0.1)
                slip = 11.2 + math.sin(t * 0.2) * 2.0
                self._bus_load = 38
            elif self._active_scenario == "can_fd_adas_vision":
                self._bus_load = 58
            elif self._active_scenario == "intermittent_wiring_fault":
                self._bus_load = 78
                if math.sin(t * 2.0) > 0.6:
                    self._bump_stat("_error_count", 1)
            else:
                self._bus_load = 40 + int(3 * math.sin(t))

            self._current_rpm = rpm
            self._current_boost = boost
            self._current_temp = temp
            self._pack_voltage = pack_volt
            self._battery_soc = soc
            self._pack_current = current
            self._sog_knots = sog
            self._depth_meters = depth
            self._propeller_slip = slip

            self._push_telemetry_tick()

    def _push_telemetry_tick(self) -> None:
        """Push the current telemetry snapshot to the frontend (F-28)."""
        if self._window is None:
            return
        t = self._sim_time
        try:
            js_code = (
                f"if (window.onTelemetryTick) window.onTelemetryTick({{"
                f"timeSec: {t:.2f}, timeFormatted: '{t:.2f}s', rpm: {int(self._current_rpm)}, "
                f"turboBoostBar: {self._current_boost:.2f}, coolantTempC: {int(self._current_temp)}, "
                f"oilPressureBar: 4.2, busLoadPercent: {self._bus_load}, errorCount: {self._error_count}, "
                f"packVoltageV: {self._pack_voltage:.1f}, batterySocPercent: {self._battery_soc:.1f}, packCurrentA: {self._pack_current:.1f}, "
                f"sogKnots: {self._sog_knots:.1f}, depthMeters: {self._depth_meters:.1f}, propellerSlipPct: {self._propeller_slip:.1f}}});"
            )
            self._window.evaluate_js(js_code)
        except (AttributeError, OSError, RuntimeError) as exc:
            logger.warning(
                "Frontend telemetry push failed",
                extra={"error": str(exc)},
            )

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
        # F-28: connect the real CAN bus before the ingestion loop starts
        try:
            self.bus.connect()
            logger.info("CAN bus connected for live ingestion", extra={"channel": self.channel_name})
        except (OSError, RuntimeError) as exc:
            logger.warning("CAN bus connect failed; running in DEMO-only mode", extra={"error": str(exc)})

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
            self._set_ui_state(_running=False)
            self.watchdog.stop()
