---
title: "AI Context: Testing & Quality Verification"
tags:
  - ai-context
  - testing
  - pytest
  - hypothesis
  - coverage
  - verification
updated: 2026-09-01
---

# Testing & Quality Verification Context Card

Bu kart, projede yeni kod yazılırken veya refactor yapılırken testlerin nasıl yazılması ve koşturulması gerektiğini belirler.

## 1. Test Piramidi & Standartları

- **Toplam Test Durumu:** 1160+ Test (%100 Pass Oranı).
- **Test Çerçeveleri:** `pytest`, `pytest-cov`, `hypothesis` (Property-based testing).
- **Kod Kalitesi & Linting:** `ruff` (0 hata toleransı).

## 2. Test Kategorileri

| Dizin | Kapsam | Örnek Dosyalar |
|---|---|---|
| `tests/unit/core/` | Core Domain, CanFrame, PlatformError | `test_frame.py`, `test_types.py` |
| `tests/unit/safety/` | Safety Gateway, E-Stop, Watchdog | `test_safety_gateway.py`, `test_estop.py` |
| `tests/unit/protocols/` | J1939 TP, UDS Client, OBD Poller | `test_j1939_transport.py`, `test_uds_client.py` |
| `tests/unit/hal/` | AbstractBus, VirtualBus, RP1210 | `test_virtual_bus.py`, `test_rp1210.py` |
| `tests/property/` | Hypothesis tabanlı rastgele veri fuzzer'ları | `test_crc_properties.py`, `test_buffer_properties.py` |
| `tests/e2e/` | Uçtan uca entegrasyon ve yük testleri | `test_e2e_pipeline.py`, `test_e2e_diagnostics.py` |

## 3. Test Koşturma Komutları

```powershell
# Hızlı birim testleri koşturma
pytest -v -m "not slow"

# Tam test süitini koşturma
pytest -v

# Ruff linter & format kontrolü
ruff check .
ruff format --check .

# Hypothesis property-based testleri
pytest tests/property/
```

## 4. AI İçin Test Kuralları
- Eklenen her yeni özellik için **en az bir pozitif**, **en az iki sınır/hata (boundary & negative)** test senaryosu yazılmalıdır.
- Zaman aşımı içeren testlerde `sleep` kullanılmamalı; `VirtualClock` veya enjekte edilmiş `ClockProvider` mock'lanmalıdır.
