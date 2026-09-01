# Kalan İşler — Universal CAN-Bus Tool

> **Durum baz tarihi:** 2026-09-01 · 1163/1163 test PASSED · ruff 0 hata · 19 commit
> Bu dosya, tamamlanmış kapsamlı review + düzeltme dalgalarının (78 bulgu, P0/P1/P2
> protokol düzeltmeleri, Dalga 1-5, K1-K4, "Küçükler" grubu, RP1210/CSV entegrasyonu,
> gateway lock-scope refactor, Hypothesis property süiti) ardından **hâlâ açık** olan
> işlerin tek kaynağıdır. Bir kalem tamamlandığında bu dosyadan düşürülür.

---

## 1. Devam Eden — Paralel Oturum Sahipliğinde (dokunma!)

### K1(a) — Bulut/Lisans UI Entegrasyonu (ÇALIŞMA AĞACINDA, COMMIT EDİLMEDİ)
- **Dosyalar:** `src/ui/desktop_app.py`, `src/ui/frontend/src/components/modals/SettingsModal.tsx`,
  `src/ui/frontend/src/components/reports/ReportsExportView.tsx`, `src/ui/frontend/src/services/bridge.ts`
- **İçerik:** CloudClient/LicenseFlow/TelemetryUploader bridge API'leri + Settings/Reports
  modallarında bulut SaaS akışları (~1000 satır)
- **NOT:** Bu işin sahibi kullanıcı/paralel oturum — **başka bir oturum bu dosyalara
  dokunmamalı.** Bitince devralınıp doğrulanacak:
  - [ ] Ruff'ta 3 hata var (unsorted import bloğu + 2 kullanılmayan import:
    `LicenseError`, `SecurityError` — `desktop_app.py`) → temizlenecek
  - [ ] Tam süit + ruff yeşil → kendi dürüst commit'i
  - [ ] Bulut yolunda `H1 cihaz bağı` denetimi: `license_flow.py` `data["device_id"]`'yi
    HWID ile karşılaştırmıyor — UI bağlanırken bu zaafın kapatılması değerlendirilmeli

---

## 2. Teknik Kalemler (herhangi bir oturum alabilir)

### K3(b) — BLF Replay Ayrıştırıcısı (son replay formatı)
- **Yerde:** `src/hal/replay/parsers.py` + `player.py`
- **Çözüm:** Bağımlılıktaki `python-can` zaten BLF okuyabiliyor — `can.BLFReader` ile
  frame yineleme, mevcut `CanFrame` modeline çeviri (~50 satır). Baştan format
  reverse-engineer ETMEMEK için özellikle not: `python-can`'ın kendi BLF implementasyonu
  kullanılır.
- **Uzantı kablolaması:** `ReplayBus.from_trace_file` zaten hazır — `.blf` dalı eklenir,
  şu anki `ValueError` kaldırılır.
- **Testler:** örnek BLF bytes'i ile (python-can kendi test asset'lerinden üretilir)
  roundtrip + bozuk dosya dayanıklılığı
- **README:** ReplayBus satırında "BLF henüz yok" notu güncellenir.

### DBC Decoder — Kalıcı Sinyal Cache Temizliği (küçük)
- **Yerde:** `src/engine/decoder/dbc_decoder.py` — `add_dbc_file` artık üç cache'i de
  temizliyor (E8 kapandı), ancak `from_dbc_file`/`from_dbc_string` her seferinde yeni
  instance ürettiği için sorun yok. Kalan tek nokta: `_get_signal_metadata` anahtarı
  `id(msg_def)` — GC sonrası ID yeniden kullanımı teorik risk. Öncelik: düşük.
  Yalnız dokunulacaksa `msg_def.frame_id` anahtarına geçiş.

### Performans — UI Ingest Yolu (ölçümlü fakat uygulanmamış)
- E13 kapandı (batch evaluate_js); kalan: telemetri döngüsündeki `router.route_frame` +
  decoder zinciri frame başına çalışıyor — yüksek yükte UI thread'i yorulabilir.
  profilleme sonrası kararlaştırılır (benchmark altyapısı `.scratch/review_benchmarks.py`).

---

## 3. Ürün Kararı Gerektirenler (kod hazır, bağlama kararı kullanıcıda)

### K2 — Bağımsız E-Stop Doğrulayıcı
- **Durum:** Reset token'ı aynı süreçte üretilip tüketiliyor ("yerel kurtarma" olarak
  kodda + README'de dürüstçe sınıflandırıldı). Gerçek çoklu-operatör yetkilendirmesi
  için: UI'da operatör challenge akışı tasarımı + ayrı bileşen. Kod yapısı
  (`create_reset_token` / `reset` ayrık) buna hazır.

### K1(b) — Lisans Yığınının Composition Root'a Bağlanması
- **Durum:** Altyapı testli (Ed25519, HWM, grace, anti-rollback); başlangıçta lisans
  denetimi + özellik kilitleme akışı ürün kararı ister: hangi özellikler lisanslı,
  sunucu dağıtımı, anahtar üretimi. Paralel K1(a) UI işi bitince doğal aday.

---

## 4. Doğrulama Borcu (düşük risk, tek seferlik)

- [ ] **`secrun scan ./`** — HANDOFF'un doğrulama üçlüsündeki son ayak. Bu oturumda
  kurulu değil (PyPI/npm'de yok). Yedeği koşuldu: bandit (11 bulgu — hepsi isimlendirilmiş
  sabitler/heuristik, gerçek sızıntı yok) + detect-secrets (4 isabet — hepsi yanlış
  pozitif). secrun'lu bir ortamda bir kez koşulup 22 bilinen FP dışında isabet
  olmadığı teyit edilmeli.
- [ ] **Saha doğrulamaları:** RP1210Bus (mock-DLL testli, gerçek Nexiq/DLA adaptörü
  değil) ve rp1210 CLI yolu gerçek donanımla.

---

## 5. Kapanmış Kabul Edilenler (buradan iş ÜRETİLMEZ — sadece bağlam)

78-bulgu review'nin tamamı, P0/P1/P2 protokol düzeltmeleri (J1939 CMDT state machine,
ISO-TP N_As, UDS raw NRC, ALFI, T4/T2/T3), Dalga 1-5, K1-K4 doküman kararları,
"Küçükler" (B9-E15 serisi), D8 kanonik TX + privileged_send, gateway lock-scope
refactor (H2), Hypothesis property süiti (40 test, mutasyon-doğrulanmış), RP1210
entegrasyonu (K4-a), CSV replay (K3-a), doküman hijyeni (82→13 md). Detaylar: git
geçmişi (Türkçe commit mesajları) ve `docs/testing/traceability.md`.

## 6. Uzak Depo

- [ ] Tüm commit'ler yalnızca yerelde (`main` dalı, 19 commit) — push kullanıcı
  kararı/talimatıyla.
