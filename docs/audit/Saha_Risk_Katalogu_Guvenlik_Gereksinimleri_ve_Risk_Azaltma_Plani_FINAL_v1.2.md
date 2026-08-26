# Universal CAN Diagnostic & Telemetry Tool
## Saha Risk Kataloğu, Güvenlik Gereksinimleri, Risk Register ve Saha Doğrulama Planı

**Doküman türü:** Safety / Risk Assessment / Safety Requirements / Field Validation
**Proje:** Universal CAN-Bus Diagnostic & Telemetry Tool
**Kapsam:** Automotive / Heavy-Duty / Marine / J1939 / NMEA 2000 / ISO-TP / UDS / CAN / CAN-FD
**Durum:** Pre-Field Validation
**Tarih:** 2026-08-25
**Versiyon:** 1.2
**Kritiklik:** HIGH / SAFETY-RELEVANT
**Temel ilke:** Safe-by-default, fail-safe, fail-silent diagnostic interface

---

## 0. v1.1 → v1.2 Değişiklik Özeti

Bu sürüm, v1.1 dokümanının mevcut organizasyonunu koruyarak aşağıdaki boşlukları kapatır:

- Risk seviyelerine ölçülebilir **Severity / Likelihood / Detectability** boyutları eklendi.
- "Risk = Severity × Detectability" yerine üç boyutlu risk değerlendirme yaklaşımı getirildi.
- Global ve per-message **TX rate policy**, burst limit ve bus-utilization ölçümü eklendi.
- Fiziksel acil izolasyon ile yazılımsal TX stop birbirinden ayrıldı.
- **TX Watchdog / Safety Supervisor** mimarisi eklendi.
- Database / decoder / adapter firmware **version skew** ve hash traceability eklendi.
- Decoder confidence değerinin TX yetkilendirmesindeki rolü tanımlandı.
- Confidence'ın tek başına TX izni vermediği açıkça belirtildi.
- NMEA 2000 için **ISO Transport Protocol / Fast Packet / proprietary transport** ayrımı eklendi.
- ISO-TP addressing/context validation gereksinimleri genişletildi.
- Ring buffer için açık overflow policy eklendi.
- Replay güvenlik filtresi ve Address Claim / network-management riski eklendi.
- Aktüatör testleri için LOTO benzeri fiziksel güvenlik interlock'u eklendi.
- UNKNOWN state için raw hex görünürlüğü eklendi; UNKNOWN veri alarm/telemetry kaynağı olamaz.
- Fault-triggered **SUSPICIOUS_ACTIVITY** capture ve pre-trigger/post-trigger kayıt mekanizması eklendi.
- Güvenli durumları yöneten formal **Safety State Machine** eklendi.
- Fail-silent diagnostic interface prensibi eklendi.
- Genişletilmiş Risk Register oluşturuldu.
- Field Readiness Checklist ölçülebilir gereksinimlerle genişletildi.

---

## İçindekiler

1. Amaç ve Kapsam
2. Temel Güvenlik İlkeleri
3. Risk Metodolojisi ve Sınıflandırma
4. Kritik Güvenlik Mimarisi
5. Safety State Machine
6. PASSIVE / LISTEN-ONLY Mode
7. CAN Physical Layer Riskleri
8. Protocol Identification Riskleri
9. J1939 Riskleri
10. NMEA 2000 Riskleri
11. Manufacturer-Specific / Proprietary Riskleri
12. Decode Riskleri
13. Telemetry Riskleri
14. Buffer / Queue / Performance Riskleri
15. Timestamp / Timebase Riskleri
16. CAN Error State / Bus-Off Riskleri
17. ISO-TP Riskleri
18. UDS / Diagnostic Riskleri
19. TX Riskleri
20. TX Safety Supervisor ve Watchdog
21. Replay Riskleri
22. Configuration ve Version Skew Riskleri
23. Network Topology / Gateway Riskleri
24. Firmware / Adapter / USB Riskleri
25. Human Factors ve Physical Safety
26. UI Safety Requirements
27. Confidence / Trust / Provenance Modeli
28. Decoder Database Güvenliği
29. Forensic Logging ve Audit Trail
30. UNKNOWN / PROPRIETARY State
31. Simulation Mode
32. Hardware-in-the-Loop
33. Saha Test Kademeleri
34. Gerçek Tekne İçin Minimum Güvenlik Kuralları
35. Risk Register
36. Quantifiable Safety Metrics
37. Safe-by-Default Requirements
38. Fail-Safe / Fail-Silent Requirements
39. Decoder Safety Rule
40. Diagnostic Safety Rule
41. Replay Safety Rule
42. Field Readiness Checklist
43. Saha Acil Durum Prosedürü
44. Suspicious Activity / Rollback Policy
45. Validation Evidence ve Release Gate
46. Final Safety Statement
47. Kaynaklar / Referanslar

---

# 1. Amaç ve Kapsam

Bu dokümanın amacı, Universal CAN Diagnostic & Telemetry Tool'un laboratuvar dışında gerçek araç, ağır vasıta, marine ve tekne sistemlerinde kullanılmasından önce karşılaşabileceği teknik, yazılımsal, protokol, elektriksel, operasyonel ve insan kaynaklı riskleri sistematik biçimde tanımlamak ve her risk için uygulanabilir azaltma/tespit/doğrulama gereksinimleri oluşturmaktır.

Sistem yalnızca bir CAN viewer değildir. Mimari olarak:

```text
CAN Interface
    ↓
Frame Capture
    ↓
Protocol Identification
    ↓
Transport / Reassembly
    ↓
Decoder
    ↓
Telemetry
    ↓
Diagnostics
    ↓
Potential TX / Control
```

zincirine sahip olduğu için safety-relevant diagnostic software olarak ele alınmalıdır.

Bu doküman bir ürün sertifikasyonu veya üretici servis prosedürü yerine geçmez. Gerçek saha kullanımından önce ilgili araç/tekne üreticisinin servis dokümantasyonu, network topolojisi, ECU prosedürleri ve uygulanabilir standartlar ayrıca doğrulanmalıdır.

---

# 2. Temel Güvenlik İlkeleri

## 2.1 Passive First

İlk ve varsayılan çalışma şekli:

```text
LISTEN ONLY / PASSIVE
```

olmalıdır.

## 2.2 Unknown Is Valid

Programın bilmediği mesajı `UNKNOWN` olarak bırakması, yanlış anlamlandırmasından daha güvenlidir.

## 2.3 Standard ≠ Observed ≠ Supported ≠ Decoded ≠ Verified

Aşağıdaki kavramlar ayrı tutulmalıdır:

```text
Standard Definition
Observed On Bus
Advertised / Supported By ECU
Successfully Parsed
Verified Against Known Source
```

Bir PGN'nin standartta bulunması, hedef ECU'nun onu kullandığı anlamına gelmez.

## 2.4 RX ≠ TX

RX/Decode pipeline'ın TX pipeline'a doğrudan erişimi olmamalıdır.

## 2.5 Safe by Default

Beklenmeyen durumda:

```text
TX = DISABLED
```

olmalıdır.

## 2.6 Fail-Silent Diagnostic Interface

Diagnostic cihazı hata verdiğinde, hedef sistemin ağını aktif olarak bozmak yerine mümkün olan en güvenli pasif duruma geçmelidir.

## 2.7 Human-in-the-Loop

Yüksek riskli diagnostic/control işlemleri açık kullanıcı yetkilendirmesi olmadan başlamamalıdır.

---

