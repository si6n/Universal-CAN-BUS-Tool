# CRC Referansı — Parametreli Katalog ve Keşif Motoru Arama Uzayı (2026-08-30)

Kaynaklar: Greg Cook, "Catalogue of parametrised CRC algorithms" (reveng.sourceforge.io,
11.12.2024 baskısı — lokal kopya: `_kaynak/crc_catalog_1-15.htm`) + opendbc kodu (eşleme doğrulaması).

## 1. Kritik düzeltme: 0x07 ≠ SAE J1850
Önceki taslaklarda "CRC-8 0x07 (SAE J1850)" yazılmıştı — **yanlış**. Katalog (width=8):
- **CRC-8/SAE-J1850:** poly **0x1D**, init **0xFF**, refin=F, refout=F, xorout **0xFF**, check 0x4B.
- **CRC-8/SMBUS** (plain "CRC-8" varsayılanı): poly **0x07**, init 0x00, xorout 0x00, check 0xF4.
- **CRC-8/AUTOSAR** (alias **8H2F**): poly **0x2F**, init 0xFF, xorout 0xFF, check 0xDF.
  opendbc VW kodu yorumla doğrular: "Static lookup table for CRC8 poly 0x2F, aka 8H2F/AUTOSAR".
- **CRC-8/MAXIM-DOW:** poly 0x31, init 0x00, refin=refout=T (yansımalı), check 0x15.
- **CRC-8/CDMA2000:** poly 0x9B, init 0xFF, xorout 0x00, check 0xDA (yansımalı eşdeğeri CRC-8/WCDMA).
Sonuç: CANBUSconfidenceid'in {0x07, 0x1D, 0x2F, 0x31, 0x9B} **polinom seti geçerli kalır**;
yalnızca adlandırmalar düzeltildi.

## 2. Katalogdaki TÜM CRC-8 algoritmaları (20 kayıt, eksiksiz; check = "123456789" yanıtı)
| Ad | poly | init | refin | refout | xorout | check |
|---|---|---|---|---|---|---|
| CRC-8/SMBUS (= "CRC-8") | 0x07 | 0x00 | F | F | 0x00 | 0xF4 |
| CRC-8/SAE-J1850 | 0x1D | 0xFF | F | F | 0xFF | 0x4B |
| CRC-8/AUTOSAR (8H2F) | 0x2F | 0xFF | F | F | 0xFF | 0xDF |
| CRC-8/HITAG | 0x1D | 0xFF | F | F | 0x00 | 0xB4 |
| CRC-8/GSM-A | 0x1D | 0x00 | F | F | 0x00 | 0x37 |
| CRC-8/TECH-3250 (alias AES/EBU) | 0x1D | 0xFF | T | T | 0x00 | 0x97 |
| CRC-8/MIFARE-MAD | 0x1D | 0xC7 | F | F | 0x00 | 0x99 |
| CRC-8/I-CODE | 0x1D | 0xFD | F | F | 0x00 | 0x7E |
| CRC-8/MAXIM-DOW | 0x31 | 0x00 | T | T | 0x00 | 0x15 |
| CRC-8/NRSC-5 | 0x31 | 0xFF | F | F | 0x00 | 0xF7 |
| CRC-8/CDMA2000 | 0x9B | 0xFF | F | F | 0x00 | 0xDA |
| CRC-8/WCDMA | 0x9B | 0x00 | T | T | 0x00 | 0x25 |
| CRC-8/LTE | 0x9B | 0x00 | F | F | 0x00 | 0xEA |
| CRC-8/ROHC | 0x07 | 0xFF | T | T | 0x00 | 0xD0 |
| CRC-8/I-432-1 (ITU) | 0x07 | 0x00 | F | F | 0x55 | 0xA1 |
| CRC-8/DARC | 0x39 | 0x00 | T | T | 0x00 | 0x15 |
| CRC-8/DVB-S2 | 0xD5 | 0x00 | F | F | 0x00 | 0xBC |
| CRC-8/BLUETOOTH | 0xA7 | 0x00 | T | T | 0x00 | 0x26 |
| CRC-8/GSM-B | 0x49 | 0x00 | F | F | 0xFF | 0x94 |
| CRC-8/OPENSAFETY | 0x2F | 0x00 | F | F | 0x00 | 0x3E |
Not: 0x1D dört farklı init/xorout varyantıyla, 0x9B üç, 0x07 ve 0x2F ikişer kez geçer —
**polinom tek başına algoritma tanımlamaz**; init/xorout/reflection parametreleri şart.
CRC-16 için kataloğun ayrı sayfası (16.htm) — Hyundai CAN-FD 16-bit CRC eşlemesi PR-2'de yapılacak.

