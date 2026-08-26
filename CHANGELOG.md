# Changelog

All notable changes to the **Universal CAN-Bus Diagnostic & Telemetry Platform** are documented here.

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
