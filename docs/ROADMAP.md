# Kalan İşler — Universal CAN-Bus Tool

> **Durum baz tarihi:** 2026-09-01 · 1190/1190 test PASSED · ruff 0 hata · 26 commit
> Bu dosya, tamamlanmış kapsamlı review + düzeltme dalgalarının (78 bulgu, P0/P1/P2
> protokol düzeltmeleri, Dalga 1-5, K1-K4, "Küçükler" grubu, RP1210/CSV/BLF entegrasyonu,
> gateway lock-scope refactor, Hypothesis property süiti, Bulut UI SaaS köprüsü,
> DBC Knowledge Pack [133 DBC], Golden-Traces [14 Benchmark Vektörü], Sinyal Keşif & Kanıt Motoru)
> ardından **hâlâ açık** olan işlerin tek kaynağıdır. Bir kalem tamamlandığında bu dosyadan düşürülür.

---

## 1. Ürün Kararı Gerektirenler (kod hazır, bağlama kararı kullanıcıda)

### K2 — Bağımsız E-Stop Doğrulayıcı
- **Durum:** Reset token'ı aynı süreçte üretilip tüketiliyor ("yerel kurtarma" olarak
  kodda + README'de dürüstçe sınıflandırıldı). Gerçek çoklu-operatör yetkilendirmesi
  için: UI'da operatör challenge akışı tasarımı + ayrı bileşen. Kod yapısı
  (`create_reset_token` / `reset` ayrık) buna hazır.

### K1(b) — Lisans Yığınının Composition Root'a Bağlanması
- **Durum:** Altyapı testli (Ed25519, HWM, grace, anti-rollback); başlangıçta lisans
  denetimi + özellik kilitleme akışı ürün kararı ister: hangi özellikler lisanslı,
  sunucu dağıtımı, anahtar üretimi. K1(a) UI köprüsü bağlandığı için doğal aday.

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
(133 DBC, 12518 mesaj, 57862 sinyal), Golden-Traces 14 benchmark vektörü ve
entegrasyon süiti, Sinyal Keşif ve Kanıt Motoru (Signal Discovery & Evidence Engine
ve 9 birim/entegrasyon testi), doküman hijyeni (82→13 md).
Detaylar: git geçmişi (Türkçe commit mesajları) ve `docs/testing/traceability.md`.

## 5. Uzak Depo

- [ ] Tüm commit'ler yalnızca yerelde (`main` dalı, 26 commit) — push kullanıcı
  kararı/talimatıyla.