# 3. Risk Metodolojisi ve Sınıflandırma

## 3.1 Safety Impact Level

| Seviye | Tanım |
|---|---|
| L0 | Sadece gözlem/görüntüleme; fiziksel sistem etkisi beklenmez |
| L1 | Yanlış telemetry/decode; fiziksel etki doğrudan beklenmez |
| L2 | CAN network davranışını veya iletişim durumunu etkileyebilir |
| L3 | ECU davranışını veya diagnostic state'i değiştirebilir |
| L4 | Fiziksel sistem, hareket, propulsion, steering veya operasyon güvenliğini etkileyebilir |

## 3.2 Risk Boyutları

Risk önceliklendirmesinde aşağıdaki boyutlar ayrı değerlendirilmelidir:

| Boyut | Ölçek | Soru |
|---|---|---|
| Severity (S) | S1–S4 | Sonuç ne kadar ağır? |
| Likelihood / Occurrence (L) | L1–L4 | Gerçekleşme olasılığı ne kadar? |
| Detectability (D) | D1–D4 | Hata kullanıcı/system tarafından ne kadar erken fark edilebilir? |

Önceliklendirme için basit RPN benzeri skor kullanılabilir:

```text
Risk Score = S × L × D
```

Bu skor, güvenlik sertifikasyonu yerine mühendislik önceliklendirmesi içindir. Gerçek saha verisi geldikçe güncellenmelidir.

## 3.3 Detectability Kriteri

| D | Anlam |
|---|---|
| D1 | Hata anında ve belirgin şekilde tespit edilir |
| D2 | Normal monitoring ile kısa sürede tespit edilir |
| D3 | Özel telemetry/log incelemesi gerekir |
| D4 | Hata büyük ölçüde gizlidir; sonuç ortaya çıkana kadar fark edilmeyebilir |

## 3.4 Risk Class

| Skor | Sınıf |
|---:|---|
| 1–8 | LOW |
| 9–24 | MEDIUM |
| 25–39 | HIGH |
| 40–64 | CRITICAL |

> Risk Class eşikleri proje içi başlangıç eşikleridir; saha/HIL sonuçlarına göre kalibre edilmelidir.

---

# 4. Kritik Güvenlik Mimarisi

```text
                        USER / UI
                           │
                           ▼
                    ┌──────────────┐
                    │  SAFETY GATE │
                    └──────┬───────┘
                           │
              ┌────────────┴────────────┐
              │                         │
             RX                        TX
              │                         │
              ▼                         ▼
        ┌───────────┐            ┌─────────────┐
        │ CAN Driver│            │ TX Safety   │
        └─────┬─────┘            │ Supervisor  │
              │                  └──────┬──────┘
              ▼                         │
        ┌───────────┐               ┌────┴────┐
        │ Ring/Queue│               │Checks   │
        └─────┬─────┘               ├─────────┤
              │                     │Permission│
              ▼                     │Whitelist │
        ┌───────────────┐           │Rate Limit│
        │Protocol Detect│           │Payload   │
        └──────┬────────┘           │State     │
               │                    │Watchdog  │
               ▼                    └────┬─────┘
           Decoder                      │
               │                         ▼
               ▼                      CAN Driver
           Telemetry                      │
               │                         ▼
               ▼                      CAN BUS
            Logging
```

RX pipeline:

```text
CAN RX
→ Hardware/Frame Validation
→ Timestamp
→ Capture Buffer
→ Protocol Identification
→ Transport/Reassembly
→ Decoder
→ Telemetry
→ Logging
```

TX pipeline:

```text
User/Diagnostic Action
→ Safety State Check
→ Explicit Permission
→ Protocol State Check
→ Target/Address Validation
→ Confidence Check
→ ID Whitelist
→ Payload Validation
→ Per-ID Rate Limit
→ Global Bus-Load Limit
→ TX Watchdog Lease
→ Hardware TX
→ Audit Log
```

RX decoder'ın otomatik TX göndermesi yasaktır.

---

# 5. Safety State Machine

Sistem için açık bir safety state machine kullanılmalıdır.

```text
                 ┌─────────────┐
                 │   STARTUP   │
                 └──────┬──────┘
                        ▼
                 ┌─────────────┐
                 │     SAFE    │
                 │   TX OFF    │
                 └──────┬──────┘
                        ▼
                 ┌─────────────┐
                 │   PASSIVE   │
                 │   RX ONLY   │
                 └──────┬──────┘
                        │ explicit arm
                        ▼
                 ┌─────────────┐
                 │   ARMED TX  │
                 └──────┬──────┘
                        │ validated TX
                        ▼
                 ┌─────────────┐
                 │   ACTIVE    │
                 └──────┬──────┘
                        │ fault/event
                        ▼
                 ┌─────────────┐
                 │    FAULT    │
                 │  TX REVOKED │
                 └──────┬──────┘
                        ▼
                 ┌─────────────┐
                 │   PASSIVE   │
                 └─────────────┘
```

### State transition rules

- STARTUP → SAFE: her zaman TX kapalı.
- SAFE → PASSIVE: interface initialization başarılıysa.
- PASSIVE → ARMED TX: yalnızca açık kullanıcı eylemi + safety checks.
- ARMED TX → ACTIVE: yalnızca TX policy bütün koşulları sağlıyorsa.
- ACTIVE → FAULT: watchdog timeout, validation failure, bus-off, unexpected firmware response, fatal exception veya safety event.
- FAULT → PASSIVE: TX revoke ve queue flush tamamlandıktan sonra.
- FAULT durumundan otomatik olarak ACTIVE'e geçiş yasaktır.

---

# 6. PASSIVE / LISTEN-ONLY Mode

Uygulama varsayılan olarak PASSIVE / LISTEN-ONLY modunda başlamalıdır.

Bu modda:

- CAN frame alınabilir.
- Frame decode edilebilir.
- J1939 analiz edilebilir.
- NMEA 2000 analiz edilebilir.
- ISO-TP / NMEA transport reassembly yapılabilir.
- UDS mesajları okunabilir.
- Telemetry oluşturulabilir.
- Forensic log alınabilir.

Ancak:

> PASSIVE modunda hiçbir CAN frame gönderilmemelidir.

TX fonksiyonunun yalnızca UI'dan gizlenmesi yeterli değildir; software architecture ve adapter configuration seviyesinde de TX authorization bulunmamalıdır.

---

# 7. CAN Physical Layer Riskleri

## 7.1 Yanlış bitrate

Yanlış bitrate:

- CAN error
- ACK error
- Frame corruption
- Error Passive
- Bus-Off

oluşturabilir.

### Requirement

Connection öncesinde bitrate açıkça gösterilmelidir.

Önerilen configuration telemetry:

```text
Bitrate
Sample Point
CAN Mode
Data Bitrate (CAN-FD)
Channel
Interface
```

## 7.2 Classical CAN / CAN-FD karışıklığı

Classical CAN ve CAN-FD açıkça ayrı configuration state'leri olmalıdır.

## 7.3 11-bit / 29-bit ID

Standard ID / Extended ID ayrımı korunmalıdır.

J1939 ve NMEA 2000 ağlarında Extended CAN ID bağlamı doğrulanmalıdır.

## 7.4 CANH / CANL ters bağlantısı

Fiziksel bağlantı hatasıdır. Yazılım mümkünse traffic sanity-check sunmalıdır; yazılım kontrolü fiziksel doğrulamanın yerine geçmez.

## 7.5 Termination

Yanlış termination signal integrity ve intermittent communication sorunlarına neden olabilir.

