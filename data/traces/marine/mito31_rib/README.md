# MITO 31 RIB — Deniz Deneme Kayıtları (Mendeley)

Kaynak: "Dataset for Sea-Trial Data Processing and Manoeuvring Analysis of a
Rigid Inflatable Boat (RIB) MITO 31" — Niazmand Bilandi, Roshan, Mancini,
Vitiello (FORCE Technology / TalTech / Univ. Napoli Federico II).
DOI: 10.17632/pz37h8vtjt.1 — **CC BY 4.0**.
SHA256 (zip): `06f4a18a5a5d5b1517227377b2908a2bb818f3d1489ba5729c4dad2ccfc16084`.

İçerik: iki adımlı (two-stepped) yüksek hızlı planing tekne MITO 31'in tam
ölçekli deniz denemesi — sıfır hız serbest sürüklenme (free-drift), yüksek hız
düz seyir (seakeeping, 37 knot) ve dönüş manevraları.

## Dosyalar

| Dosya | Boyut | İçerik |
|---|---|---|
| `Log_NMEA_2000_turn.TXT` | 8.6 MB | Dönüş manevrası NMEA 2000 kaydı (JSON benzeri decode edilmiş) |
| `imu_gnss/01_zero_speed_wave_buoy/Log_IMU_boa_onda.TXT` | 11.4 MB | Sıfır hız dalga boyuncu — IMU/GNSS |
| `imu_gnss/02_seakeeping_and_turn/LOG_IMU_seakeeping_plus_1turn_37_knots.TXT` | 10.0 MB | 37 knot seyir + dönüş — IMU/GNSS |
| `imu_gnss/03_turning/Log_IMU_turn.TXT` | 9.2 MB | Dönüş manevrası — IMU/GNSS |

## N2K PGN kapsamı (Log_NMEA_2000_turn.TXT, ~50k mesaj)

127488 Engine Rapid **16.270x** (çift motor!), 127493 Transmission Dynamic
**16.266x**, 129025 Position Rapid 8.098x, 129026 COG/SOG 4.049x, 127489
Engine Dynamic 3.267x, 129542/129547/127258/129283/129539/129033/129029/129540
(1 Hz ailesi) ~810x, 127505 Fluid Level 327x, 128267 Water Depth 151x,
65311 (üretici-özel) 81x, 59904 ISO Request 12x.

## Notlar

- N2K kaydı **decode edilmiş JSON** formatındadır (canboat analyzer benzeri);
  ham CAN frame'i değildir. PGN istatistikleri ve alan değerleri için doğrudan
  kullanılabilir; ReplayBus oynatımı için dönüştürme gerekir.
- IMU/GNSS kayıtları çapraz doğrulama (golden kanıt) için kullanılır:
  PGN 127488 RPM ↔ IMU ivme/yaw-rate korelasyonu, GNSS rota ↔ 129025/129026.
- Atıf: Niazmand Bilandi, R., Roshan, F., Mancini, S., Vitiello, L. (2026).
  Mendeley Data, V1, DOI 10.17632/pz37h8vtjt.1 (CC BY 4.0).
