# E2E Test Infra: Phase 2 Functional Safety

## Test Philosophy
- Opaque-box, requirement-driven derived from `ORIGINAL_REQUEST.md`.
- Methodology: Category-Partition + Boundary Value Analysis (BVA) + Pairwise Combinatorial + Real-World Application Workloads.

## Feature Inventory
| # | Feature | Source (requirement) | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---------|---------------------|:------:|:------:|:------:|:------:|
| 1 | CAN-02 TxPort & UDS Gateway | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 2 | CAN-05 SecretProvider & E-Stop | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 3 | CAN-06 Fail-Closed Whitelist | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | ✓ |
| 4 | CAN-12 Deadlock-Free State Machine | ORIGINAL_REQUEST §R4 | 5 | 5 | ✓ | ✓ |
| 5 | CAN-24/25 Rule Ordering & Monotonic Clocks | ORIGINAL_REQUEST §R5 | 5 | 5 | ✓ | ✓ |

## Test Architecture
- Test Runner: `pytest`
- Execution: `pytest tests/e2e/test_phase2_*.py`
- Invariant Testing: Timing attacks on HMAC, reentrancy deadlocks, replay token rejection, speed interlock precedence over dual confirmation, fail-closed empty whitelist.

## Coverage Goals
- Tier 1: ≥5 happy-path test cases per feature (Total ≥ 25)
- Tier 2: ≥5 boundary/edge cases per feature (Total ≥ 25)
- Tier 3: Pairwise cross-feature interactions (Total ≥ 10)
- Tier 4: Real-world vehicle diagnostic telemetry scenarios (Total ≥ 5)
- Total E2E Tests: ≥ 65 tests