## 7.6 Ground/reference

PC, adapter ve araç/tekne arasında ground farkları değerlendirilmeli; marine deployment'ta galvanik izolasyon gereksinimi açıkça tanımlanmalıdır.

## 7.7 İzolasyon

Gerçek saha için kullanılan CAN interface'in galvanik izolasyon özellikleri, çalışma gerilimleri ve transient dayanımı doğrulanmadan saha bağlantısı yapılmamalıdır.

## 7.8 Voltage / transient

Araç ve marine sistemlerde voltage spike, brownout, surge, ESD, EMI ve load-dump benzeri transientler dikkate alınmalıdır.

### Requirement

CAN interface için en azından aşağıdaki donanım parametreleri dokümante edilmelidir:

```text
Operating Voltage Range
CAN Common-Mode Range
Galvanic Isolation: YES/NO
Transient Protection: YES/NO
ESD Protection: YES/NO
TVS Specification
Connector Rating
```

TVS, seri direnç veya başka koruma elemanları cihazın gerçek şemasına göre seçilmelidir; tek bir bileşen bütün saha risklerinin garantisi değildir.

---

# 8. Protocol Identification Riskleri

## 8.1 Yanlış auto-detection

Program "This is J1939" sonucunu kesin gerçek olarak sunmamalıdır.

```text
Protocol Confidence:
HIGH
MEDIUM
LOW
UNKNOWN
```

## 8.2 Protocol context collision

Aynı CAN ID farklı network/context'lerde farklı anlamlar taşıyabilir. Yalnızca ID üzerinden mutlak anlam çıkarılmamalıdır.

## 8.3 Auto-detection policy

Auto-detection yalnızca öneri üretmeli; kritik aktif işlemler için protocol selection doğrulanmalıdır.

---

# 9. J1939 Riskleri

## 9.1 Standard PGN = kesin destek değildir

Bir PGN'nin standarda ait olması, hedef ECU'nun onu kullandığı veya desteklediği anlamına gelmez.

System metadata:

```text
STANDARD DEFINITION
OBSERVED ON BUS
SUPPORTED BY ECU
```

ayrımını korumalıdır.

## 9.2 Standard PGN = tüm SPN'ler aktif değildir

Bir ECU PGN içindeki yalnızca bazı SPN'leri destekleyebilir.

## 9.3 Not Available değerleri

Protokolün tanımladığı `Not Available`/reserved özel değerleri fiziksel veri olarak gösterilmemelidir.

## 9.4 Reserved bits

Reserved alanlar telemetry olarak yorumlanmamalıdır.

## 9.5 Source Address

Source Address kalıcı ECU identity olarak kabul edilmemelidir.

## 9.6 Address Claim

Dynamic address claim sonrası eski SA→ECU mapping'leri otomatik olarak sonsuza kadar geçerli sayılmamalıdır.

## 9.7 Proprietary PGN

Proprietary mesajlar standard decoder ile zorla decode edilmemelidir.

Doğru durum:

```text
PROPRIETARY / UNKNOWN
```

---

# 10. NMEA 2000 Riskleri

NMEA 2000'i J1939 ile benzerlikleri nedeniyle aynı protocol stack olarak varsaymak tehlikelidir. PGN/addressing yapısında ortaklıklar olsa da NMEA 2000 kendine özgü semantic ve transport kullanımına sahiptir.

Özellikle NMEA 2000 cihaz dokümantasyonlarında hem **ISO Transport Protocol** PGN'leri (ör. 060160 ve 060416) hem de **Fast-packet proprietary** PGN'leri (ör. 126720) görülebilmektedir. citeturn493530search0turn493530search6

### Requirement

NMEA 2000 transport layer aşağıdaki durumları ayırmalıdır:

```text
Single Frame
ISO Transport Protocol
Fast Packet
Proprietary / Vendor-specific Transport
```

J1939 transport assumptions NMEA 2000 traffic'e körlemesine uygulanmamalıdır.

### Ek riskler

- Yanlış PGN semantic mapping
- Manufacturer Code / Industry Group context kaybı
- Fast Packet sequence/reassembly hatası
- ISO Transport Protocol ile Fast Packet'in karıştırılması
- Address Claim / Commanded Address işlemlerinin yanlış yorumlanması
- Proprietary PGN'nin standard PGN sanılması

NMEA 2000'de ISO Address Claim ve ISO transport PGN'lerinin de bulunduğu vendor dokümantasyonlarında açıkça görülmektedir; dolayısıyla "NMEA 2000 = yalnızca Fast Packet" yaklaşımı da yanlıştır. citeturn493530search0turn493530search7

---

# 11. Manufacturer-Specific / Proprietary Riskleri

## 11.1 Üretici özel mesajın yanlış decode edilmesi

Aynı CAN ID farklı üreticilerde farklı anlamlara sahip olabilir.

## 11.2 Model / firmware farkı

Aynı ECU modelinin firmware sürümleri arasında PGN, SPN, timing veya diagnostic behavior farklılaşabilir.

## 11.3 Decoder source tracking

Decoder database her definition için en az:

```text
STANDARD / MANUFACTURER / MODEL / FIRMWARE / UNKNOWN
```

kaynağını taşımalıdır.

---

# 12. Decode Riskleri

## 12.1 Endianness

Yanlış byte order fiziksel değeri tamamen değiştirebilir.

## 12.2 Signed / unsigned

Signed/unsigned interpretation açıkça tanımlanmalıdır.

## 12.3 Bit numbering

Start bit / bit length / byte order hataları yanlış telemetry üretir.

## 12.4 Scaling

Raw → physical conversion database ile doğrulanmalıdır.

## 12.5 Offset

Offset ayrı ve versioned olarak saklanmalıdır.

## 12.6 Unit

°C/°F, bar/kPa/psi, rpm/rad/s, km/h/mph, V/mV vb. unit'ler karıştırılmamalıdır.

## 12.7 Counter / CRC / Checksum

Desteklenen protokollerde integrity alanları doğrulanmadan signal `VALID` kabul edilmemelidir.

## 12.8 Semantic validity

Bir raw value matematiksel olarak decode edilebilse bile fiziksel olarak geçerli olmayabilir. Range/enum/reserved-state validation uygulanmalıdır.

---

# 13. Telemetry Riskleri

## 13.1 Stale data

Her signal en az:

```text
Value
Timestamp
Age
Validity
Status
Source
Confidence
```

taşımalıdır.

Örnek:

```text
RPM: 1500
Age: 73 ms
Status: VALID
```

ve:

```text
RPM: 1500
Age: 5.2 s
Status: STALE
```

## 13.2 Frame loss

```text
Received
Processed
Dropped
Rejected
```

istatistikleri ayrı gösterilmelidir.

## 13.3 Decoder backlog

Queue depth ve processing latency ölçülmelidir.

## 13.4 False verified state

`Decoded` bir değerin `Physically Verified` gibi sunulması yasaktır.

---

# 14. Buffer / Queue / Performance Riskleri

## 14.1 Ring buffer overflow

Overflow durumunda policy önceden tanımlanmalıdır.

Önerilen seçenekler:

```text
DROP_OLDEST
DROP_NEWEST
BLOCK_PRODUCER
MULTI_QUEUE
```

### Önerilen kullanım

- **Live telemetry:** çoğu durumda `DROP_OLDEST`; güncel veri korunur.
- **Forensic raw capture:** çoğu durumda `DROP_NEWEST` + explicit dropped counter; kayıt bütünlüğü korunur.
- **Critical diagnostic state:** ayrı bounded queue veya explicit back-pressure.

