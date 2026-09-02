# OBD-II ve J1939 Referans Zemini — Korelör Çapraz Doğrulama Seti (2026-08-30)

Kaynaklar: Wikipedia "OBD-II PIDs" (ham vikimetin birebir alındı; lokal kopya
`_kaynak/obd2_*.wiki`), CSS Electronics "OBD2 Explained" (2025-01 güncellemesi) ve
"J1939 Explained" (2025-01), Wikipedia "SAE J1939" (ham metin), recan (Data in Brief 2020)
SPN tanımları. Amaç: correlator (PR-4) fiziksel etiketleri bu tablolarla ispatlar;
dbc_builder scale/offset doğrulaması buradan gelir.

## 1. OBD-II CAN (11-bit) çerçeve formatı
- **İstek:** fonksiyonel ID **0x7DF**, 8 bayt:
  `[ek-veri-bayt-sayısı=02][servis=01][PID][dolgu ×5]` (ISO 15765-2 dolgu için CC önerir).
  Araç-özel istek: ek-bayt=03, servis 0x22 + 2 baytlık PID (ör. 0x4980).
- **Yanıt:** **0x7E8…0x7EF** (ECU fiziksel adresi 0x7E0… + 8; motor/genellikle 0x7E8):
  `[uzunluk][servis+0x40 → 0x41][PID][A][B][C][D][dolgu]`. 7Fh = genel ret.
  Uzun yanıtlar ISO-TP çok-çerçeveli gelir (ilk bayt = ek-bayt sayısı 3–6).
- Service 01 = anlık veri; 02 = dondurulmuş kare (PID 02 = tetikleyen DTC).

## 2. Mode 01 PID formülleri (SAE J1979; A=ilk veri baytı; kA+B = 256·A+B)
| PID | Büyüklük | Bayt | Formül | Birim |
|---|---|---|---|---|
| 04 | Hesaplanan motor yükü | 1 | 100/255·A | % |
| 05 | Motor soğutma suyu sıcaklığı | 1 | A−40 | °C |
| 06/07 | Kısa/uzun vadeli yakıt ayarı (Bank 1) | 1 | 100/128·A−100 | % |
| 0A | Yakıt basıncı (gauge) | 1 | 3A | kPa |
| 0B | Emme manifoldu mutlak basıncı | 1 | A | kPa |
| 0C | Motor hızı | 2 | (256A+B)/4 | rpm |
| 0D | Araç hızı | 1 | A | km/h |
| 0E | Ateşleme avansı | 1 | A/2−64 | ° TDC |
| 0F | Emme havası sıcaklığı | 1 | A−40 | °C |
| 10 | MAF hava akış hızı | 2 | (256A+B)/100 | g/s |
| 11 | Gaz kelebeği konumu | 1 | 100/255·A | % |
| 1F | Motor startından beri süre | 2 | 256A+B | s |
| 21 | MIL açıkken kat edilen mesafe | 2 | 256A+B | km |
| 22 | Yakıt rayı basıncı (manifolda göre) | 2 | 0.079·(256A+B) | kPa |
| 23 | Yakıt rayı basıncı (dizel/GDI gauge) | 2 | 10·(256A+B) | kPa |
| 33 | Mutlak barometrik basınç | 1 | A | kPa |
| 42 | Kontrol modülü gerilimi | 2 | (256A+B)/1000 | V |
| 43 | Mutlak yük değeri | 2 | 100/255·(256A+B) | % |
| 45 | Göreceli gaz kelebeği konumu | 1 | 100/255·A | % |
| 46 | Dış ortam sıcaklığı | 1 | A−40 | °C |
| 47–4B | Mutlak kelebek/pedal konumları B–F | 1 | 100/255·A | % |
| 4C | Emredilen kelebek aktüatörü | 1 | 100/255·A | % |
| 4D | MIL açıkken çalışma süresi | 2 | 256A+B | dk |
| 4E | DTC silinmesinden beri süre | 2 | 256A+B | dk |
| 51 | Yakıt tipi | 1 | numaralandırılmış (1=bensin, 4=dizel, 8=elektrik …) | — |
| 52 | Etanol yüzdesi | 1 | 100/255·A | % |
| 5A | Göreceli kelebek konumu | 1 | 100/255·A | % |
| 5C | Katalizör sıcaklığı (B1S1..B2S2: 3C–3F) | 2 | (256A+B)/10−40 | °C |
| 61/62 | Sürücü talebi / gerçek motor torku | 1 | A−125 | % |
| 63 | Motor referans torku | 2 | 256A+B | N·m |
| A6 | Kilometre sayacı (MY2019+ zorunlu) | 4 | (A·2²⁴+B·2¹⁶+C·2⁸+D)/10 | km |
- Bit-maskeli destek PIDs: 00/20/40/60/80/A0/C0. Bit-kodlanmış: 01, 03, 12, 1C, 41.
- 0x22/0x23'te AB, PID 0x32/0x54'te **two's-complement işaretli** — signedness sınıflandırması
  (CAN-D) OBD alanlarında da gerekir.

