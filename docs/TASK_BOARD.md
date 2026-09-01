---
title: "Universal CAN-Bus Tool - Task & Milestone Board"
tags:
  - tasks
  - roadmap
  - kanban
---

# 📋 Proje Görev & İzleme Panosu (Task Board)

---

## ⏳ Açık Doğrulama & Geliştirme Görevleri

- [ ] **`secrun scan ./`** — Ortamda secrun kurulu olduğunda son ayak güvenlik taramasını tamamla (`docs/ROADMAP.md`).
- [ ] **RP1210 Saha Doğrulaması:** Gerçek Nexiq/DLA adaptörü ile fiziksel CAN hattında RP1210Bus testi.
- [ ] **K2 Bağımsız E-Stop Doğrulayıcı:** UI'da operatör challenge akışı ve ayrı onay bileşeni entegrasyonu.
- [ ] **K1(b) Lisanslama Denetimi:** Composition root üzerinde lisans kilitleme ürün kararı.

---

## 🎯 Kilometre Taşları Durumu (Milestones)

| Kilometre Taşı | Kapsam | Durum | İlgili Dizin |
|---|---|---|---|
| **M1** | UDS & OBD-II Knowledge Base & Active Poller | 🟢 DONE | `src/protocols/obd/`, `src/protocols/uds/` |
| **M2** | Commercial Vehicle OEM J1939 Decoders | 🟢 DONE | `src/protocols/j1939/oem/` |
| **M3** | Multi-Packet Transport & Auto-Reassembly Pipeline | 🟢 DONE | `src/engine/reassembly.py`, `src/protocols/j1939/transport.py` |
| **M4** | Checksum & Rolling Counter (E2E Safety) | 🟢 DONE | `src/safety/e2e/`, `src/safety/crc/` |
| **M5** | E2E Integration & 1000+ Test Suite (%100 Pass) | 🟢 DONE | `tests/` |
| **M6** | Cloud Client & Resumable Telemetry Upload | 🟢 DONE | `src/cloud/` |
| **M7** | Saha Doğrulaması & Donanım Entegrasyonları (RP1210/Vector) | 🟡 IN PROGRESS | `src/hal/` |