Global tek policy yerine queue amacına göre policy seçilmelidir.

## 14.2 UI bottleneck

Her frame'de UI repaint yapılmamalıdır.

## 14.3 Disk I/O bottleneck

Log writer CAN reception'dan ayrı worker/queue üzerinde çalışmalıdır.

## 14.4 Zero-loss claim

Sistem gerçekten sıfır frame loss garanti edemiyorsa UI'da `0% packet loss` gibi doğrulanamaz claim gösterilmemelidir.

---

# 15. Timestamp / Timebase Riskleri

## 15.1 Host vs hardware timestamp

```text
Host Timestamp
Hardware Timestamp
```

ayrılmalıdır.

## 15.2 Clock drift

Uzun süreli capture'larda drift raporlanmalıdır.

## 15.3 Monotonic clock

Latency ve timeout ölçümlerinde wall-clock yerine mümkün olduğunca monotonic time kullanılmalıdır.

---

# 16. CAN Error State / Bus-Off Riskleri

Program mümkünse aşağıdaki durumları izlemelidir:

```text
Error Active
Error Passive
Bus Off
ACK Error
Bit Error
Stuff Error
CRC Error
Form Error
```

`CONNECTED` göstergesi yalnızca USB cihazının bağlı olduğunu değil, mümkün olduğu ölçüde gerçek CAN controller state'ini yansıtmalıdır.

### Bus-Off policy

Bus-Off olduğunda:

```text
TX = DISABLED
Capture state = preserved
Error event = logged
Automatic recovery = policy-controlled
```

olmalıdır.

Otomatik recovery sırasında TX'in yeniden aktifleşmesi varsayılan olarak yasaktır.

---

# 17. ISO-TP Riskleri

## 17.1 SF / FF / CF / FC state machine

Transport state açıkça modellenmelidir.

## 17.2 Sequence Number

CF sequence number uyuşmazlığı payload'ı `INVALID` yapmalıdır.

## 17.3 Flow Control

```text
BS
STmin
FS
```

alanları doğru yorumlanmalıdır.

## 17.4 Timeout

Yarım kalan transferler bounded lifetime'a sahip olmalıdır.

## 17.5 Address / N_AI context validation

Reassembly session'ı yalnızca uygun addressing context ile eşleştirilmelidir.

```text
CAN ID / Addressing Mode
        ↓
N_AI / Session Context
        ↓
Payload Reassembly
```

Yanlış session association durumunda payload `INVALID_CONTEXT` olarak işaretlenmelidir.

### TX güvenliği

Reassembled payload'ın diagnostic TX'e ulaşabilmesi için ayrıca:

- Target validation
- Address validation
- Diagnostic session validation
- Confidence validation
- TX whitelist

gereklidir.

---

# 18. UDS / Diagnostic Riskleri

Bu bölüm HIGH / CRITICAL safety relevance taşır.

## 18.1 Diagnostic Session

```text
Default
Extended
Programming
```

gibi session state'leri explicit state machine ile takip edilmelidir.

## 18.2 Security Access

Seed/Key işlemleri açık yetkilendirme ve hedef doğrulaması olmadan çalıştırılmamalıdır.

## 18.3 ECU Reset

Varsayılan olarak disabled.

## 18.4 DTC Clear

Şartlar:

```text
Explicit User Action
+
Clear Confirmation
+
Target Verification
+
Audit Log
```

## 18.5 RoutineControl / actuator control

Fiziksel davranış oluşturabilecek rutinler ayrı HIGH-RISK category altında tutulmalıdır.

## 18.6 WriteData / Programming

Default disabled; PASSIVE mode'da erişilemez; ayrı release/test authorization gerekir.

---

# 19. TX Riskleri

## 19.1 Yanlış CAN ID

Target validation olmadan TX yapılamaz.

## 19.2 Yanlış DLC

Payload length/DLC validation zorunludur.

## 19.3 Yanlış payload

Payload semantic validation gerekir.

## 19.4 Yanlış timing

Timing protocol/database profile ile uyumlu olmalıdır.

## 19.5 TX flooding

Global ve per-ID rate policy uygulanmalıdır.

## 19.6 TX storm

Repeated-send döngüleri bounded olmalıdır.

## 19.7 Reconnect sırasında TX

Reconnect sonrası TX yeniden authorize edilmeden gönderim yapılamaz.

## 19.8 TX default disabled

```text
TX = DISABLED
```

ile başlanmalıdır.

## 19.9 Bus utilization

TX başlamadan önce mümkünse mevcut bus load ölçülmelidir.

---

# 20. TX Safety Supervisor ve Watchdog

## 20.1 Safety Supervisor

TX işlemini yalnızca business logic'in kararına bırakmak yasaktır.

Safety Supervisor aşağıdaki koşulları merkezi olarak kontrol etmelidir:

```text
Safety State
Protocol State
Target Identity
Confidence
Whitelist
Payload Validity
Timing
Rate Limit
Bus Utilization
Adapter State
Watchdog Lease
User Authorization
```

## 20.2 Watchdog / heartbeat

UI heartbeat tek başına yeterli değildir.

Önerilen mimari:

```text
Application
   │
   ├── UI Heartbeat
   ├── TX Worker Heartbeat
   ├── Safety Supervisor
   └── Adapter State Monitor
             │
             ▼
       TX Authorization Lease
             │
          timeout
             ▼
       TX REVOKE / Queue Flush
             │
             ▼
          PASSIVE
```

### Başlangıç güvenlik parametresi

`TX_WATCHDOG_TIMEOUT_MS` gibi bir parameter tanımlanabilir; başlangıç doğrulama değeri örneğin 500 ms olabilir. Bu değer **evrensel standart değil**, HIL/adapter davranışı ile doğrulanacak bir proje parametresidir.

## 20.3 Global exception / panic handling

Fatal exception:

```text
Exception
→ Safety Supervisor
→ TX Authorization Revoke
→ TX Queue Flush
→ Adapter Safe State
→ FAULT / PASSIVE
→ Audit Log
```

akışını tetiklemelidir.

Automatic restart sonrası TX'in yeniden başlaması yasaktır.

---

# 21. Replay Riskleri

Replay default olarak disabled olmalıdır.

```text
LOG
 ↓
REPLAY ENGINE
 ↓
REPLAY SAFETY FILTER
 ↓
TX SAFETY SUPERVISOR
 ↓
CAN BUS
```

## Replay filter

Varsayılan olarak aşağıdaki kategoriler bloklanmalıdır:

```text
Address Claim / Network Management
ECU Reset
Diagnostic Write
Actuator Control
Programming
Security Access
Unknown / Proprietary TX
Unverified commands
```

Replay sırasında canlı network'e dönülmesiyle log replay'in karışmaması için UI'da açık state gösterilmelidir:

```text
SIMULATION
LOG REPLAY
LIVE CAN
```

birbirinden ayrı olmalıdır.

## Replay loop

Replay loop veya repeated replay bounded olmalıdır.

---

# 22. Configuration ve Version Skew Riskleri

## 22.1 Eski configuration

Önceki session'dan kalan bitrate/channel/protocol ayarları sessizce kullanılmamalıdır.

## 22.2 Wrong profile

```text
Automotive
Heavy-Duty
Marine
NMEA 2000
J1939
```

profile'ları açıkça gösterilmelidir.

## 22.3 Database / firmware version skew

Aşağıdaki metadata session başında kaydedilmelidir:

