# Project Haris — Maritime M-SOC Validation Dataset

Kaynak: Zenodo DOI 10.5281/zenodo.21994503 (Nasr, A. et al., 2026-08)
**Açık erişim** — Estonya Denizcilik Akademisi eğitim gemisi "Sinilind"
(Stentor 54 Pilothouse) üzerinde canlı NMEA 2000/CAN backbone kaydı.

## Dosyalar

| Dosya | Boyut | İçerik |
|---|---|---|
| `vessel.csv` | 1.8 MB | 17.089 adet 10 sn'lik N2K snapshot (timestamp, pozisyon, SOG, heading, COG, depth) |
| `combined.csv` | 12.3 MB | vessel + bench (simülatör) birleşik, 144.157 satır |
| `metadata.json` | 1 KB | Zenodo metaverisi |
| `raw/can0_raw_sinilind.log` | 1.76 GB | **Ham candump**: 36.238.192 CAN 29-bit extended frame, 74 PGN (48 standart N2K + 28 üretici/ISO), 455 benzersiz ID. Pencere: 2026-08-05 .. 08-13 |

## PGN Profili (ilk 30, 36.2M frame)

```
PGN 64004: 4.131.454  |  PGN 61709: 3.430.705  |  PGN 61701: 2.941.075
PGN 63493: 2.408.385  |  PGN 63502: 2.402.888  |  PGN 63489: 1.766.575
PGN 63491: 1.606.058  |  PGN 63492: 1.606.058  |  PGN 61715: 1.606.058
PGN 61714: 1.606.057  |  PGN 63748: 921.015    |  PGN 61965: 803.018
PGN 63490: 802.941    |  PGN 64787: 802.779    |  PGN 65341: 735.616
PGN 64775: 642.270    |  PGN 65324: 632.240    |  PGN 65305: 627.723
PGN 64258: 510.565    |  PGN 64006: 481.821    |  PGN 62739: 481.653
PGN 59904: 448.766    |  PGN 60928: 443.269    |  PGN 61722: 376.948
PGN 65280: 370.979    |  PGN 65286: 334.233    |  PGN 64770: 321.175
PGN 64003: 321.159    |  PGN 64257: 259.400    |  PGN 63749: 222.978
```

## Notlar

- `can0_raw` candump formatındadır: `(ts) can0 ID#DATA` — projenin
  ReplayBus'ı `.asc/.csv/.blf` bekler; dönüşüm için Golden-Traces
  `scripts/convert_candump_to_asc.py` kullanılabilir.
- `vessel.csv` **decode edilmiş** telemetridir (10 sn periyotlu snapshot),
  ham CAN frame'i değildir. PGN destekli analiz için kullanılabilir
  (pozisyon/hız/heading zaman serisi).
- PGN 64004, 61709, 61701, 63493-63502 gibi yüksek PGN'ler ISO 11783
  (ISOBUS/J1939) alanındadır ve N2K üzerinde taşınır — Sinilind gemisinde
  Volvo Penta tipi motor/şanzıman telemetrisine işaret eder.
- Atıf: Nasr, A. et al. (2026). "Project Haris: Maritime M-SOC Validation
  Dataset", Zenodo. DOI 10.5281/zenodo.21994503.