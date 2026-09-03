# OpenSkipper SampleLogs — Gerçek Tekne N2K Kayıtları

Kaynak: github.com/OpenSkipper/SampleLogs — **CC BY-SA 3.0** (tam metin
`LICENSE-note.txt`; türevler aynı lisansla kamuya açık dağıtılmalı ve
www.openskipper.com kaynağı belirtilmelidir).

## Dosyalar

| Dosya | Boyut | Tekne / cihaz | İçerik |
|---|---|---|---|
| `Kees_NMEA2000_Sample.log` | 24.9 MB | "Kees" teknesi (2009) | 1 saat gerçek N2K, 40 ID: heading 20 Hz, GNSS 9.6 Hz, ISO Request (59904) → Address Claim (60928) korelasyonu ~30 sn periyot; PGN 129540 Sats-in-View 19.2 Hz (Golden-Traces golden) |
| `YDWG-02_NMEA2000_Raw_Sample.log` | 1.0 MB | Yacht Devices YDWG-02 | 6 dk ham N2K akışı, 15 ID: Position Rapid 9.9 Hz, Sats-in-View 26.7 Hz — `HH:MM:SS.mmm R <ID> <bayt>` formatı (tarihsiz) |
| `Nov_08_2009_Weatherstation_N2K.log` | 2.0 MB | Hava istasyonu | N2K watch formatı `<HH:MM:SS.mmm>: <-/-> <pgn> <aid> <hex>`; Heading 4.70 Hz + Wind 2.35 Hz (Golden-Traces golden) |

## Format notları

- Kees logu canboat CSV varyantıdır: `2009-06-18Z09:46:01.129,...` (10.
  karakterde `Z` damgalı).
- YDWG-02 ve hava istasyonu formatları Golden-Traces arşivindeki
  `convert_openskipper_*.py` dönüştürücüleriyle Vector ASC'ye çevrilmiştir
  (bkz. Golden-Traces/converted/n2k/).
