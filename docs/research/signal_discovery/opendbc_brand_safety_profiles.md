# opendbc Marka Sayaç/Checksum Profilleri — Doğrulanmış Katalog (2026-08-30)

Kaynak: commaai/opendbc `opendbc/safety/` (master; MIT). 25 başlık dosyası bu oturumda
lokal olarak indirildi ve **satır-satır okundu** (`_kaynak/opendbc/` — yalnızca doğrulama
kanıtı, repo kopyası değil). Amaç: PR-2 sayaç/checksum detektörlerinin parametre uzayını
gerçek OEM implementasyonlarıyla temellendirmek + keşif çıktısının "marka profili" ile
karşılaştırılma seti (MASTER_PLAN BÖLÜM 7).

## 1. Genel doğrulama çerçevesi (safety.h + declarations.h)
- `CanMsgCheck{addr, bus, len, frequency_hz, ignore_checksum, ignore_counter, max_counter,
  ignore_quality_flag}` — `max_counter=0` → sayaç kontrolü atlanır; `frequency` beklenen Hz
  (cycle-time kanıtı: DBC `GenMsgCycleTime` hipotezinin marka teyidi).
- `RxStatus{msg_seen, index, valid_checksum, wrong_counters, valid_quality_flag, last_counter,
  last_timestamp, lagging}`.
- Sayaç (safety.h `update_counter`): `expected = (last_counter + 1) % (max_counter + 1)`;
  `wrong_counters += (expected == counter) ? -1 : +1`, `0..MAX_WRONG_COUNTERS (=5)` arasında
  doyurulur; `wrong_counters >= 5` → mesaj geçersiz (debt-model: her doğrulama borcu 1 azaltır,
  5 net hata birikince güven kalmaz).
