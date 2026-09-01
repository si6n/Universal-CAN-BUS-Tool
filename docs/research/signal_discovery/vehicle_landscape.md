# Araç ve Kütüphane Manzarası (doğrulamalı — 2026-08-30)

## 1. cantools (Python DBC kütüphanesi) — DOĞRULANDI, UÇTAN UCA TEST EDİLDİ
- github.com/cantools/cantools — MIT lisans, 2,277★, Python, konular: dbc, kcd, sym, arxml, cdd.
  Default branch: master, kaynak `src/` layout'unda (eski `cantools/database` yolu 404).
- **Ampirik test (lokal Python 3.13.15, cantools 43.0.0):** Database → Message → Signal kur →
  DBC metnine dönüştür → geri yükle → kare çöz. **SONUÇ OK: `{'COUNTER': 1, 'SPEED': 100}`**
  (test mesajı: frame_id 0x1F3, 8 bayt, COUNTER 0|4@1+, SPEED 8|16@1+ km/h).
- **Kritik API düzeltmesi:** 43.0.0'da `Database.dump()` metodu YOK. Doğru yollar:
  - `cantools.database.dump_file(database, filename, database_format=None, encoding=None,
    sort_signals='default')` → dosyaya yazar (format: dbc, kcd, sym, arxml).
  - `cantools.database.can.formats.dbc.dump_string(database, sort_signals='default', ...)`
    → DBC metni döner (string).
- **Signal.__init__** imzası: `(name, start, length, byte_order='little_endian', is_signed=False,
  raw_initial=None, raw_invalid=None, conversion=None, minimum=None, maximum=None, unit=None,
  dbc_specifics=None, comment=None, receivers=None, is_multiplexer=False, multiplexer_ids=None,
  multiplexer_signal=None, spn=None)`.
- **Message.__init__** imzası: `(frame_id, name, length, signals, contained_messages=None,
  header_id=None, header_byte_order='big_endian', unused_bit_pattern=0x00, comment=None,
  senders=None, send_type=None, cycle_time=None, dbc_specifics=None, autosar_specifics=None,
  is_extended_frame=False, is_fd=False, bus_name=None, signal_groups=None, strict=True,
  protocol=None, sort_signals=sort_signals_by_start_bit)`.
- **Database.__init__**: `(messages, nodes, buses, version, dbc_specifics, autosar_specifics,
  frame_id_mask, strict=True, sort_signals)`; mesaj ekleme/değiştirme sonrası `refresh()` şart.
- Bit numaralandırma: `start` = LSB bit konumu; DBC'ye `@1`/`@0` olarak yansır.
- `Message.cycle_time` (ms) ↔ DBC `BA_ "GenMsgCycleTime"`.