```text
Application Version
Adapter Firmware Version
Decoder Version
Database Version
Database SHA-256
Selected Profile
Protocol Revision
ECU Identification (when safely available)
```

## 22.4 Compatibility state

Database ile ECU firmware ilişkisi:

```text
COMPATIBLE
PARTIALLY_COMPATIBLE
UNKNOWN
INCOMPATIBLE
```

olarak ifade edilmelidir.

Database hash'i aynı değilse güvenlik-kritik TX operations otomatik olarak `REQUIRES_REVIEW` durumuna alınabilir.

---

# 23. Network Topology / Gateway Riskleri

Gerçek sistemlerde:

```text
Engine CAN
Navigation CAN
Instrument CAN
NMEA 2000
Diagnostic CAN
Proprietary CAN
```

gibi farklı network segmentleri bulunabilir.

## 23.1 Wrong bus

Yanlış bus'a bağlanmak gerçek risk kabul edilmelidir.

## 23.2 Gateway

Gateway:

- filtering
- routing
- translation
- rate limiting
- address mapping

uygulayabilir.

PC'nin gördüğü network bütün ECU network'ünü temsil etmeyebilir.

## 23.3 Gateway loop

CAN A ↔ Gateway ↔ CAN B gibi yapılarda yanlış bridge configuration loop ve flooding oluşturabilir.

Diagnostic tool'da bridge/replay fonksiyonu bulunuyorsa default disabled olmalıdır.

---

# 24. Firmware / Adapter / USB Riskleri

## 24.1 Firmware mismatch

PC software ile adapter firmware arasında:

```text
Protocol Version
Frame Format
Timestamp Format
CAN Mode
TX Semantics
```

uyumsuzluğu olabilir.

## 24.2 USB disconnect

USB disconnect:

- capture interruption
- frame loss
- unexpected reconnect
- queued TX

risklerini doğurabilir.

Reconnect sonrası:

```text
TX MUST REMAIN DISABLED
```

## 24.3 Adapter TX queue

Emergency veya watchdog event'inde adapter içindeki queued TX frame'lerin durumu ayrıca doğrulanmalıdır.

---

# 25. Human Factors ve Physical Safety

Kullanıcı hataları sistem güvenliğinin parçasıdır.

Riskli işlemler açıkça ayrılmalıdır:

```text
Connect
Transmit
Replay
Diagnostic Session
ECU Reset
DTC Clear
Routine Control
Actuator Test
Programming
```

## 25.1 Physical / Environmental Safety

Actuator Test / RoutineControl gibi işlemler fiziksel hareket oluşturabilir.

Aktüatör testinden önce:

- Makine/motor üretici prosedürüne göre güvenli durumda olmalı.
- Hareketli parçalar ve hazard zone kontrol edilmeli.
- Yüksek riskli testler mümkünse ikinci bir kişi gözetiminde yapılmalı.
- UI'da fiziksel hareket uyarısı açık metinle gösterilmeli.
- Marine sistemlerde steering/throttle/shift/trim gibi komutlar manevra riski olan durumda test edilmemeli.

## 25.2 LOTO / Energy Isolation

Aktüatör testlerinde mümkün olduğunda üreticinin Lockout/Tagout veya eşdeğer enerji izolasyon prosedürü uygulanmalıdır.

UI interlock yalnızca kullanıcının aşağıdaki onaylarını kaydetmelidir:

```text
[ ] Equipment is physically secured.
[ ] Personnel are outside the hazard zone.
[ ] Required energy isolation has been applied.
[ ] Manufacturer service procedure is being followed.
```

Bu checkbox'lar gerçek fiziksel izolasyonu doğrulamaz ve LOTO'nun yerine geçmez.

---

# 26. UI Safety Requirements

Renk tek başına safety indicator olmamalıdır.

Açık metinle aşağıdaki durumlar gösterilmelidir:

```text
PASSIVE
TX DISABLED
TX ARMED
LIVE CAN
SIMULATION
REPLAY
BUS OFF
STALE
UNKNOWN
PROPRIETARY
FAULT
DATABASE MISMATCH
```

TX açılmadan önce UI:

```text
Current Bus Load
Target ECU
Protocol
Command Class
Confidence
Database Version
Safety State
```

gösterebilmelidir.

---

# 27. Confidence / Trust / Provenance Modeli

Decoder çıktısı:

```text
HIGH
MEDIUM
LOW
UNKNOWN
```

confidence taşımalıdır.

Ancak:

> **Confidence tek başına TX authorization değildir.**

Önerilen policy:

```text
HIGH
 → TX candidate olabilir
 → additional safety checks REQUIRED

MEDIUM
 → explicit confirmation
 → restricted operation

LOW
 → TX BLOCKED

UNKNOWN
 → TX BLOCKED
```

Ayrıca command risk level confidence'dan bağımsız değerlendirilmelidir.

Örneğin `ECU RESET` için HIGH confidence bile otomatik TX yetkisi sağlamaz.

---

# 28. Decoder Database Güvenliği

Database her tanım için mümkün olduğunca:

```text
Protocol
Standard
Standard Revision
Manufacturer
Model
Firmware Range
PGN / CAN ID
SPN / Signal
Scale
Offset
Unit
Validity
Reserved Values
Source
Confidence
Database Version
```

taşımalıdır.

Database değişiklikleri version-control altında tutulmalıdır.

Her release:

```text
Database Version
Database Hash
Schema Version
Migration Version
```

ile izlenebilir olmalıdır.

---

# 29. Forensic Logging ve Audit Trail

## 29.1 Raw capture

Mümkün olduğunca:

```text
Host Timestamp
Hardware Timestamp
CAN Channel
Interface
Bitrate
CAN Mode
Direction
CAN ID
ID Type
DLC
Payload
Error State
Protocol
Decoder
Decoder Version
Confidence
```

kaydedilmelidir.

## 29.2 Diagnostic / TX audit

```text
User
User Action
Command
Target
Timestamp
Reason
Protocol State
Database Version
Result
Error
```

kaydedilmelidir.

## 29.3 Tamper evidence

Safety-critical session loglarında hash-chain veya signed manifest gibi mekanizmalar ileride değerlendirilebilir.

---

# 30. UNKNOWN / PROPRIETARY State

Bilinmeyen mesaj zorla anlamlandırılmamalıdır.

Doğru:

```text
UNKNOWN
CAN ID: 0x...
DLC: 8
RAW: FF 12 A4 ...
Confidence: UNKNOWN
```

Raw hex kullanıcıya gösterilebilir.

Ancak UNKNOWN veri:

- otomatik telemetry signal olarak üretilmemeli,
- otomatik alarm kaynağı olmamalı,
- otomatik TX decision source olmamalıdır.

Manuel expert analysis ayrı bir işlem olarak yapılabilir.

---

# 31. Simulation Mode

Gerçek ECU yerine simülasyon desteği bulunmalıdır.

```text
CAN Simulator
      ↓
Application
      ↓
Protocol Decoder
      ↓
Telemetry
      ↓
Logging
```

Simülatör aşağıdaki senaryoları üretebilmelidir:

- normal traffic
- burst traffic
- malformed frame
- dropped frame
- stale data
- invalid checksum
- sequence error
- transport timeout
- bus-off simulation
- unknown/proprietary messages
- Address Claim sequence
- diagnostic negative response

---

# 32. Hardware-in-the-Loop

```text
PC
 ↓
CAN Interface
 ↓
STM32 / CAN Simulator
 ↓
Test CAN Network
```

Gerçek ECU ilk test hedefi olmamalıdır.

