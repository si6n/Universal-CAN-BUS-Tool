# E2E Test Infra: Universal CAN-Bus Diagnostic & Telemetry Tool

## Test Philosophy
- Opaque-box, requirement-driven testing ensuring reliability across safety-critical CAN bus telemetry and diagnostics.
- Methodology: Category-Partition + Boundary Value Analysis (BVA) + Pairwise Combinatorial Testing + Real-World Workload Scenarios.

## Feature Inventory & Test Coverage Matrix
| # | Feature | Source | Tier 1 (Coverage) | Tier 2 (Boundary) | Tier 3 (Cross-Feature) | Tier 4 (Workload) |
|---|---------|--------|:-----------------:|:-----------------:|:----------------------:|:-----------------:|
| 1 | HWID Generation & Collector | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 2 | License Validation & HWM | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 3 | HMAC-SHA256 E-Stop Token | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 4 | UDS Non-Blocking Client | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 5 | DBC Decoder Length Check & LRU | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 6 | TxSafetyGateway Deque Limiter | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 7 | BinaryRingBuffer Low Contention | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 8 | ReplayBus High-Precision Timing | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 9 | BusMetrics.state Enum | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | ✓ |
| 10 | AI Copilot Markdown Parser | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | ✓ |
| 11 | Demo Frame Source Tagging | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | ✓ |

## Test Architecture
- Test Runner: `pytest` (`python -m pytest tests/ -v`)
- Static Checkers: `ruff` (`python -m ruff check .`), `mypy` (`python -m mypy src/ --strict`)
- Coverage Thresholds:
  - 100% pytest pass rate
  - 0 ruff errors
  - 0 mypy strict errors

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Expected Outcome |
|---|----------|--------------------|------------------|
| 1 | High-speed Telemetry Streaming | RingBuffer, DBC Decoder, BusMetrics, Virtual Driver | Zero frame drops, valid signal extraction without corrupted padding |
| 2 | Safety Gateway Emergency Trip | TxSafetyGateway, E-Stop Interlock, HMAC Reset | Immediate TX cutoff, valid HMAC reset restoration |
| 3 | UDS Diagnostic Session with Live CAN | UDS Client Async, ISO-TP, Virtual Driver | Async routine completes without blocking background bus RX |
| 4 | Replay Trace Timing Fidelity | ReplayBus, BinaryRingBuffer, BusMetrics | Microsecond-accurate playback matching trace timestamps |
| 5 | AI Copilot Diagnosis Under Markdown Output | AiDiagnosticCopilot, Local Expert Fallback | Robust markdown code block handling and structured diagnosis output |
