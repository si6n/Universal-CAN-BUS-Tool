---
title: "AI Prompt Recipes & Copilot Playbooks"
tags:
  - ai-context
  - prompts
  - playbooks
  - copilot
---

# AI Prompt Recipes & Copilot Playbooks

Bu dosya, Universal CAN-Bus Tool projesinde AI araçlarına (Antigravity, Cursor, Claude Code, Copilot, Smart Connections) verebileceğiniz hazır, yüksek verimli prompt kalıplarını içerir.

---

## 🎯 Tarif 1: Yeni Bir OEM J1939 Dekoderi Yazdırma

```markdown
Sen bir Otomotiv Gömülü Sistem Uzmanısın. Universal CAN-Bus Tool projemize yeni bir OEM J1939 dekoderi ekleyeceğiz.

Lütfen `docs/ai_context/01_ARCHITECTURE_AND_LAYERS.md` ve `docs/ai_context/04_OEM_DIAGNOSTICS_MATRIX.md` kurallarına sıkı sıkıya bağlı kalarak:
1. `src/protocols/j1939/oem/[oem_adi].py` dosyasını oluştur.
2. Sinyaller: [Örn: Retarder Torq, DPF Soot Load, DEF Tank Level]
3. Hatalı frame veya veri eksikliğinde exception fırlatmak yerine güvenli fallback (`None` / `SignalQuality.INVALID`) dön.
4. `tests/unit/protocols/test_j1939_oem_[oem_adi].py` altında en az 1 pozitif, 2 negatif/boundary testini pytest ile yaz.
```

---

## 🎯 Tarif 2: Güvenlik & Choke-Point Denetimli Refactor / Özellik Ekleme

```markdown
Projemiz ISO 26262 ASIL-B/D fonksiyonel güvenlik prensipleriyle geliştirilmektedir.
`docs/ai_context/02_FUNCTIONAL_SAFETY_INVARIANTS.md` belgesindeki kuralları oku.

Yapılacak İşlem: [Örn: Yeni bir UDS rutin kontrol servisi ekleme (SID 0x31)]
Zorunluluklar:
- `TxPort` (yani `TxSafetyGateway`) haricinde hiçbir bileşenden doğrudan frame basma.
- E-Stop aktifken veya Watchdog kirası dolmuşken `SafetyViolationError` fırlatıldığını doğrula.
- Zaman hesaplamalarında `time.time()` ASLA kullanma, `time.monotonic()` kullan.
```

---

## 🎯 Tarif 3: CAN Trace Logundan Anomali / Protokol Hata Teşhisi

```markdown
Aşağıdaki CAN bus trace logunu analiz et. 
Projemizdeki `docs/protocols/uds_services_and_nrc_reference.md` ve `docs/protocols/j1939_dm_dtc_reference.md` kurallarına göre:

Log Verisi:
[BURAYA CAN FRAME LOGUNU VEYA HEX VERİLERİNİ YAPIŞTIRIN]

Analiz İsteği:
1. Hangi protokoller ve servisler çağrılmış?
2. Herhangi bir NRC (Negative Response) veya eksik ISO-TP / BAM akış kontrolü var mı?
3. Sinyal değerleri fiziksel birimlere dönüştürüldüğünde anomali tespit ediliyor mu?
```

---

## 🎯 Tarif 4: Hypothesis Property-Based Fuzzer Testi Yazdırma

```markdown
`docs/ai_context/05_TESTING_AND_VERIFICATION.md` kılavuzuna göre:
`[Modül Adı]` için Hypothesis kütüphanesini kullanarak bir property-based fuzzer testi yaz.
- Rastgele bozuk byte dizileri (`st.binary()`) ve sınır CAN ID'leri (`st.integers()`) üret.
- Kodun unhandled exception vermeden güvenli biçimde `PlatformError` döndürdüğünü doğrula.
```
