# Kalan İşler — Universal CAN-Bus Tool

> **Durum baz tarihi:** 2026-09-01 · 1200/1200 test PASSED · ruff 0 hata · 35 commit
> Bu dosya, tamamlanmış kapsamlı review + düzeltme dalgalarının (CODE_REVIEW-KIMIK3 ve
> CODE_REVIEW-DEEPSEEK üzerindeki tüm 78+ bulgunun çözümü: Dalga 1-5, P0/P1/P2
> protokol düzeltmeleri, JsonFormatter extra alanları, tahrif edilemez kanonik rapor SHA-256,
> hız fail-closed kilidi, ISO-TP tampon aşımı, UDS routine CRC32 doğrulaması, J1939 CTS monotonluğu,
> NMEA2000 sentinel sınırları, ReplayBus loop desteği, DBC C-identifier sanitizasyonu,
> RP1210/CSV/BLF entegrasyonu, gateway lock-scope refactor, Hypothesis property süiti,
> Bulut UI SaaS köprüsü, DBC Knowledge Pack [181 DBC], Golden-Traces [14 Benchmark Vektörü],
> Sinyal Keşif & Kanıt Motoru, K1(b) H1 Cihaz Bağı, K2 E-Stop Challenge-Response Köprüsü,
> Nuitka C++ Derleme Zırhı ve Desktop Launcher & Auto-Updater Altyapısı) ardından
> **hâlâ açık** olan işlerin tek kaynağıdır. Bir kalem tamamlandığında bu dosyadan düşürülür.

---

## 1. Ürün Kararı Gerektirenler (kod hazır, bağlama kararı kullanıcıda)

### K2 — Bağımsız E-Stop Doğrulayıcı
- **Durum:** K2 E-Stop challenge-response reset API'leri (`estop_request_challenge`,
  `estop_submit_reset_token`, `estop_reset_local`) hem backend hem TypeScript köprüsüne
  bağlandı. Çoklu-operatör yetkilendirme altyapısı devrede.

### K1(b) — Lisans Yığınının Composition Root'a Bağlanması
- **Durum:** H1 cihaz bağı (`device_id` DPAPI eşleşmesi) bağlandı ve test edildi.
  İleride ticari ürün kararıyla zorunlu aktivasyon kapısı `main.py` başlangıcına konabilir.

---

## 2. Performans ve Optimizasyon (ölçümlü fakat bekletilen)

### Performans — UI Ingest Yolu
- E13 kapandı (batch evaluate_js); telemetri döngüsündeki `router.route_frame` +
  decoder zinciri frame başına çalışıyor — yüksek yükte UI thread'i profilleme sonrası
  kararlaştırılır (benchmark altyapısı `.scratch/review_benchmarks.py`).

---

## 3. Doğrulama Borcu (düşük risk, tek seferlik)

- [ ] **`secrun scan ./`** — HANDOFF'un doğrulama üçlüsündeki son ayak. Bu ortamda
  kurulu değil (PyPI/npm'de yok). Yedeği koşuldu: bandit (11 bulgu — hepsi isimlendirilmiş
  sabitler/heuristik, gerçek sızıntı yok) + detect-secrets (4 isabet — hepsi yanlış
  pozitif). secrun'lu bir ortamda bir kez koşulup 22 bilinen FP dışında isabet
  olmadığı teyit edilmeli.
- [ ] **Saha doğrulamaları:** RP1210Bus (mock-DLL testli, gerçek Nexiq/DLA adaptörü
  değil) ve rp1210 CLI yolu gerçek donanımla.

---

## 4. Kapanmış Kabul Edilenler (buradan iş ÜRETİLMEZ — sadece bağlam)

78-bulgu review'nin tamamı, P0/P1/P2 protokol düzeltmeleri (J1939 CMDT state machine,
ISO-TP N_As, UDS raw NRC, ALFI, T4/T2/T3), Dalga 1-5, K1-K4 doküman kararları,
"Küçükler" (B9-E15 serisi), D8 kanonik TX + privileged_send, gateway lock-scope
refactor (H2), Hypothesis property süiti (40 test, mutasyon-doğrulanmış), RP1210
entegrasyonu (K4-a), CSV replay (K3-a), BLF replay (K3-b), Bulut/Lisans UI SaaS
köprüsü (K1-a), DBC decoder cache key frame_id geçişi, DBC Knowledge Pack
(181 DBC, 14961 mesaj, 75603 sinyal), Golden-Traces 14 benchmark vektörü ve
entegrasyon süiti, Sinyal Keşif ve Kanıt Motoru (Signal Discovery & Evidence Engine
ve 9 birim/entegrasyon testi), Nuitka C++ derleme hattı (`scripts/build_nuitka.py`),
Masaüstü Launcher & Auto-Updater (`src/launcher/`), doküman hijyeni (82→13 md).
Detaylar: git geçmişi (Türkçe commit mesajları) ve `docs/testing/traceability.md`.

## 5. Uzak Depo

- [ ] Tüm commit'ler yalnızca yerelde (`main` dalı, 30 commit) — push kullanıcı
  kararı/talimatıyla.