HIL testleri safety state machine, TX watchdog, queue flush, adapter reconnect ve replay isolation gibi konuları da kapsamalıdır.

---

# 33. Saha Test Kademeleri

```text
LEVEL 0
Unit Tests
   ↓
LEVEL 1
Protocol Simulation
   ↓
LEVEL 2
CAN Simulator
   ↓
LEVEL 3
Hardware-in-the-Loop
   ↓
LEVEL 4
Isolated Lab CAN Network
   ↓
LEVEL 5
Known Safe ECU
   ↓
LEVEL 6
Real Vehicle / Marine Network
```

Her seviyenin exit criteria belgelenmeden bir sonraki seviyeye geçilmemelidir.

---

# 34. Gerçek Tekne İçin Minimum Güvenlik Kuralları

İlk gerçek-tekne bağlantısında:

- TX kapalı.
- Replay kapalı.
- Diagnostic write kapalı.
- ECU reset kapalı.
- DTC clear kapalı.
- Actuator control kapalı.
- Programming kapalı.
- Unknown/proprietary frame'ler zorla decode edilmiyor.
- Bus state izleniyor.
- Dropped frame counter izleniyor.
- Stale telemetry gösteriliyor.
- Adapter/firmware/database bilgisi loglanıyor.
- Connection configuration açıkça gösteriliyor.
- Safety state PASSIVE.
- Kullanıcı emergency isolation prosedürünü biliyor.

---

# 35. Risk Register

Aşağıdaki tablo başlangıç risk register'ıdır. `S/L/D` değerleri saha verisi değil, doğrulama önceliklendirmesi için mühendislik başlangıç tahminidir.

| ID | Risk | Kategori | Seviye | S | L | D | Öncelik | Azaltma |
|---|---|---|---|---:|---:|---:|---:|---|
| R-01 | İstenmeyen TX | TX / Safety | L4 | 4 | 2 | 4 | 32 | TX default off, Safety Gate, watchdog |
| R-02 | Yanlış bitrate | Physical | L2 | 2 | 3 | 2 | 12 | Explicit config, sanity check |
| R-03 | Yanlış CAN channel | Configuration | L2 | 2 | 3 | 3 | 18 | Channel identity, confirmation |
| R-04 | CAN/CAN-FD karışıklığı | Physical/Protocol | L2 | 2 | 2 | 3 | 12 | Mode validation |
| R-05 | 11/29-bit ID hatası | Protocol | L2 | 2 | 2 | 3 | 12 | Explicit ID type |
| R-06 | Yanlış PGN/SPN decode | Decode | L3 | 3 | 3 | 4 | 36 | Database validation, confidence |
| R-07 | Proprietary decode hatası | Decode | L4 | 4 | 2 | 4 | 32 | UNKNOWN by default |
| R-08 | Not Available'ı gerçek veri sanma | Decode | L2 | 2 | 3 | 3 | 18 | Validity rules |
| R-09 | Stale telemetry | Telemetry | L2 | 2 | 3 | 3 | 18 | Age/status |
| R-10 | Frame loss / buffer overflow | Performance | L2 | 2 | 3 | 3 | 18 | Counters, queue policy |
| R-11 | Bus-Off | CAN | L3 | 3 | 2 | 3 | 18 | Error monitor, TX revoke |
| R-12 | ISO-TP state machine hatası | Transport | L3 | 3 | 2 | 4 | 24 | HIL, timeout, sequence validation |
| R-13 | Address/context mismatch | Transport | L3 | 3 | 2 | 4 | 24 | N_AI/session binding |
| R-14 | UDS command hatası | Diagnostic | L3 | 3 | 2 | 4 | 24 | State machine, whitelist |
| R-15 | ECU Reset | Diagnostic | L4 | 4 | 1 | 4 | 16 | Explicit command gate |
| R-16 | Actuator control | Physical | L4 | 4 | 1 | 4 | 16 | LOTO/interlock |
| R-17 | Replay on live bus | TX/Replay | L4 | 4 | 1 | 4 | 16 | Replay disabled + filter |
| R-18 | Database/firmware skew | Configuration | L4 | 4 | 2 | 4 | 32 | Version/hash/compatibility |
| R-19 | Confidence ile yanlış TX | Safety | L4 | 4 | 2 | 4 | 32 | Confidence policy + command risk |
| R-20 | TX flooding | TX | L3 | 3 | 2 | 3 | 18 | Per-ID + global rate limit |
| R-21 | TX watchdog failure | Safety | L4 | 4 | 1 | 4 | 16 | Independent safety supervisor |
| R-22 | UI freeze sırasında TX | Safety | L4 | 4 | 1 | 4 | 16 | Watchdog lease |
| R-23 | Global exception sonrası TX | Software | L4 | 4 | 1 | 4 | 16 | Panic handler, queue flush |
| R-24 | Adapter reconnect sonrası TX | USB/Firmware | L4 | 4 | 1 | 4 | 16 | TX remains revoked |
| R-25 | Gateway loop | Network | L4 | 4 | 1 | 4 | 16 | Bridge disabled / lab-only |
| R-26 | Wrong physical bus | Topology | L4 | 4 | 2 | 3 | 24 | Bus identity / operator check |
| R-27 | NMEA transport confusion | Marine | L3 | 3 | 2 | 4 | 24 | ISO TP/Fast Packet split |
| R-28 | Ground/transient damage | Hardware | L4 | 4 | 1 | 3 | 12 | Isolation/protection validation |
| R-29 | Log corruption | Forensic | L2 | 2 | 2 | 3 | 12 | Buffered writer + integrity |
| R-30 | False VERIFIED state | UX/Trust | L3 | 3 | 3 | 4 | 36 | Provenance model |

> Yüksek Severity + düşük Likelihood kombinasyonları “önemsiz” değildir. L4 riskleri rare olsa bile güvenlik gate'lerinde korunmalıdır.

---

# 36. Quantifiable Safety Metrics

Bu bölüm, “rate limiter var”, “watchdog var” gibi belirsiz gereksinimleri ölçülebilir hale getirir.

## 36.1 Capture Metrics

Her session için:

```text
RX_FRAMES_RECEIVED
RX_FRAMES_PROCESSED
RX_FRAMES_DROPPED
RX_FRAMES_REJECTED
MAX_QUEUE_DEPTH
AVG_QUEUE_DEPTH
PROCESSING_LATENCY_P50
PROCESSING_LATENCY_P95
PROCESSING_LATENCY_P99
```

## 36.2 TX Metrics

```text
TX_FRAMES_REQUESTED
TX_FRAMES_ALLOWED
TX_FRAMES_BLOCKED
TX_FRAMES_SENT
TX_FRAMES_REJECTED
TX_RATE
TX_BURST_COUNT
TX_QUEUE_DEPTH
TX_SAFETY_REVOKE_COUNT
```

## 36.3 Bus Load

Mümkünse:

```text
RX Bus Utilization %
TX Bus Utilization %
Total Bus Utilization %
```

ayrı izlenmelidir.

## 36.4 Rate Policy

Global tek bir `TX_MIN_INTERVAL_MS` bütün protocol/message sınıfları için kullanılmamalıdır.

Policy:

```text
Global Max Bus Utilization
Per-ID Min Interval
Per-command Burst Limit
Protocol-specific Timing
Replay Timing Limit
Diagnostic Timeout
```

şeklinde modellenmelidir.

## 36.5 Watchdog