- Checksum: `compute_checksum(msg) == get_checksum(msg)` — **tolerans yok**, tek hata geçersiz kılar.
- Kalite bayrağı: marka-özel `get_quality_flag_valid` (checksum'tan bağımsız 3. kanal).
- Görülen `max_counter` değerleri: 3 (mod 4), 7 (mod 8), 15 (mod 16), 255 (mod 256)
  → detektör modül arama seti: 2/3/4/8 bit (+ bit-field birleşimleri).

## 2. Marka profilleri (dosya: `_kaynak/opendbc/modes_*.h`)

### 2.1 Toyota (toyota.h) — sayaç YOK, checksum son baytta (uzunluk dahil)
- **Sayaç:** klasik modlarda hiçbir RX mesajında yok (`ignore_counter=true` her yerde;
  `get_counter` hook'u tanımsız). SeCoC varyantı ayrı bir mimari, kapsam dışı.
- **Checksum:** son bayt. `checksum = addr_lo + addr_hi + len + Σ data[0..len-2]`
  (salt toplamsal; **kare uzunluğu da toplama dahil**).
- Doğrulanan mesajlar: 0x260 (50 Hz) ve 0x1D2 (33 Hz) checksum DOĞRULANIR;
  0xaa (83 Hz), 0x226/0x224 (40 Hz) yoksayılır. Kalite bayrağı: 0x260 bit 3
  `STEER_ANGLE_INITIALIZING`; 0xaa'da her teker için 1 hata biti (16-bit alanlar, bit i*16+7).

### 2.2 Honda (honda.h) — son bayt: sayaç üst nibble (mod 4), checksum alt nibble
- **Sayaç:** `counter = (data[len-1] >> 4) & 0x3` → mod 4 (`max_counter=3`).
- **Checksum:** `data[len-1] & 0xF`. Algoritma (nibble-toplam, **ID dahil**):
  `sum = Σ addr'nin hex basamakları + Σ veri nibble'ları (son nibble hariç)`;
  `chk = (8 - sum) & 0xF`. Son bayt = `(counter << 4) | chksum`.
- Mesajlar: 0x1A6/0x296 SCM_BUTTONS (25 Hz), 0x158 ENGINE_DATA (100 Hz),
  0x17C POWERTRAIN_DATA (100 Hz), 0x326 SCM_FEEDBACK (10 Hz), 0x1BE BRAKE_MODULE (50 Hz, bazı Bosch).

### 2.3 Hyundai klasik (hyundai.h) — konum ve algoritma mesaj başına DEĞİŞİR
| ID | Sayaç | mod | Checksum konumu |
|---|---|---|---|
| 0x260 | `(data[7]>>4) & 0x3` | 4 | `data[7] & 0xF` |
| 0x386 | `((data[3]>>6)<<2) + (data[1]>>6)` | 16 | `((data[7]>>6)<<2) + (data[5]>>6)` |
| 0x394 | `(data[1]>>5) & 0x7` | 8 | `data[6] & 0xF` |
| 0x421 SCC12 | `data[7] & 0xF` | 16 | `data[7] >> 4` |
| 0x4F1 CLU11 | `(data[3]>>4) & 0xF` | 16 | yok (yalnız sayaç kontrolü) |
- **Algoritma:** 0x386 = **popcount** (sayaç/checksum bitleri hariç tüm bitlerin sayısı)
  `(popcount ^ 9) & 15`; diğerleri = nibble-toplamı `(16 - sum % 16) % 16`
  (checksum'ın kendi baytı maskelenerek dahil edilir).
- 0x386/0x394'te sayaç ve checksum **bit-field'lara bölünmüş, 2-2 bit dağınık** —
  ardışık olmayan bit konumları! Legacy mod (eski araçlar): sayaç+checksum YOK.

### 2.4 Hyundai CAN-FD (hyundai_canfd.h + hyundai_common.h) — 16-bit CRC
- **Sayaç:** 8 baytlık karelerde `data[1] >> 4` (mod 16); 16/24/32 baytlık karelerde `data[2]`
  (mod 256). **Checksum:** `data[0..1]` üzerinde **16-bit**.
- Algoritma (`hyundai_common_canfd_compute_checksum`): CRC-16 (LUT), `data[2..len)` +
  ID'nin 2 baytı; `xorout` uzunluğa bağlı: len=24 → `0x819D`, len=32 → `0x9F5B`.
- Mesajlar: 0x35/0x100/0x105 ACCELERATOR (100 Hz), 0x175 (50 Hz), 0xa0/0xea (100 Hz),
  0x1a0 SCC_CONTROL (50 Hz), 0x1cf CRUISE_BUTTON (50 Hz, sayaç mod 16, checksum yok).

### 2.5 Subaru global (subaru.h) — checksum İLK baytta
- **Sayaç:** `data[1] & 0xF` (mod 16). **Checksum:** `data[0]`;
  `chksum = addr_lo + addr_hi + Σ data[1..len)` (toplamsal, ID dahil).
- Mesajlar: 0x40 Throttle (100 Hz), 0x119 Steering_Torque (50 Hz), 0x13a Wheel_Speeds (50 Hz),
  0x13c Brake_Status (50 Hz), 0x240 CruiseControl (20 Hz).
- Subaru preglobal (subaru_preglobal.h): sayaç/checksum YOK (kodda açık TODO).


### 2.6 Tesla Model 3/Y (tesla.h) — mesaj başına değişken konum
- **Sayaç:** 0x2b9 DAS_control `data[6]>>5` (mod 8); 0x488 DAS_steeringControl `data[2]&0xF` (mod 16);
  0x257/0x118/0x145/0x286/0x311 `data[1]&0xF` (mod 16); 0x155 `data[6]>>4` (mod 16);
  0x370 EPAS3S `data[6]&0xF` (mod 16).
- **Checksum:** 0x370/0x2b9/0x155 → bayt 7; 0x488 → bayt 3; 0x257/0x118/0x145/0x286/0x311
  → **bayt 0**. Algoritma: `chksum = addr_lo + addr_hi + Σ data[i != chksum_byte]` (toplamsal,
  ID dahil, checksum baytı atlanır — Toyota'dan fark: uzunluk DAHİL DEĞİL).
- Öğretici örnek: **aynı marka içinde checksum baytı 0 veya 3 veya 7 olabilir** →
  detektör checksum konumunu bayt-bayıt taramalı.

### 2.7 Ford (ford.h) — toplayan set {0..255}, 0xFF−sum, ARDIŞIK OLMAYAN kapsam
- 0x415 BrakeSysFeatures: sayaç `(data[2]>>2)&0xF` (mod 16), checksum **data[3]**:
  `0xFF − (data[0]+data[1] + data[2]>>6 + (data[2]>>2)&0xF)` — kapsam bit-seviyesinde parçalı!
- 0x91 Yaw_Data_FD1: sayaç `data[5]` (**mod 256**), checksum **data[4]**:
  `0xFF − (data[0..1] + data[2..3] + data[5] + data[6] parça-biti)` — 16-bit alanlar
  2 bayt toplanarak, kalite bitleri ayrı ayrı eklenerek.
- **covered-bytes modeli bu markayla çöker:** kapsanan bitler ardışık bayt aralığı DEĞİL
  (data[2]'nin yalnız üst 2 + orta 4 biti; data[6]'nın 4 biti) → PR-2 kapsamı
  **bayt-mask taraması** olarak kurgulanmalı (önek/son ek yeterli değil).
- 0x202 EngVehicleSpThrottle2: gerçek araçta sayaç atlama/+2 ECU hatası yorumu —
  Ford'un Bronco kamerası "yalnız kalite bayrağı"na bakar → opendbc bu mesajda checksum+sayaç
  kontrolünü kapatmıştır. **Ders:** match_ratio %100 beklenmez; %90+ "aday" eşik gerçekçi.

### 2.8 VW platform ailesi (volkswagen_common.h + mqb/mlb/meb/pq)
- **MQB/MEB (volkswagen_common.h):** sayaç `data[1]&0xF` (mod 16 — "LSB 8'de tutarlı" yorumu),
  checksum `data[0]` = **CRC-8/8H2F-AUTOSAR varyantı** (poly 0x2F, init 0xFF):
  `data[1..len)` üzerinden LUT-CRC → **sayaç değerine göre mesaj-özel 16 sabitlik XOR tablosu**
  → tekrar LUT → `^0xFF`. Sabit tabloları dosyada tam mevcut (LH_EPS_03 tümü 0xF5;
  MOTOR_20, GRA_ACC_01, QFK_01, ESC_51, ESP_21, Motor_51 mesaj-özel).
- **MLB:** sayaç+checksum konumları aynı; **checksum doğrulaması implement edilmemiş**
  (kod TODO'su) → keşif motoru MLB kayıtlarında "bilinmeyen varyant" görmeyi beklemeli.
- **MEB (volkswagen_meb.h):** MQB çekirdeği + MEB-özel sabit tabloları; ayrıca uzunluk-başına
  kapsam kayması (`len=28/60/44` varyantları — CAN-FD) `volkswagen_meb_alt_crc` ile.
- **PQ (volkswagen_pq.h):** bambaşka: **XOR** — `chksum = XOR(data[i != chksum_byte])`,
  checksum baytı 0 (5 baytlık HCA_1 dahil) veya 7 (MOTOR_5); sayaç `data[1]>>4` (0x0D0) ve
  `data[2]>>4` (0x38A), mod 16. → Aynı markada 3 farklı algoritma ailesi (AUTOSAR-CRC,
  XOR, yok) bir arada.


### 2.9 Chrysler klasik (chrysler.h + chrysler_common.h) — CRC-8/SAE-J1850 bit-serial
- **Sayaç:** `data[6]>>4` (mod 16; RAM DT platformunda da aynı kural). **Checksum:** SON bayt.
- **Algoritma:** bit-serial gerçekleme — **poly 0x1D, init 0xFF, final `~chksum` → CRC-8/SAE-J1850
  (xorout 0xFF) birebir** (Greg Cook kataloğuyla eşleme bu oturumda doğrulandı).
  Kaynak yorumu: illmatics.com "Remote Car Hacking" (Miller & Valasek çalışması).
- Mesajlar (Pacifica): EPS_2 0x220, ESP_1 0x140, ECM_5 0x22F, DAS_3 0x1F4; RAM DT:
  0x31/0x83/0x9D/0x99; 514 (Pacifica hız) hariç tutulur.
### 2.10 Chrysler CUSW (chrysler_cusw.h) — konum farkı: sondan 2. bayt
- Sayaç `data[len-2]&0xF` (mod 16); checksum SON bayt (klasikle aynı), algoritma klasik
  SAE-J1850 CRC. Mesajlar: 0x1E4/0x1E8/0x1EC/0x1FE/0x2EC.
### 2.11 GM / Nissan / Mazda / body — koruma YOK (negatif kontroller)
- **GM (gm.h):** "TODO: do checksum and counter checks" — tüm RX mesajları ignore.
  Volt/Bolt/Escalade 0xBE uzunluk varyantları yalnız varlık kontrolünde.
- **Nissan (nissan.h), Mazda (mazda.h), body (body.h), Subaru preglobal:** hooks'ta
  get_counter/get_checksum **tanımsız**; tüm mesajlar ignore_checksum+ignore_counter.
- **Anlamı:** bu platformların kayıtlarında detektör **hipotez üretmemeli** —
  yanlış-pozitif ölçümü için negatif-kontrol test malzemesi.

## 3. Özet tablo — "marka profili" eşleştirme seti (ID iması)
| Marka/mod | Sayaç konumu (mod) | Checksum konumu | Algoritma ailesi |
|---|---|---|---|
| Toyota klasik | — (yok) | son bayt | topla: addr+len+data (len dahil) |
| Honda | son bayt üst nibble (4) | son bayt alt nibble | nibble-topla, ID dahil, (8−sum)&0xF |
| Hyundai klasik | mesaj başına bit-field (4/8/16) | mesaj başına | popcount (0x386) veya nibble-topla |
| Hyundai CAN-FD | data[1]>>4 (16) / data[2] (256) | data[0..1] | CRC-16 + ID + len-bağımlı xorout |
| Subaru | data[1]&0xF (16) | **ilk bayt** | topla: addr+data[1..) |
| Subaru preglobal | yok | yok | — |
| Tesla | mesaj başına (8/16) | bayt 0/3/7 | topla: addr+data (checksum baytı hariç) |
| Ford | mesaj başına (16/256) | bayt 3/4 | 0xFF − parça-biti toplam (bit-mask kapsam) |
| VW MQB/MEB | data[1]&0xF (16) | bayt 0 | CRC-8/8H2F + sayaç-magic XOR |
| VW MLB | data[1]&0xF (16) | bayt 0 | (doğrulanmamış — TODO) |
| VW PQ | data[1]>>4 / data[2]>>4 (16) | bayt 0 / 7 | düz XOR (checksum baytı hariç) |
| Chrysler | data[6]>>4 (16) | son bayt | CRC-8/SAE-J1850 (0x1D/0xFF/0xFF) |
| Chrysler CUSW | data[len-2]&0xF (16) | son bayt | CRC-8/SAE-J1850 |
| GM / Nissan / Mazda / body | yok | yok | — |

## 4. PR-2'ye doğrudan aktarılan tasarım dersleri
1. **Konum değişkenliği:** sayaç/checksum baytı 0..7 aralığında herhangi bir yerde olabilir
   (Subaru ilk bayt, Honda/Toyota/Chrysler son bayt, VW bayt 0-1, Tesla bayt 0/3/7) →
   pozisyon taraması zorunlu; "son bayt" varsayımı YANLIŞ olur.
2. **Bit-field sayaçlar:** Hyundai 0x386 (`(d3>>6)<<2 | d1>>6`) ardışık olmayan bitlerde →
   bit-field detektörü mask-temelli olmalı (bayt hizalı varsayım yetersiz).
3. **mod seti:** {4, 8, 16, 256} (max_counter 3/7/15/255) + Ford'un 8-bit tam-bayt varyantı.
4. **Algoritma aileleri (arama sırası):** düz toplamsal (ID dahil/hariç × len dahil/hariç =
   4 varyant) → nibble-toplama → popcount → 0xFF−sum → XOR → CRC-8 katalog
   (crc_referansi.md §5 sıralaması).
5. **CRC-8/SAE-J1850 gerçek dünya kanıtı:** Chrysler = katalog parametrelerinin birebir
   gerçeklemesi → parametrik CRC gerçeklemesinin test vektörü olarak kullanılır.
6. **Sayaç-magic (VW) deseni:** CRC eşleşmesi ~1/16'da platoda kalırsa sayaç-koşullu XOR
   tablosu hipotezi (16 sabit) ayrı taranır — pratikte sadece bu desenle ayrıştırılır.
7. **Tolerans gerçekliği:** Ford ECU hataları (sayaç atlama, tek kare checksum hatası) →
   match_ratio eşikleri: ≥0.99 "kesin", ≥0.90 "aday", ≥0.8 "ipucu" (tasarım §4 ile uyumlu).
8. **Negatif setler:** GM/Nissan/Mazda/preglobal-Subaru kayıtları yanlış-pozitif ölçümü için
   birim-test malzemesi (hipotez üretim oranı ~0 beklenir).
9. **Frekans alanı:** RxCheck `frequency` alanı (10/25/33/50/83/100 Hz) → cycle_time
   hipotezinin marka-profil doğrulaması.
10. **Kalite bayrağı kanalı** (get_quality_flag_valid) ayrı bir doğrulama sinyalidir —
    bitstats sınıflandırmasına "quality flag" adayı olarak eklenmeli (Toyota 0x260 bit 3
    "angle initializing" örneği).


