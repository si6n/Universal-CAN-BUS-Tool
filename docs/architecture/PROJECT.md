# Project: Universal CAN-Bus Diagnostic & Telemetry Tool

## Architecture
The Universal CAN-Bus Diagnostic & Telemetry Tool is a multi-tier, high-reliability Python application designed for automotive telemetry, CAN bus diagnostics (UDS, OBD-II), safety-critical TX interlocks, hardware license binding, and AI-assisted troubleshooting.

### Subsystem Boundaries:
- **`src/hal/`**: Hardware Abstraction Layer for virtual, socketcan, PCAN, Kvaser, RP1210, and Replay transceivers.
- **`src/protocols/`**: ISO-TP (ISO 15765-2), UDS (ISO 14229-1), and OBD-II protocol engines.
- **`src/engine/`**: High-performance telemetry buffer (`BinaryRingBuffer`), DBC decoder, signal extraction, statistics, and AI copilot.
- **`src/safety/`**: Hardware E-Stop interlock, HMAC-SHA256 reset token validation, `TxSafetyGateway` rate-limiting, and payload safety firewalls.
- **`src/security/`**: 4-factor hardware fingerprinting (`hwid`), cryptographic license validation, and anti-tamper clock high-water mark protection.
- **`src/ui/`**: PySide6 dark-theme automotive diagnostic desktop GUI.

---

## Feature Inventory
Every feature from user requirements is mapped below to its assigned milestone:

| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | HWID Collection & WMI Fix | 4-factor hardware fingerprinting with robust PowerShell WMI disk query | M1 | R1 |
| 2 | License Validation Wiring | Wire HWID into LicenseValidator with default fingerprinting & time testability | M1 | R1 |
| 3 | Anti-Clock High-Water Mark | Monotonic and disk-persisted HWM drift detection & anti-rollback | M1 | R1 |
| 4 | HMAC-SHA256 E-Stop Reset | Cryptographic emergency stop token verification and replay prevention | M1 | R1 |
| 5 | Non-Blocking UDS Client | ThreadPoolExecutor async worker execution for diagnostic routines | M2 | R2 |
| 6 | DBC Decoder Length Check & LRU | Reject truncated frames without corrupt padding + LRU cache bounding | M2 | R2 |
| 7 | TxSafetyGateway Deque Optimization | O(1) sliding window rate limiter with deque and thread synchronization | M2 | R2 |
| 8 | BinaryRingBuffer Lock Contention | Zero-allocation append & two-phase lock-free object instantiation | M2 | R2 |
| 9 | ReplayBus High-Precision Timer | Master-clock time.perf_counter hybrid sleep/spinloop with timeBeginPeriod | M2 | R2 |
| 10 | BusMetrics.state Enum | Standardized `BusState(str, Enum)` across HAL base and drivers | M3 | R3 |
| 11 | AI Copilot Markdown Parser | Robust json parsing handling markdown blocks (```json ... ```) | M3 | R3 |
| 12 | Demo Simulator Frame Tagging | Explicitly tag demo/sim frames with `source="virtual"` | M3 | R3 |
| 13 | Pyproject & Linter/Type Config | pyproject.toml configuration for pytest, ruff, mypy strict | M3 | R3 |
| 14 | Pytest Full Suite Verification | 100% test pass rate across 220 unit, integration, and stress tests | M4 | R4 |
| 15 | Static Analysis Cleanliness | 0 ruff lint errors and 0 mypy strict type errors across 74 files | M4 | R4 |
| 16 | Forensic Integrity Audit | Independent verification of authentic implementation without dummy facades | M4 | R4 |

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Security & Identity Refinements | HWID collector, license validator wiring, anti-tamper HWM, E-Stop HMAC verification, dedicated tests | None | DONE |
| 2 | Performance & Protocol Reliability | UDS async worker, DBC length check & LRU, Gateway deque, RingBuffer low-contention, ReplayBus high precision | None | DONE |
| 3 | Code Quality & Standards Alignment | BusState Enum, AI Copilot json parser, demo frame tagging, pyproject.toml, strict mypy/ruff clean | None | DONE |
| 4 | Test Suite & Forensic Gate | Full test suite execution (220 tests), static verification, forensic integrity audit | M1, M2, M3 | DONE |

---

## Interface Contracts

### Security ↔ License
```python
# src/security/hwid/collector.py
def generate_hardware_fingerprint() -> str: ...
def collect_disk_serial() -> str: ...
def collect_motherboard_uuid() -> str: ...
def collect_cpu_id() -> str: ...
def collect_primary_mac() -> str: ...


# src/security/license/validator.py
class LicenseValidator:
    def __init__(
        self,
        public_key_pem: bytes | None = None,
        hardware_fingerprint: str | None = None,
        hwm_file_path: Path | str | None = None,
        boot_realtime: int | None = None,
        boot_monotonic: float | None = None,
    ) -> None: ...
```

### Protocol ↔ UI
```python
# src/protocols/uds/client.py
class UdsClient:
    def execute_async(
        self,
        routine_func: Callable[..., Any],
        *args: Any,
        callback: Callable[[Any], None] | None = None,
        error_callback: Callable[[Exception], None] | None = None,
        **kwargs: Any,
    ) -> Future[Any]: ...
```

### HAL ↔ Metrics
```python
# src/hal/base.py
class BusState(str, Enum):
    ACTIVE = "active"
    PASSIVE = "passive"
    BUS_OFF = "bus_off"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class BusMetrics:
    state: BusState = BusState.ACTIVE
```

---

## Code Layout
```
Universal CAN-Bus Diagnostic & Telemetry Tool/
├── pyproject.toml
├── PROJECT.md
├── src/
│   ├── hal/
│   │   ├── base.py
│   │   ├── drivers/
│   │   │   ├── pcan_kvaser.py
│   │   │   └── virtual.py
│   │   ├── replay/
│   │   │   └── player.py
│   │   └── rp1210/
│   ├── protocols/
│   │   └── uds/
│   │       └── client.py
│   ├── engine/
│   │   ├── buffer/
│   │   │   └── ring_buffer.py
│   │   ├── decoder/
│   │   │   └── dbc_decoder.py
│   │   └── ai/
│   │       └── diagnostic_copilot.py
│   ├── safety/
│   │   ├── estop.py
│   │   └── gateway.py
│   ├── security/
│   │   ├── anti_tamper/
│   │   ├── hwid/
│   │   │   ├── __init__.py
│   │   │   └── collector.py
│   │   └── license/
│   │       └── validator.py
│   └── ui/
└── tests/
    └── unit/
        ├── test_hwid.py
        ├── test_estop.py
        ├── test_license_validator.py
        ├── test_uds_client.py
        ├── test_dbc_decoder.py
        ├── test_safety_gateway.py
        ├── test_ring_buffer.py
        ├── test_replay_bus.py
        ├── test_ai_copilot.py
        ├── test_hal.py
        ├── test_adversarial_challenger2.py
        └── test_adversarial_stress.py
```