`TX_WATCHDOG_TIMEOUT_MS` bir proje parametresidir; başlangıç HIL test değeri örneğin 500 ms olabilir. Final değer gerçek adapter/driver/hardware behavior ile doğrulanmalıdır.

## 36.6 Queue Overflow Policy

Her queue için:

```text
Policy
Capacity
Dropped Count
High-water Mark
Recovery Behavior
```

loglanmalıdır.

---

# 37. Safe-by-Default Requirements

Başlangıç durumunda:

```text
TX:                DISABLED
REPLAY:            DISABLED
ECU WRITE:         DISABLED
ECU RESET:         DISABLED
DTC CLEAR:         DISABLED
ACTUATOR CONTROL:  DISABLED
PROGRAMMING:       DISABLED
BRIDGE:            DISABLED
```

kullanıcı açıkça etkinleştirmeden bunlar çalışmamalıdır.

---

# 38. Fail-Safe / Fail-Silent Requirements

Aşağıdaki durumlardan herhangi birinde TX authorization revoke edilmelidir:

```text
USB Disconnect
CAN Controller Error
Bus-Off
Configuration Change
Adapter Reconnect
Protocol Uncertainty
Decoder Fatal Exception
TX Validation Failure
Unexpected Firmware Response
Safety Watchdog Timeout
Application Panic
Database Compatibility Failure
Target Identity Loss
```

Safety transition:

```text
FAULT EVENT
 ↓
TX AUTHORIZATION REVOKE
 ↓
TX QUEUE FLUSH
 ↓
ADAPTER SAFE STATE
 ↓
PASSIVE / FAULT
 ↓
AUDIT LOG
```

Otomatik recovery sonrası kullanıcı yeniden explicit TX arm etmeden TX başlamamalıdır.

---

# 39. Decoder Safety Rule

Decoder'ın temel görevi:

```text
RAW
 ↓
INTERPRET
 ↓
VALIDATE
 ↓
DISPLAY
```

olmalıdır.

Decoder:

```text
RAW
 ↓
INTERPRET
 ↓
AUTOMATIC TX
```

yapmamalıdır.

---

# 40. Diagnostic Safety Rule

Diagnostic işlemleri:

```text
READ
```

ve:

```text
WRITE / CONTROL
```

olarak ayrılmalıdır.

HIGH-RISK operations:

```text
ECU Reset
DTC Clear
WriteData
RoutineControl
Actuator Test
SecurityAccess
Programming
```

explicit authorization gerektirir.

---

# 41. Replay Safety Rule

Replay:

- default OFF,
- live bus'tan açıkça ayrılmış,
- TX Safety Supervisor üzerinden çalışan,
- rate/bus-load policy'ye tabi,
- safety-filtered,
- audit logged

olmalıdır.

---

# 42. Field Readiness Checklist

## Architecture

- [ ] PASSIVE mode default
- [ ] RX/TX isolation doğrulandı
- [ ] Safety State Machine implement edildi
- [ ] TX Safety Supervisor mevcut
- [ ] TX Watchdog mevcut ve test edildi
- [ ] Fatal exception TX revoke mekanizması test edildi

## TX

- [ ] TX default disabled
- [ ] TX whitelist mevcut
- [ ] Target validation mevcut
- [ ] Payload validation mevcut
- [ ] Per-ID rate limit mevcut
- [ ] Global bus-load limit mevcut
- [ ] Burst limit mevcut
- [ ] TX queue flush mevcut
- [ ] Reconnect sonrası TX disabled

## Decoder

- [ ] Decoder confidence mevcut
- [ ] UNKNOWN state mevcut
- [ ] Proprietary detection mevcut
- [ ] Not Available handling mevcut
- [ ] Reserved handling mevcut
- [ ] Database version logged
- [ ] Database hash logged
- [ ] Firmware compatibility state mevcut

## Protocols

- [ ] J1939 PGN/SPN mapping test edildi
- [ ] J1939 Address Claim test edildi
- [ ] ISO-TP SF/FF/CF/FC test edildi
- [ ] ISO-TP sequence validation test edildi
- [ ] ISO-TP timeout test edildi
- [ ] Address/context validation test edildi
- [ ] UDS read-only test edildi
- [ ] UDS write/reset blocked by default
- [ ] NMEA 2000 ISO TP/Fast Packet ayrımı test edildi

## Telemetry

- [ ] Signal age mevcut
- [ ] STALE state mevcut
- [ ] VALID/INVALID distinction mevcut
- [ ] Received/Processed/Dropped counters mevcut
- [ ] Queue depth telemetry mevcut
- [ ] Processing latency metrics mevcut
- [ ] Bus utilization mevcut

## Hardware

- [ ] CANH/CANL doğrulandı
- [ ] Termination doğrulandı
- [ ] Galvanic isolation specification doğrulandı
- [ ] Operating voltage specification doğrulandı
- [ ] Transient/ESD protection specification doğrulandı
- [ ] Adapter firmware version logged
- [ ] Physical disconnect procedure doğrulandı

## Physical Safety

- [ ] Aktüatör testlerinde fiziksel güvenlik prosedürü mevcut
- [ ] LOTO/equivalent procedure üretici prosedürüyle hizalı
- [ ] Hazard-zone check mevcut
- [ ] İkinci kişi/supervisor requirement belirlenmiş
- [ ] Marine propulsion/steering/shift riskleri açıkça ele alınmış

## Testing

- [ ] Unit tests
- [ ] Protocol simulation
- [ ] CAN simulator
- [ ] HIL
- [ ] Isolated lab network
- [ ] Known safe ECU
- [ ] Controlled field test

---

# 43. Saha Acil Durum Prosedürü

Beklenmeyen davranış fark edildiğinde:

- beklenmeyen aktüatör hareketi,
- beklenmeyen motor davranış değişikliği,
- anormal ses/titreşim,
- beklenmeyen warning/diagnostic state,
- açıklanamayan CAN traffic surge

gibi durumlar emergency event kabul edilir.

## 43.1 Öncelikli operator response

1. Varsa software `ABORT / TX STOP` komutunu uygulayın.
2. Yazılım stopu etkili olmuyorsa diagnostic interface'i **CAN network'ten fiziksel olarak izole edin**.
3. Motor/sistem üzerinde ayrıca güvenli shutdown gerekiyorsa üreticinin prosedürünü izleyin.
4. Sistemi "düzeltmek" için rastgele reset/power-cycle yapmayın.
5. Audit log'dan timestamp, command, target ve safety state bilgilerini koruyun.
6. Kök neden anlaşılmadan gerçek sisteme yeniden TX uygulamayın.
7. Testi daha güvenli bir seviyeye geri taşıyın (ör. real system → lab → HIL).

## 43.2 Önemli not

USB'yi çekmek evrensel olarak "emergency stop" kabul edilmemelidir. Güvenli izolasyon yönteminin adapter/vehicle/marine wiring tasarımına göre ayrıca belirlenmesi gerekir.

Fiziksel emergency isolation, software TX stop'tan bağımsız bir güvenlik katmanı olmalıdır.

---

# 44. Suspicious Activity / Rollback Policy

Beklenmeyen davranış tespit edilirse sistem:

```text
Unexpected Event
      ↓
TX Authorization Revoke
      ↓
Freeze Diagnostic State
      ↓
Capture Pre-trigger Buffer
      ↓
Capture Post-trigger Window
      ↓
SUSPICIOUS_ACTIVITY
      ↓
PASSIVE / FAULT
```

olmalıdır.

## 44.1 Tetikleyiciler