## 2. SavvyCAN (C++/Qt) — masaüstü referansı
- github.com/collin80/SavvyCAN — 1.8k★, Qt5 (≥5.14; QT6 WIP dalı), 2015–2024 Collin Kidder.
- Donanım: GVRET/CANDue (EVTV) + her QtSerialBus sürücüsü (socketcan, Vector, PeakCAN, TinyCAN).
- 12 log formatı (README'den): BusMaster, Microchip, CRTD (OVMS), GVRET, generic CSV,
  Vector Trace, IXXAT Minilog, CAN-DO, Vehicle Spy, CANDump/Kayak (RO), PCAN (RO),
  Wireshark PCAP (RO). Kayıt cihazı olmadan da offline analiz yapılabilir.
- Wiki 4 sayfa (Home, Debian/Windows kurulum, Wishlist) — özellik listesi wiki'de değil.
  RE özellikleri (önceki araştırma teyidi): DBC yükleme, flow view / histogram / matrix
  grafikler, CANDecoder özel çözücüler, fuzzing, ISO-TP/UDS, script desteği.

## 3. openpilot-cabana (deanlee, C++/Qt6) — UX/metodoloji referansı ⭐
- github.com/deanlee/openpilot-cabana — MIT, 45★, CAN/CAN-FD analizörü + DBC editörü,
  gömülü OpenDBC veritabanı (50+ araç tanımı).
- **Canlı bit ısı haritası:** bit flip anında parlar, zamanla söner → aktif sinyaller anında görünür.
- **Desen boyama (bayt başına):** 🟩 artan (sayaç), 🟥 azalan, 🟧 toggle (flag),
  🟪 noisy (CRC/gürültü), ⬜ static. → Keşif motoru UI'ının sınıflandırma şeması.
- **Find Similar Bits** (mesajlar/otobüsler arası ilişkili sinyal keşfi),
  **Find Signal** (değer aralığı/eşiğe göre tüm mesajlarda arama), bit muting, sparkline,
  sinyal grafikleri (sürükle-bırak), video senkron, log birleştirme (stitching), CAN-FD ≤64B,
  DBC editör (undo/redo, VAL_ tabloları, CSV dışa aktarım).
- Kaynaklar: Vector ASC, candump, PEAK TRC (v1.x/v2.x), SocketCAN, Panda, openpilot route, ZMQ.

## 4. CANBUSconfidenceid (Python) — sayaç/checksum hipotez motoru ⭐ (açık boşluğun kapanması)
- github.com/numbpill3d/CANBUSconfidenceid — MIT, Python 3.7+, saf Python, streaming parser
  (büyük loglar bellek dostu), CLI (`can-hypothesis input.log --report -o out.json`) + Python API.
- Paket: `can_hypothesis_engine/{engine.py, parser/can_parser.py, algorithms/, models/, cli/}`.
- API: `parse_can_log(path, min_frames_per_id=20)` → ID→kareler →
  `CANHypothesisEngine().analyze_grouped_frames(id_to_frames)` → ID başına sonuç.
- **Çıktı modeli (tasarıma doğrudan taşınacak):**
  - `rolling_counters[]`: byte_position, cycle_length, increment_pattern, wrap_points,
    monotonicity, low-randomness, confidence, explanation (insan-okur).
  - `checksum_candidates[]`: algorithm (`checksum_xor` / toplamsal / ters / ones-complement /
    `crc8`), checksum_position, covered_bytes[], match_ratio, confidence, explanation.
  - `multi_byte_candidates[]`; `entropy_summary[]`: byte_position → Shannon entropisi + yorum.
- Girdi: candump kompakt `(ts) can0 ID#DATA` ve köşeli `can0 ID [8] b1..b8` formatları.
- Sayaç algoritmaları: monotonic +1, wrap tutarlılığı, küçük-mod davranışı, bit-field sayaç.
- Checksum algoritmaları: XOR, 8-bit toplamsal, ters-toplam, ones-complement,
  CRC-8 polinomları 0x07 / 0x1D / 0x2F / 0x31 / 0x9B.

## 5. opendbc (commaai) — DBC korpusu + OEM safety kuralları ⭐ 2. turda TAM DAMITILDI
- github.com/commaai/opendbc — MIT, 3.4k★, "a Python API for your car"; yüzlerce araç DBC'i.
- `opendbc/safety/` yapısı: safety.h, declarations.h, helpers.h, can.h + `modes/` altında
  25+ marka dosyası (toyota, honda, hyundai, hyundai_canfd, hyundai_common, subaru,
  subaru_preglobal, chrysler, chrysler_common, chrysler_cusw, tesla, gm, nissan, mazda,
  ford, volkswagen_common/mqb/mlb/meb/pq, body, psa, rivian, mg, elm327...).
- **2. tur çalışması:** 25 dosya lokal indirildi (`_kaynak/opendbc/`), jenerik doğrulama
  çerçevesi + tüm marka sayaç/checksum kuralları satır-satır çıkarıldı →
  **opendbc_marka_guvenlik_profilleri.md** (PR-2'nin parametre seti; negatif-kontrol
  markaları dahil).

## 5b. canmatrix (ebroecker) — DBC format dönüştürücü (2. tur eki)
- github.com/ebroecker/canmatrix — **BSD-2-Clause**, 1,087★, Python, aktif (2026-08 push).
  Default branch: development.
- ".arxml .dbc .dbf .kcd ... fibex json sym xlsx" dönüşümleri + karşılaştırma/diff.
  Konular: arxml, can, canbus, compare, convert, dbc, dbf, dissector, fibex, json, kcd,
  python, sym, xlsx.
- **Kullanım:** dbc_builder (PR-5) çıktısının **arxml/kcd/sym/xlsx genişletmesi** ve
  keşif-çıktısı ↔ mevcut DBC diff'i için; BSD lisansı türev işe engel değil.

## 5c. 2. turda taranan diğer araçlar (GitHub keşif taraması)
- **CAN_Commander** (MatthewKuKanich, 1,059★, C, **lisans YOK**): kapsamlı RE aracı
  (etkileşim + analiz); lisanssız → yalnızca fikir referansı, kod incelemesi önerilmez.
- **CANviz** (Chanchaldhiman, 281★, TypeScript+React+FastAPI, MIT): tarayıcı-tabanlı
  CAN analizör; cantools konuları — **UI mimarisi referansı** (PR-6 ısı haritası için).
- **ESP32_RET_SD** (MotorvateDIY, 71★, C++, MIT): ESP32 SD-kartlı gömülü CAN RE firmwari —
  gömülü taraf için ikincil referans.
- **CANalyze.jl** (tsabelmann, 7★, Julia, MIT): mesaj/değişken analiz paketi — PEAK/sym
  konuları; marjinal, izlemede.
- **Volvo-VIDA, DiveCAN, canana, Ford-Fiesta-MK5-MS-CAN-bus, RNetMsgBroker**: tek-araç RE
  çalışmaları (gömülü/sistem spesifik) — veri kumesi/korelör için tekil örnekleme kaynakları,
  genel mimariye etkisi yok.
- Yöntem makalelerinin araçları: **CANMatch** (TVT'21; kod paylaşımı sınırlı), **CAN-D**
  (ORNL; arXiv'de kod linki yok — pipeline tanımı makaleden taşınacak).

## 6. cabana (commaai, web) — "CAN visualizer and DBC maker"
- github.com/commaai/cabana — openpilot route'larını görselleştirip DBC üreten web aracı;
  deanlee/openpilot-cabana bunun bağımsız sürdürülen masaüstü türevi.

## 7. CANalyzat0r (schutzwerk) — güvenlik odaklı analiz
- github.com/schutzwerk/CANalyzat0r — "Security analysis toolkit for proprietary car protocols".
  Orijinal cabreraalvaro reposu taşınmış/silinmiş görünüyor (arama yalnız schutzwerk kopyaları
  buldu). Girdi formatı desteği (candump/TRC/ASC) için ikincil referans.

## 8. Ana proje entegrasyon noktaları (bu oturumda doğrulandı)
- `FrameRouter.subscribe(callback|queue, filter_ids, channel_id, use_queue)` (src/engine/router.py)
  → keşif motoru mevcut abonelik modeliyle akış alır; `MAX_QUEUE_SIZE = 10_000`.
- `DbcSignalDecoder` (src/engine/decoder/dbc_decoder.py): cantools Database kullanıyor
  (bağımlılık zaten mevcut), `from_dbc_file`, J1939 PGN-maskeli `_lookup_message`
  (PDU1: PS hedef adres, PDU2: PS dahil — golden README kuralıyla birebir),
  `DecodedSignal/DecodedMessage`, `SignalStatus` (VALID/NOT_AVAILABLE/ERROR/STALE/UNKNOWN),
  J1939 sentinel değerleri (max=NA, max-1=error).
- `CanFrame` (src/core/models/can_frame.py): arbitration_id, timestamp_ns, channel_id.
- MASTER_PLAN BÖLÜM 7: entropi + monotonik sayaç (+1 mod N) + CRC-8 hipotez + korelasyon →
  güven skoru → teknisyen onayı → DBC/KCD/SYM. BÖLÜM 18: golden trace L1/L2/L3 + hypothesis.