## 3. opendbc eşlemesi (kodla doğrulanmış gerçeklemeler)
- **Chrysler** (chrysler_common.h) = CRC-8/SAE-J1850 birebir: init 0xFF, poly 0x1D
  (bit-serial gerçekleme), final `~` → xorout 0xFF. Kaynak yorumu: illmatics "Remote Car Hacking".
- **VW MQB/MEB** (volkswagen_common.h) = CRC-8/AUTOSAR varyantı: init 0xFF, `data[1..len)`
  üzerinden; ardından **sayaç-değerine göre mesaj-özel sabitle XOR**, tekrar LUT, final `^0xFF`
  (bkz. opendbc_marka_guvenlik_profilleri.md §2.8). **MLB:** sayaç var, checksum doğrulaması
  henüz implement edilmemiş (kodda TODO).
- **Hyundai CAN-FD** = 16-bit LUT CRC; `data[2:] + ID 2 bayt`; xorout len'e göre 0x819D/0x9F5B.

## 4. CRC RevEng aracı (reveng.sourceforge.io)
- Versiyon 3.0.6 (2024-08); **GPLv3+**; taşınabilir C; 113 preset + kullanıcı tanımlı model;
  istenilen bit genişliği; ileri/geri hesap.
- **Model arama:** yeterli sayıda doğru (mesaj, CRC) çiftinden Rocksoft parametrelerini
  (poly/init/refin/refout/xorout) geri kazanabilir — bilinmeyen OEM CRC varyantlarını
  çözmenin kanıtlanmış yolu (Ross Williams Rocksoft modeline uyumludur).
- Lisans notu: GPL → motora **kod kopyalanmaz**; yalnızca offline doğrulama aracı olarak
  kullanılır (bizim gerçekleme saf Python; katalog parametreleri olgu olduğundan serbesttir).

## 5. PR-2 detektörü için CRC-8 arama sırası (öneri)
1. Parametrik gerçekleme: `crc8(data, poly, init, refin, refout, xorout)` — LUT'sız tek pass.
2. Sabit set, otomotiv öncelikli: SAE-J1850 → SMBUS → AUTOSAR → HITAG → GSM-A → MAXIM-DOW →
   CDMA2000 → WCDMA → LTE → TECH-3250 → NRSC-5 → MIFARE-MAD → I-CODE → ROHC → I-432-1 →
   OPENSAFETY → DARC → DVB-S2 → BLUETOOTH → GSM-B (tüm katalog, ~20 model).
3. Genişletme: init {0x00,0xFF,0x55} × xorout {0x00,0xFF} taraması (yalnız sonuçsuz kalınca).
4. covered_bytes: **bit-mask** tarama — ardışık önek/son ek + Ford tarzı **ardışık olmayan**
   maskeler (bkz. marka profilleri §2.7).
5. Sayaç-bağımlı sapma (VW-magic): saf CRC eşleşme oranı ~1/16 plato yaparsa, sayaç başına
   16 sabitlik XOR-tablosu hipotezi ayrı taranır; kanıt = match_ratio sıçraması.
6. 16-bit aile (CAN-FD): CRC-16 katalog sayfasıyla ayrı iş (PR-4 sonrası).
7. Her aday, katalog `check` değeriyle birim-test doğrulanır (determinizm; BÖLÜM 18).
