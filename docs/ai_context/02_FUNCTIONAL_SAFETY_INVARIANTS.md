---
title: "AI Context: Functional Safety Invariants (ISO 26262 ASIL-B/D)"
tags:
  - ai-context
  - safety
  - asil
  - e-stop
  - e2e-crc
updated: 2026-09-01
---

# Functional Safety Invariants (ISO 26262 ASIL-B/D) Context Card

Bu kart, projedeki fonksiyonel güvenlik prensiplerini ve ihlal edilemez sistem kurallarını (invariants) tanımlar. AI ajanları kod yazarken veya hata ararken bu kuralları asla gevşetemez veya kaldıramaz.

## 1. TxSafetyGateway 6-Aşamalı Choke-Point

Tüm giden CAN paketleri `TxSafetyGateway.send(frame)` metodundan geçer. Aşamalar sırasıyla şunlardır:

1. **E-Stop Durum Kontrolü:** E-Stop aktif ise paket anında reddedilir (`SafetyViolationError`).
2. **Kira (Watchdog Lease) Süresi:** Monotonic watchdog kira süresi dolmuşsa iletim bloke edilir.
3. **DLC & Çerçeve Bütünlüğü:** Standart CAN için DLC <= 8, CAN FD için DLC <= 64 doğrulaması.
4. **ID İzin / Yasak Listesi (Allowlist / Denylist):** Güvenlik açısından kilitli ID'ler (örn. kritik fren/direksiyon kontrol ID'leri) engellenir.
5. **Oran Sınırlama (Rate Limiting / Token Bucket):** Bus aşırı yüklenmesini (Bus Flooding) önleyen bant genişliği kontrolü.
6. **E2E CRC & Counter Stamping:** Yapılandırılmışsa pakete rolling counter ve CRC basılır (`TxE2ESafetyPackager`).

## 2. Emergency Stop (E-Stop) & HMAC Reset Token Invariant

- E-Stop tetiklendiğinde (`trigger_estop()`), tüm bus yazma işlemleri donanım düzeyinde durur.
- E-Stop durumundan çıkış (`reset()`), rastgele veya boş parametreyle yapılamaz.
- **HMAC-SHA256 Token Sözleşmesi:**
  - `create_reset_token()` makine tohumu (machine seed) ve timestamp kullanarak tek kullanımlık kriptografik token üretir.
  - `reset(token)` bu token'ı doğrulamadan güvenlik kilidini açmaz.

## 3. AUTOSAR E2E (End-to-End) Profilleri & CRC-8 Polinomları

E2E katmanı paket bozulması, sıra atlaması ve paket kaybını tespit eder:

| Profil | Polinom | Başlangıç Değeri (Init) | XOR Out | Rolling Counter | Kullanım Alanı |
|---|---|---|---|---|---|
| **E2E Profile 1** | `0x1D` (SAE J1850) | `0xFF` | `0xFF` | 0..14 (veya 0..15) | Standart AUTOSAR |
| **E2E Profile 2** | `0x2F` (MQB / P2) | `0xFF` | `0xFF` | 0..15 | VAG MQB, Modern OEM |
| **Toyota Profile** | Checksum Modulo-256 | `0x00` | `0x00` | 0..15 | Toyota OEM |

- **Performans Kuralı:** CRC hesaplamaları runtime döngüleriyle değil, 256 elemanlı önceden hesaplanmış lookup tablolarıyla (LUT) yapılır (mikrosaniye altı gecikme).

## 4. AI İçin Güvenlik Hatırlatmaları
- Bir fonksiyonda güvenlik kontrolü başarısız olduğunda "sessizce geçmek" (`pass` veya `None` dönmek) **YASAKTIR**. Uygun `PlatformError` fırlatılmalıdır.
- Testlerde güvenlik kontrollerini bypass etmek için `mock` yazarken mutlaka production kodunun korunduğunu doğrulayın.