- beklenmeyen DTC oluşumu,
- beklenmeyen CAN traffic spike,
- beklenmeyen diagnostic response,
- target identity değişikliği,
- watchdog timeout,
- unexpected ECU state transition,
- bus state değişimi,
- validation failure

## 44.2 Capture

Sadece son birkaç saniyeyi saklamak yerine mümkünse:

```text
PRE_TRIGGER_CAPTURE
+
EVENT_TIMESTAMP
+
POST_TRIGGER_CAPTURE
```

kullanılmalıdır.

Başlangıç test profili örneğin:

```text
Pre-trigger: 30 s
Post-trigger: 10 s
```

olabilir. Bu bir proje default'udur; depolama ve trafik profiline göre doğrulanmalıdır.

## 44.3 Operator message

```text
UNSAFE / UNEXPECTED CONDITION DETECTED
TX HAS BEEN DISABLED
DO NOT CONTINUE THE TEST
CHECK THE CONNECTION AND SERVICE PROCEDURE
```

---

# 45. Validation Evidence ve Release Gate

Her safety-critical requirement için test evidence tutulmalıdır.

Önerilen kayıt:

```text
Requirement ID
Test ID
Software Version
Firmware Version
Database Version
Database Hash
Hardware
Test Configuration
Expected Result
Actual Result
Pass/Fail
Tester
Timestamp
Log Artifact
```

## Release gate

Gerçek saha kullanımına geçiş için en az:

```text
NO OPEN CRITICAL SAFETY DEFECTS
NO UNRESOLVED TX SAFETY FAILURE
NO UNRESOLVED BUS-OFF RECOVERY ISSUE
NO UNRESOLVED DECODER DATA-INTEGRITY ISSUE
NO UNRESOLVED DATABASE COMPATIBILITY ISSUE
FIELD PROCEDURE APPROVED
```

şartları aranmalıdır.

---

# 46. Final Safety Statement

> **Bu yazılımın gerçek bir araç veya tekne network'ünde kullanılması, yalnızca decoder'ların çalışıyor olmasıyla güvenli kabul edilmemelidir.**

Saha kullanımından önce aşağıdaki alanlar ayrı ayrı doğrulanmalıdır:

- CAN physical layer
- protocol correctness
- decoder correctness
- data validity
- error handling
- TX isolation
- safety state management
- diagnostic state management
- watchdog behavior
- database compatibility
- fail-safe / fail-silent behavior
- human factors
- physical safety
- hardware isolation
- logging / forensic traceability
- simulation
- HIL
- controlled field testing

Özellikle gerçek marine/vehicle ECU'larında ilk testler READ-ONLY / LISTEN-ONLY modunda gerçekleştirilmelidir.

Bu doküman bir safety engineering başlangıç noktasıdır. Gerçek saha kullanımı öncesinde hedef sistemin üretici servis prosedürleri, network dokümantasyonu ve uygulanabilir standartları ayrıca doğrulanmalıdır.

---

# 47. Kaynaklar / Referanslar

## 47.1 Proje içi temel kaynak

Bu v1.2 dokümanı, proje içindeki **Saha_Risk_Kataloğu__Güvenlik_Gereksinimleri_ve_Risk_Azaltma_Planı_v1.1.md** dokümanının yapısı ve terminolojisi temel alınarak genişletilmiştir.

## 47.2 NMEA 2000 transport doğrulaması

Vendor dokümantasyonunda NMEA 2000 için ISO acknowledgment, ISO Address Claim, ISO Transport Protocol (PGN 060160 / 060416) ve Fast-packet proprietary (PGN 126720) örnekleri birlikte yer almaktadır:

- Garmin NMEA 2000 PGN Information: https://www8.garmin.com/manuals/webhelp/GUID-4E35EBDF-6BB0-4B04-89C5-4642E8D77431/EN-US/GUID-8E7A6446-ACB3-477F-9216-5B15325BB783.html
- Garmin NMEA 2000 PGN Information (2024 manual): https://www8.garmin.com/manuals/webhelp/GUID-E5A56C73-E63C-479F-BDB2-198E7FB08115/EN-US/GUID-8E7A6446-ACB3-477F-9216-5B15325BB783.html
- Garmin NMEA 2000 PGN Information (2026 documentation): https://www8.garmin.com/manuals/webhelp/GUID-9A17B80C-F7A5-453E-8E7D-E8F0ECD1DCD4/en-US/GUID-47EAC1F6-4933-4C1B-B62B-61D0C63F3E99.html

> Not: NMEA 2000 proprietary/transport davranışı için hedef cihazın üretici dokümantasyonu ayrıca doğrulanmalıdır. Vendor dokümanı standardın tamamını temsil etmez.

---

# Appendix A — Örnek Safety Configuration

Aşağıdaki değerler **proje başlangıç parametreleri**dir; evrensel CAN/UDS/NMEA 2000 standardı olarak yorumlanmamalıdır.

```yaml
safety:
  default_mode: PASSIVE
  tx_enabled: false
  replay_enabled: false
  ecu_write_enabled: false
  ecu_reset_enabled: false
  dtc_clear_enabled: false
  actuator_control_enabled: false
  programming_enabled: false
  bridge_enabled: false

watchdog:
  enabled: true
  tx_watchdog_timeout_ms: 500   # başlangıç HIL değeri; doğrulanmalı

logging:
  forensic_logging: true
  audit_logging: true
  database_hash: true
  firmware_version: true

replay:
  enabled: false
  filter_address_claim: true
  filter_diagnostic_write: true
  filter_actuator_control: true
  filter_programming: true
  filter_unknown_proprietary_tx: true

telemetry:
  stale_threshold_ms: configurable
  queue_policy: DROP_OLDEST

forensic_capture:
  pre_trigger_seconds: 30
  post_trigger_seconds: 10
```

---

# Appendix B — Örnek TX Authorization Decision

```text
TX Request
   │
   ▼
Safety State == ARMED ?
   │ no → BLOCK
   ▼
Target Known ?
   │ no → BLOCK
   ▼
Protocol State Valid ?
   │ no → BLOCK
   ▼
Confidence >= Policy ?
   │ no → BLOCK
   ▼
Command Risk Allowed ?
   │ no → BLOCK
   ▼
ID Whitelisted ?
   │ no → BLOCK
   ▼
Payload Valid ?
   │ no → BLOCK
   ▼
Timing Valid ?
   │ no → BLOCK
   ▼
Bus Load Safe ?
   │ no → BLOCK
   ▼
Watchdog Lease Valid ?
   │ no → BLOCK
   ▼
USER AUTHORIZATION OK ?
   │ no → BLOCK
   ▼
TRANSMIT
```

Bu modelin temel hedefi:

> **Bir tek kontrolün güvenliği belirlememesi; TX'in ancak tüm bağımsız safety gate'lerinden geçtikten sonra mümkün olmasıdır.**

---

# Appendix C — Saha Kullanımına Geçmeden Önce Son Soru

Sistem gerçek bir tekneye bağlanmadan önce ekip şu soruya cevap verebilmelidir:

> **"Yazılımın yanlış decode etmesi halinde ne olur; yanlış TX yapması halinde ne olur; yazılım donarsa ne olur; adapter reconnect olursa ne olur; bus-off olursa ne olur; kullanıcı yanlış profile bağlanırsa ne olur; database eskiyse ne olur; ve bu olayların her birinde TX'in gerçekten durduğunu nasıl kanıtladık?"**

Bu sorulardan herhangi birinin cevabı yalnızca "kullanıcı dikkat eder" ise requirement tamamlanmış sayılmamalıdır.
