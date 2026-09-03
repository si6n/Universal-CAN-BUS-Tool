# Marine Trace Samples — canboat (v8.1.0)

Gerçek tekne NMEA 2000 / J1939 CAN kayıtları. Kaynak: canboat/canboat
`samples/` dizini, Apache-2.0 (© canboat authors, Kees Verruijt).
Sabitleme: `v8.1.0` (2026-08-30 release).

## Formatlar

- `*.raw` — canboat **PLAIN**: `timestamp,src,pgn,dst,pri,dlc,b1,b2,...`
  (satır başına bir frame; FAST toplu kayıtlarında DLC > 8 olabilir)
- `*.all` — canboat **FAST**: `# format=FAST` başlıklı, tam mesaj başına satır
- `*.log` — ikili/özel ağ kayıtları (ikonvert, fusion)
- `*.ebl` — Actisense NGT-1 ikili kayıt formatı
- `*.dle` — Yacht Devices YDNU ikili kayıt formatı
- `*.pcap` — ham CAN pcap (Wireshark)
- `*.trc` — PEAK PCAN-View metin trace
- `*.csv` / `*.n2klog.csv` — Garmin CSV export
- `sample-YDWG02*.txt`, `merrimac-ydwg-2020.raw` — Yacht Devices RAW
- `candump*.txt/log` — Linux can-utils candump
- `00010001-130823-27.log`, `NKpayloadsW2K-1.txt` — W2K-1 / NK payload kayıtları
- `sbender1` — SuBender tank sensör kaydı

Projenin ReplayBus'ı `.asc/.csv/.blf` bekler; bu kayıtlar analiz/sinyal
keşfi referansı ve dış dönüşüm girdisidir (PLAIN→ASC dönüştürücüsü planlanmış).

## Öne çıkan kayıtlar

| Dosya | Boyut | Tekne / cihaz | İçerik |
|---|---|---|---|
| maneuvers.raw, maneuvers2.raw | 8.4+9.1 MB | canboat test teknesi | Tam manevra seti (217k frame) |
| dirona-actisense-serial.raw | 2.8 MB | M/V Dirona | Okyanus seyri (40k frame) |
| merrimac-actisense-serial-2011.raw | 73 MB | M/V Merrimac | En uzun kayıt (2011 seferi) |
| merrimac-2022.raw | 7.1 MB | M/V Merrimac | 2022 seferi (80k frame) |
| susteranna*.raw | 0.4+0.9 MB | M/V Susteranna | Genel seyir |
| live.all | 24 MB | canboat canlı oturum | 25k frame karışık trafik |
| ap48-tack.all | 42.6 MB | B&G AP48 | Pilot vira manevraları |
| triton-engine-setup.all | 0.7 MB | B&G Triton | Motor kurulum |
| nac3-operations.raw | 5.9 MB | Navico NAC-3 | Otomatik pilot operasyonları |
| ac42-commissioning.raw | 3 MB | B&G AC42 | Pilot komisyon kaydı |
| navico-source-selection.raw | 4.4 MB | Navico ağı | Kaynak seçimi (130842) |
| raymarine-ev1.raw / .dle | 1.6 MB | Raymarine EV-1 | Dümen/pilot döngüsü |
| furuno-130842*.raw (5 dosya) | ~9 MB | Furuno SCX-20 | Hız/heading/ivme manevraları |
| furuno-fap7011c-*.raw (2) | ~1.6 MB | Furuno FAP-7011C | Pilot manevraları |
| garmin-ap-reactor-126720.raw | 134 KB | Garmin Reactor | Pilot durum |
| scx20*.raw (20 dosya) | ~1.9 MB | Furuno SCX-20 | Ayar aracı trafiği |
| simrad*.raw, simnet-*.raw | ~1.5 MB | Simrad/Simnet | Pilot, olay zamanlayıcı, TP32 |
| bandg_*.raw | ~10 KB | B&G | TritonEdge, Zeus, latin1 string |
| fusion-130820.log / *.raw | ~5.9 MB | Fusion stereo | Medya cihazı (UTF-8 dahil) |
| sleipner-slink-*.raw | 144 KB | Sleipner S-Link | Pusur motoru kontrol + PPC |
| victron-61184-vreg.raw | 300 B | Victron | PGN 61184 regülatör |
| boatkit-*.raw | ~2 KB | Yanmar/Garmin/Fusion | Kontrol kayıtları |
| mercury-proprietary.raw | 1 KB | Mercury | Üretici-özel motor |
| maretron-*.raw | ~5 KB | Maretron ALM100/SSC300 | Alarm, pusula |
| lowrance-65285.raw | 0.7 KB | Lowrance | Sıcaklık |
| ikonvert.log | 0.5 MB | Digital Yacht iKonvert | Gateway kaydı |
| actisense*.ebl/.raw/.log | ~21 KB | Actisense | NGT-1 ikili + W2K-1 |
| can0-1.pcap | 1.6 MB | SocketCAN | Ham pcap |
| candump*.txt/log (4) | ~0.4 MB | can-utils | candump örnekleri |
| sample3_*.csv/.trc | ~1.3 MB | Garmin GPSMAP / PCAN | CSV + PCAN-View |
| pgn*.raw/.txt/.ebl | ~70 KB | canboat | Tek-PGN kayıtları |
| strings.raw, fake127510+127511.raw | ~4 KB | canboat | String PGN'ler, test frame'leri |
| simulator*.raw, sample-*.txt | ~180 KB | canboat simülatör | Rüzgar/sıcaklık/çevre, tam PGN seti |

`candumpSample1.txt` 253 KB (B&G ZG100 + ST508), `candumpSample3.txt` 126 KB.

## Di�er kaynaklardan eklenen dosyalar

| Dosya | Kaynak | ��erik |
|---|---|---|
| `signalk_aava-n2k.data` | SignalK/signalk-server (Apache-2.0) | 2014 "Aava" yelkenlisi, 10 dk ger�ek N2K, 19 PGN: 1 Hz pozisyon/zaman, 2 Hz h�z/�evre, heartbeat (Golden-Traces golden; canboat CSV `ISO-Z` damgal�) |
| `PGN127507.raw` | canboat | Charger Status �rnek kayd� (8 �arj cihaz� instance'�, CHARGER_STATE enum) � Golden-Traces golden |
| `open-ships_sample.log` | open-ships/n2k (MIT) | 6 sn ger�ek yelkenli kayd�, candump format� `($ts) can0 ID#DATA` |
