---
title: "ISO 14229 UDS Services & Negative Response Codes (NRC) Reference"
tags:
  - uds
  - iso14229
  - protocols
  - reference
---

# ISO 14229 UDS Services & NRC Quick Reference

## 1. UDS Servisleri (SID Listesi)

| Servis ID (Hex) | Servis Adı (UDS Service) | Açıklama |
|---|---|---|
| `0x10` | Diagnostic Session Control | Standart (0x01), ECU Programming (0x02), Extended (0x03) |
| `0x11` | ECU Reset | Hard Reset (0x01), KeyOffOn (0x02), Soft Reset (0x03) |
| `0x14` | Clear Diagnostic Information | DTC hafızasını sıfırlama |
| `0x19` | Read DTC Information | DTC durum maskesi ve freeze-frame okuma |
| `0x22` | Read Data By Identifier (DID) | Sensör ve konfigürasyon DID değerlerini okuma |
| `0x23` | Read Memory By Address | ECU hafıza adresinden doğrudan veri çekme |
| `0x27` | Security Access | Seed & Key el sıkışması ile korumalı servislere erişim |
| `0x2E` | Write Data By Identifier (DID) | Kalibrasyon ve DID yazma |
| `0x31` | Routine Control | ECU test rutinlerini başlatma / durdurma / sonuç alma |
| `0x34` | Request Download | ECU yazılım güncelleme (Flash yükleme başlatma) |
| `0x36` | Transfer Data | Firmware veri bloklarını gönderme |
| `0x37` | Request Transfer Exit | Yazılım transferini tamamlama |
| `0x3E` | Tester Present | Bağlantıyı canlı tutma (Keep-Alive, Zero Subfunction) |

## 2. Negatif Yanıt Kodları (Negative Response Codes - NRC)

Format: `[0x7F, RequestSID, NRC]`

| NRC (Hex) | NRC İsmi | Olası Neden & Çözüm |
|---|---|---|
| `0x10` | `generalReject` | Genel işlem reddi |
| `0x11` | `serviceNotSupported` | İstenen servis bu ECU tarafından desteklenmiyor |
| `0x12` | `subFunctionNotSupported` | Servis destekleniyor fakat alt fonksiyon tanımsız |
| `0x13` | `incorrectMessageLengthOrInvalidFormat` | Mesaj uzunluğu veya PCI formatı hatalı |
| `0x22` | `conditionsNotCorrect` | Koşullar uygun değil (örn: motor çalışırken flash atılamaz) |
| `0x24` | `requestSequenceError` | Sıralama hatası (örn: Seed almadan Key göndermek) |
| `0x31` | `requestOutOfRange` | İstenen DID veya parametre aralık dışı |
| `0x33` | `securityAccessDenied` | Güvenlik kilidi açılmamış (Security Access gerekli) |
| `0x35` | `invalidKey` | Gönderilen güvenlik anahtarı (Key) hatalı |
| `0x36` | `exceedNumberOfAttempts` | Hatalı anahtar deneme limiti aşıldı |
| `0x37` | `requiredTimeDelayNotExpired` | Deneme kotası sonrası bekleme süresi dolmadı |
| `0x78` | `requestCorrectlyReceived-ResponsePending` | İşlem sürüyor, ECU meşgul (Zaman aşımı uzatılmalı) |
| `0x7E` | `subFunctionNotSupportedInActiveSession` | Mevcut oturumda (Session) bu alt fonksiyon yetkisiz |
| `0x7F` | `serviceNotSupportedInActiveSession` | Mevcut oturumda bu servis çalıştırılamaz (Extended Session açılmalı) |
