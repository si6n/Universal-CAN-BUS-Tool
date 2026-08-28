# Changelog

All notable changes to the **Universal CAN-Bus Diagnostic & Telemetry Platform** are documented here.

## [Unreleased]
### Security
- **BREAKING (CAN-02 / FAZ 0-1):** `AbstractBus.send()` removed. The HAL transmission
  primitive is now the abstract `_send_raw()`, reachable only through
  `TxSafetyGateway`, closing the bypass that let UDS, the demo simulator, the GUI and
  replay callers transmit around the 6-stage safety pipeline. Buses without a TX
  primitive now fail at construction time instead of failing open at first transmission.
- **K-04:** `UdsClient` no longer auto-constructs an `allow_all_for_testing` gateway;
  a raw bus is wrapped in a fail-closed gateway whitelisted to the client's own `tx_id`.
- **K-01:** `SafeMultiplexedBus._send_raw()` fails closed with `PermissionError` — the
  application-layer adapter has no physical TX capability.
- **K-16:** `scripts/demo_traffic_generator.py` routes every transmission through
  `TxSafetyGateway` with an explicit ID whitelist, a PASSIVE->ARMED_TX arming ladder,
  source-side pacing below the gateway budget, and `source="demo"` tagging (Invariant 5).
- **Invariant 4:** `main.py --cli` opens the interface in listen-only (PASSIVE) mode;
  the CLI has no TX path at all.

### Fixed
- `--interface` was silently dropped by the desktop GUI and CLI window (a user selecting
  `--interface pcan` got a virtual bus while believing they were on hardware).
- **H-29:** monotonic duration tests no longer depend on host clock granularity. CI
  runners (Hyper-V emulated QPC, ~15.6 ms ticks) observed a 10 ms sleep as `0 ns`, which
  failed two tests. `tests/conftest.py::monotonic_clock` now drives those assertions.
- **K-17:** CI actions are pinned to full commit SHAs, workflow token permissions are
  reduced to `contents: read`, and `fail-fast: false` keeps both matrix jobs reporting.

### Code Review Cleanup (S-5, S-8, S-3/S-10, SP-7, SP-9)
- **S-5:** `BusMetrics.state` is now a `BusState` invariant — the `| str` escape hatch
  is gone. `PythonCanBus` assigns enum members instead of raw strings, and its python-can
  `BusState` import no longer shadows the platform enum (`CanLibBusState` alias).
- **SP-7:** `EStopEvent` gains `wall_time_utc` (UTC `datetime` mirror of `timestamp_ns`)
  so E-Stop audit records use the same `datetime.now(timezone.utc)` format as the
  safety state machine's fault history.
- **SP-9:** `UdsClient` dispatches on the new explicit `ValidatedTxPort` Protocol via
  `isinstance()` instead of probing undocumented attributes with `hasattr()`.
  `ValidatedTxPort` extends `TxPort` with the gateway's `validate_and_transmit()`
  contract in `src/core/contracts/ports.py`.
- **S-8:** the desktop telemetry loop serializes the JS push payload with `json.dumps`
  instead of hand-built f-string JS literals, removing the code-injection surface in
  `evaluate_js`.
- **S-3/S-10:** removed the middle-man re-export modules `src/hal/tx_port.py` and
  `src/hal/can_interface.py`; consumers use the canonical `src/core/contracts/ports.py`
  and `src/hal/__init__.py` exports (PROJECT.md updated accordingly).

## [13.0.0] - 2026-08-26
### Added
- **Formal Safety State Machine**: Fail-Silent and Safe-by-Default architecture (`STARTUP` -> `SAFE` -> `PASSIVE` -> `ARMED_TX` -> `ACTIVE` -> `FAULT`).
- **500 ms Monotonic TX Watchdog Supervisor**: Monotonic heartbeat lease with automatic E-Stop and queue revocation.
- **Speed Interlock & TX Safety Gateway**: Hardware/Software interlock (>0.5 km/h lock, 100 msg/s sliding-window rate limiter).
- **SAE J1939-21/71/73/81 Complete Stack**: BAM, RTS/CTS CMDT, DM1..DM11, Dynamic 64-bit Address Claiming.
- **ISO 14229 UDS & ISO 15765-2 DoCAN**: Single/Multi-Frame segmentation, 10-step ECU Bootloader & Flashing Engine.
- **NMEA 2000 Fast Packet**: 223-byte multi-frame reassembly (ISO 11783-3) and marine engine/transmission PGN library.
- **Volvo Penta EDC / EVC**: MID 128 (PID/SID/PPID/PSID) and EVC PGN 65360/65361 telemetry.
- **Evidence-Based Reverse Engineering Engine**: Pearson $r > 0.85$, Spearman $\rho$, Time-Lag, and automatic DBC generation.
- **NumPy Pre-Allocated Ring Buffer**: 300,000 frames binary circular buffer (28 MB RAM, zero GC latency).
- **Ed25519 Cryptographic Licensing**: 7-day offline grace period, Anti-Clock Rollback, Win32 CIM HWID.
- **Native Desktop WebView2 GUI**: React 18 + TypeScript + Tailwind CSS 60 FPS Oscilloscope.
