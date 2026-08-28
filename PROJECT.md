# Project: Universal CAN-Bus Diagnostic & Telemetry Tool — Phase 2 Architecture & Plan

## Architecture
Phase 2 Functional Safety & Architectural Hardening enforces strict choke-points, fail-closed security invariants, cross-platform cryptographic key storage, replay-protected emergency stops, deadlock-free concurrency, and monotonic clock separation.

- **HAL Layer (`src/hal/`)**: `AbstractBus` encapsulates raw bus transmissions (`_send_raw()`). `TxPort` protocol provides the safe transmission interface.
- **Safety Subsystem (`src/safety/`)**:
  - `TxSafetyGateway`: Implements `TxPort`, enforces 6-stage rule evaluation pipeline (Sanity -> State/EStop -> Whitelist -> Speed Interlock -> Dual Confirmation -> Rate Budget). Fail-closed whitelist by default.
  - `SecretProvider` (`src/safety/secret_provider.py`): Platform-adaptive secret storage (Windows DPAPI with fallback, Linux 0600 keyfile, Ephemeral in-memory).
  - `EmergencyStopSystem` (`src/safety/estop.py`): Cryptographic challenge-response reset tokens `(epoch, nonce, timestamp_monotonic_ns, action, hmac)` using `hmac.compare_digest` with anti-replay cache.
  - `SafetySupervisor` / `SafetyStateMachine` (`src/safety/state_machine.py`): Reentrant lock, snapshot-then-release callback dispatch, exception isolation, monotonic epoch counter.
- **Protocols Layer (`src/protocols/uds/`)**: `UdsClient` depends strictly on `TxPort`. No direct bus access.
- **Clock Specialization**: `time.monotonic_ns()` for all state durations, timers, staleness, rate limits. `datetime.now(timezone.utc)` strictly for audit/log forensics.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | CAN-02 TxPort Choke-Point | AbstractBus._send_raw() protection, TxPort protocol, UdsClient dependency inversion | M1 | ORIGINAL_REQUEST R1 |
| 2 | CAN-05 SecretProvider & E-Stop | Dynamic SecretProvider (DPAPI/Linux/Ephemeral), E-Stop replay protection, structured tokens | M2 | ORIGINAL_REQUEST R2 |
| 3 | CAN-06 Fail-Closed Whitelist | Empty whitelist rejects transmissions (WHITELIST_FAIL_CLOSED), allow_all_for_testing flag | M3 | ORIGINAL_REQUEST R3 |
| 4 | CAN-12 Deadlock-Free Dispatch | Snapshot-then-release in _force_fault/transition_to, callback exception isolation, state epoch | M4 | ORIGINAL_REQUEST R4 |
| 5 | CAN-24 Safety Rule Ordering | Strict 6-stage order: Sanity -> State/EStop -> Whitelist -> Speed -> DualConfirm -> RateBudget | M5 | ORIGINAL_REQUEST R5 |
| 6 | CAN-25 Clock Specialization | Monotonic clocks for durations/staleness/budgets vs UTC wall-clock for audit logging | M5 | ORIGINAL_REQUEST R5 |
| 7 | Comprehensive E2E Test Suite | 4-tier requirement-driven opaque-box test suite (Tiers 1-4) | E2E-Track | ORIGINAL_REQUEST All |
| 8 | Tier 5 Adversarial Hardening | White-box stress testing, reentrancy attacks, timing attacks, replay attacks | M6 | ORIGINAL_REQUEST All |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | R1: TxPort & UDS Gateway (CAN-02) | `src/hal/base.py`, `src/hal/tx_port.py`, `src/protocols/uds/client.py`, `src/safety/gateway.py` | None | IN_PROGRESS |
| M2 | R2: SecretProvider & E-Stop Hardening (CAN-05) | `src/safety/secret_provider.py`, `src/safety/estop.py` | None | IN_PROGRESS |
| M3 | R3: Fail-Closed Whitelist (CAN-06) | `src/safety/gateway.py`, `src/safety/exceptions.py` | M1 | PLANNED |
| M4 | R4: Deadlock-Free Callback Dispatch (CAN-12) | `src/safety/state_machine.py` | None | IN_PROGRESS |
| M5 | R5: Rule Ordering & Monotonic Clocks (CAN-24, CAN-25) | `src/safety/gateway.py`, `src/safety/state_machine.py`, `src/telemetry/` | M1, M3, M4 | PLANNED |
| E2E | E2E Testing Suite (Tiers 1-4) | `tests/e2e/test_phase2_*.py`, `TEST_READY.md` | None | IN_PROGRESS |
| M6 | Final Verification, Tier 5 Hardening & Forensic Audit | Full test suite, adversarial tests, ruff, mypy, clean audit | M1-M5, E2E | PLANNED |

## Interface Contracts
### `TxPort` Protocol (`src/hal/tx_port.py` or `src/hal/base.py`)
```python
class TxPort(Protocol):
    async def send(self, frame: CanFrame) -> bool: ...
    def send_sync(self, frame: CanFrame) -> bool: ...
```

### `SecretProvider` (`src/safety/secret_provider.py`)
```python
class SecretProvider(ABC):
    @abstractmethod
    def get_secret(self, key_name: str) -> bytes: ...
    @abstractmethod
    def store_secret(self, key_name: str, secret: bytes) -> None: ...
```

### `EmergencyStopToken` (`src/safety/estop.py`)
```python
@dataclass(frozen=True)
class EmergencyStopToken:
    epoch: int
    nonce: str
    timestamp_monotonic_ns: int
    action: str
    signature: str  # HMAC-SHA256 hex
```

## Code Layout
- `src/hal/base.py` — `AbstractBus` base with `_send_raw()` protected method
- `src/hal/tx_port.py` — `TxPort` protocol definition
- `src/hal/virtual.py`, `can_interface.py` — Concrete bus implementations of `_send_raw()`
- `src/safety/secret_provider.py` — `SecretProvider` interface and backends
- `src/safety/estop.py` — Dynamic secret & replay-protected `EmergencyStopSystem`
- `src/safety/gateway.py` — `TxSafetyGateway` implementing `TxPort`, 6-stage rule ordering, fail-closed whitelist
- `src/safety/state_machine.py` — `SafetySupervisor` / `SafetyStateMachine` with snapshot-then-release & monotonic epoch
- `src/protocols/uds/client.py` — `UdsClient` taking `tx_port: TxPort`
