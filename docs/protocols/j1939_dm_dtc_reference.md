---
title: "SAE J1939 Diagnostic Messages (DM1..DM11) & DTC Format Reference"
tags:
  - j1939
  - dm1
  - dtc
  - spn
  - fmi
  - reference
---

# SAE J1939 Diagnostic Messages (DM) & DTC Reference

## 1. J1939 Diagnostik Mesajları (DM Listesi)

| Mesaj | PGN (Hex / Dec) | Tanım | İletim Türü |
|---|---|---|---|
| **DM1** | `0xFECA` (65226) | Active Diagnostic Trouble Codes (Aktif Arızalar) | Periyodik 1 Hz Yayın |
| **DM2** | `0xFECB` (65227) | Previously Active DTCs (Geçmiş Arızalar) | İstek Üzerine (On Request) |
| **DM3** | `0xFECC` (65228) | Diagnostic Data Clear/Reset for Previously Active DTCs | İstek ile Sıfırlama |
| **DM4** | `0xFECD` (65229) | Freeze Frame Parameters | İstek Üzerine |
| **DM5** | `0xFECE` (65230) | Diagnostic Readiness 1 | İstek / Periyodik |
| **DM11**| `0xFED3` (65235) | Diagnostic Data Clear/Reset for Active DTCs | İstek ile Sıfırlama |

## 2. J1939 4-Baytlık DTC Yapısı

J1939'da her arıza kodu (DTC) 4 bayttan oluşur:

```
Byte 1: SPN LSB (Bits 0..7)
Byte 2: SPN MSB (Bits 8..15)
Byte 3: SPN En Üst 3 Bit (Bits 16..18) [Bits 7..5] + FMI (Bits 0..4)
Byte 4: Occurrence Count (OC - Bits 0..6) + SPN Conversion Method (Bit 7)
```

### SPN & FMI Formülü:
- **`SPN = (Byte1) | (Byte2 << 8) | ((Byte3 & 0xE0) << 11)`**
- **`FMI = Byte3 & 0x1F`** (0..31)
- **`OC  = Byte4 & 0x7F`** (0..127)

### Yaygın FMI (Failure Mode Identifier) Anlamları:
- `FMI 0`: Veri geçerli fakat normal çalışma aralığının üstünde (Data Above Normal)
- `FMI 1`: Veri geçerli fakat normal çalışma aralığının altında (Data Below Normal)
- `FMI 2`: Veri düzensiz, kesintili veya hatalı (Data Erratic/Intermittent)
- `FMI 3`: Gerilim normalin üstünde / Artıya kısa devre (Voltage Above Normal)
- `FMI 4`: Gerilim normalin altında / Şasiye kısa devre (Voltage Below Normal)
- `FMI 9`: Anormal güncelleme hızı / CAN zaman aşımı (Abnormal Update Rate)
- `FMI 11`: Kök neden belirlenemedi (Root Cause Not Known)