## 3. SAE J1939 (29-bit)
- 250 kbit/s (J1939/11, /15; /14 → 500K); yalnızca **29-bit genişletilmiş ID** (CAN 2.0B);
  veri 8 bayt; **Intel bayt sırası** (LSB first); TP (J1939-21) ile **≤1785 baytlık** PGN'ler
  (BAM/CM-CTS çok-çerçeve); PGN'ler çoğunlukla broadcast, bir kısmı istek üzerine.
- **29-bit ID =** öncelik 3 bit (28–26) | R (25) | DP (24) | **PF** (23–16) | **PS** (15–8) |
  **SA** (7–0); **PGN (18 bit) = R+DP+PF+PS** (standart J1939-21 yerleşimi; 18+3+8=29 tutarlı).
  **PDU1** (PF<240): PS = hedef adres → PGN = PF‖00; **PDU2** (PF≥240): PS = grup uzantısı →
  PGN = PF‖PS (ana projenin golden README PDU1/PDU2 kuralıyla birebir).
- Mülkiyet aralığı: PGN 0x00FF00–0x00FFFF (proprietary). SPN'ler PGN verisini oluşturur.
- Bilinen örnekler (recan/golden teyitli): **EEC1 = PGN 61444 (0xF004)** — SPN 190 motor hızı
  (2 bayt, 0.125 rpm/bit, offset 0; 0xFFFF=NA); **CCVS1 = PGN 65265 (0xFEF1)** — SPN 84
  tekerlek-bazlı araç hızı (2 bayt, 1/256 km/h/bit). İstek PGN 59904 (0xEA00) ve adres
  talebi PGN 60928 (0xEE00) standart J1939-21 sabitleridir (bu turda bağımsız kaynak
  eşlemesi yapılmadı). Colorado State Kenworth kayıtlarında CCVS ↔ Video VBox teyidi
  golden.yaml external_checklist maddesidir.

## 4. Korelör çapraz doğrulama haritası (PR-4 girdisi)
| Fiziksel büyüklük | Dışsal kanıt | Plausibility aralığı | DBC scale/offset iması |
|---|---|---|---|
| Araç hızı | OBD PID 0x0D | 0–220 km/h | RAW↔OBD lineer fit (r² ≥ 0.98) → scale/offset |
| Motor hızı | OBD PID 0x0C | 0–8000 rpm | 2 bayt LE aday; ölçek /4 kalıbı |
| Pedal / kelebek | OBD PID 0x11 / 0x49 | 0–100 % | monoton artan eşlik, % ölçek |
| Sıcaklıklar | OBD PID 0x05 / 0x0F / 0x46 | −40…+150 °C | offset −40 kalıbı |
| Gerilim | OBD PID 0x42 | 9–16 V | /1000 ölçek |
| J1939 hız | SPN 84 (CCVS1) | 0–250 km/h | 1/256 km/h/bit; 0xFFFF sentinel |
| J1939 RPM | SPN 190 (EEC1) | 0–8000 rpm | 0.125 rpm/bit; 0xFFFF sentinel |
- **Prosedür:** keşif aday sinyali ↔ eşzamanlı OBD-II/J1939 ölçümü → Pearson r + lineer fit
  (scale = Δraw/Δphys, offset) → `Evidence("external_validation")` + confidence bonus.
  Fit başarısızsa aday reddedilmez; yalnızca etiketsiz kalır (MASTER_PLAN BÖLÜM 7:
  "kesinlik iddiası yerine çok katmanlı kanıt"). Uygulama senaryosu: CAN-Modes Ford Fiesta
  RAW + OBD PID log çifti (veri_kumeleri.md §1).
