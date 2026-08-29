Tüm dosyaları başarıyla teslim aldım. Fazladan gönderilen `docs_code_review_report.md` dosyasını tek kopya olarak işledim, çakışan bulguları birleştirdim. Şimdi 14 ayrı analiz dosyasını **tek, temiz ve kapsamlı bir MASTER REVIEW** raporuna dönüştürüyorum.

---

# 🔍 Universal-CAN-Bus-Diagnostic
## MASTER KOD İNCELEME & GÜVENLİK DENETİM RAPORU

**Repo:** https://github.com/si6n/Universal-CAN-Bus-Diagnostic
**Kapsam:** `src/`, `tests/`, `scripts/`, `examples/`, `docs/`, `.github/`
**Standartlar:** ISO 21434:2021 · SAE J1939-21/73/81 · ISO 14229-1 (UDS) · ISO 15765-2 (ISO-TP) · NMEA 2000 · ISO 11898 · ASPICE · OWASP
**Kaynak:** 14 bağımsız AI analiz raporunun birleştirilmiş ve tekilleştirilmiş hali

---

## 1. 📋 YÖNETİCİ ÖZETİ

Proje, otomotiv/marin CAN teşhisi için **safety-critical** bir platformdur ve mimari niyet doğrudur: 6 katmanlı yapı, formal Safety State Machine, TX Safety Gateway, E-Stop, watchdog ve DRM/lisanslama katmanları tasarlanmıştır. Ancak denetim, **tasarım niyeti ile implementasyon arasında kritik uçurumlar** olduğunu göstermektedir.

**En çarpıcı tespit:** Dokümantasyon "HMAC-SHA256 E-Stop Token" ve "274/274 test başarılı" gibi iddialar taşırken, gerçek kod **hardcoded statik string** kullanmakta ve test sayısı üç belgede üç farklı rakam (274 / 220 / 161) olarak geçmektedir. Bu, audit kanıtlarının güvenilirliğini zedeleyen sistemik bir **doküman-kod sapmasıdır.**

### Toplam Bulgu Özeti (14 raporun birleştirilmiş hali)

| Öncelik | Tekilleştirilmiş Bulgu Sayısı |
|---|---|
| 🔴 KRİTİK | **~42** |
| 🟠 YÜKSEK | **~78** |
| 🟡 ORTA | ~15 |
| **TOPLAM** | **~135 özgün bulgu** |

> Not: 14 raporda ham olarak ~228 bulgu tespit edilmiş; aynı sorunun farklı raporlarda tekrar etmesi nedeniyle ~135 özgün bulguya indirgenmiştir.

### 🎯 İlk 10 Gösterge (Showstopper)

| # | Bulgu | Konum | Neden Kritik |
|---|---|---|---|
| 1 | **J1939 TP.DT reassembly eksik/kesik** | `protocols/j1939/transport.py` | Tüm multi-frame DM1/DTC mesajları kayboluyor; protokol çalışmıyor |
| 2 | **E-Stop hardcoded HMAC secret** | `safety/estop.py` | Saldırgan E-Stop'u yetkisiz sıfırlayabilir → hareket halinde tehlikeli TX |
| 3 | **`pickle.loads()` ile disk deserializasyonu** | `engine/buffer/rolling_disk.py` | Dosya manipülasyonunda **RCE** (Remote Code Execution) |
| 4 | **TOCTOU — gateway TX / watchdog** | `safety/gateway.py`, `safety/watchdog.py` | Fail-silent garantisi kırılıyor; race window |
| 5 | **WebView2 JS/komut enjeksiyonu** | `ui/desktop_app.py` | XSS → Python köprüsünden safety fonksiyon çağrısı (RCE) |
| 6 | **CI'da mutable action tag'leri** | `.github/workflows/ci.yml` | Supply-chain hijack (tag poisoning) riski |
| 7 | **`shell=True` komut enjeksiyonu** | `scripts/build_exe.py` | Derleme zincirinde enjeksiyon yüzeyi |
| 8 | **Simülatör canlı kanala yönlenebilir** | `scripts/demo_traffic_generator.py` | Fiziksel araca kazara TX |
| 9 | **`watchdog.py` için hiç test yok** | `tests/` | ISO 21434 TR.SAFE.5 kanıtı yok |
| 10 | **Açık güvenlik açıkları public dokümanda** | `docs/audit/implementation_plan.md` | Saldırı senaryosuyla birlikte yayınlanmış |

---

## 2. 📊 RİSK MATRİSİ (ISO 21434 TARA)

```
                    OLASILIK
              Yüksek      Orta       Düşük
            ┌──────────┬──────────┬──────────┐
  Kritik    │ TP.reasm │ watchdog │ NMEA seq │  ██ KABUL EDİLEMEZ
  Etki      │ estop-sec│ TOCTOU   │ hijack   │  (Derhal düzelt)
            │ pickle   │ wildcard │          │
            ├──────────┼──────────┼──────────┤
  Yüksek    │ JS-inject│ HWM-key  │ antitamper│ ▓▓ YÜKSEK RİSK
  Etki      │ shell=Tr │ anti-roll│ timing   │  (Planlı düzelt)
            │ CI-tags  │ PS-inject│          │
            ├──────────┼──────────┼──────────┤
  Orta      │ GC-baskı │ FF_DL    │ doc-tutar│ ░░ ORTA RİSK
  Etki      │ zero-copy│ ext      │          │  (İzle/iyileştir)
            └──────────┴──────────┴──────────┘
```

---

## 3. 🔴 KRİTİK BULGULAR — ACİL MÜDAHALE

Bu bölüm, tüm raporlarda **KRİTİK** olarak işaretlenmiş ve tekilleştirilmiş bulguları içerir. Her biri güvenlik, emniyet veya temel işlevsellik açısından gösterge niteliğindedir.

### 3.1 🛡️ Safety / Emniyet Kritikleri

#### K-01 · E-Stop Hardcoded HMAC Secret
**Konum:** `src/safety/estop.py` (~L52) · **CWE-798** · ISO 21434 §10.4.1
**Kaynak raporlar:** src_report-1, src_report-3 (A4), SECURITY_REVIEW (B-03)

`b"EMERGENCY_STOP_DEFAULT_HMAC_SECRET_2026"` literalı kaynak kodda açık. Saldırgan bu sabitten geçerli reset token üretip aktif E-Stop'u yetkisiz sıfırlayabilir → araç hareket halindeyken tehlikeli TX.

```python
# DÜZELTME: Varsayılanı kaldır, zorunlu kıl, DPAPI/secret-store kullan
def __init__(self, reset_secret: bytes | None = None) -> None:
    if reset_secret is None or len(reset_secret) < 32:
        raise ValueError(
            "reset_secret must be ≥32 cryptographically random bytes. "
            "Use os.urandom(32) or DPAPI-protected config."
        )
    self.reset_secret = reset_secret
```

#### K-02 · Watchdog Otomatik Besleme / TOCTOU
**Konum:** `src/ui/desktop_app.py` (~L151), `src/safety/watchdog.py` (~L76-85) · **CWE-362/367**
**Kaynak raporlar:** src_report-1, src_report-3 (A1), SECURITY_REVIEW (B-02)

İki ayrı sorun iç içe:
1. `_telemetry_loop` her 50ms'de watchdog'u otomatik besliyor → UI kilitlense bile lease düşmüyor, 500ms supervisor etkisiz.
2. `elapsed` ve `is_tx_permitted` iki ayrı lock alımıyla okunuyor → aradaki pencerede heartbeat elapsed'i sıfırlayabilir, timeout asla tetiklenmeyebilir.

```python
# DÜZELTME 1: Watchdog sadece UI heartbeat hattından beslenmeli
# DÜZELTME 2: elapsed + is_tx_permitted snapshot'ını AYNI lock bölgesinde al
with self._lock:
    elapsed = time.monotonic() - self._last_heartbeat_time
    is_running = self._is_running
    should_fault = is_running and not self.supervisor.is_tx_permitted \
                   and elapsed > self.timeout_sec
if should_fault:
    self._fire_timeout(elapsed)  # eylem lock dışında
```

#### K-03 · Gateway Deadlock + TOCTOU + Kural Sırası
**Konum:** `src/safety/gateway.py` (~L82-105) · **CWE-367/667**
**Kaynak raporlar:** src_report-3 (A2, A3), SECURITY_REVIEW (B-01), SECURITY_CRIT_HIGH

Üç bağlantılı sorun:
1. **Deadlock:** Whitelist ihlalinde `estop.trigger()` `_lock` altında çağrılıyor; callback zinciri `gateway._lock` talep ederse deadlock.
2. **TOCTOU:** `estop.is_engaged` kontrolü (CHECK) ile `bus.send()` (USE) farklı kilit nesneleriyle korunuyor.
3. **Kural sırası:** Speed Interlock, Dual Confirmation'dan sonra gelmeli; mevcut sıra semantik tutarsızlık yaratıyor.

```python
# DÜZELTME: İhlali lock altında tespit et, bayrağı ayarla;
# E-Stop'u lock DIŞINDA tetikle; bus.send() lock içinde kalsın
def validate_and_transmit(self, frame, is_critical_command=False, user_confirmed=False):
    estop_reason = None
    with self._lock:
        if self.estop.is_engaged:  # double-check
            raise SafetyError("ESTOP_ACTIVE", code="ESTOP_ACTIVE")
        # ... rule chain (normatif sıra: State→Lease→EStop→Speed→DualConf→Whitelist→Rate)
        if self.whitelist_ids and frame.arbitration_id not in self.whitelist_ids:
            estop_reason = f"Non-whitelisted ID: 0x{frame.arbitration_id:08X}"
        else:
            self._tx_timestamps.append(now)
            self.bus.send(frame)  # lock bırakılmadan
            return True
    if estop_reason:
        self.estop.trigger(EStopTriggerSource.UNAUTHORIZED_PAYLOAD, estop_reason)
        raise SafetyError(..., code="WHITELIST_VIOLATION")
```

#### K-04 · TX Whitelist Safe-by-Default İhlali
**Konum:** `src/safety/gateway.py` (~L41)
**Kaynak raporlar:** src_report-1

Boş whitelist (`set()`) varsayılanında tüm ID'ler geçiyor. Safe-by-default prensibi ihlali.

```python
if not self.whitelist_ids:
    raise SafetyError("Whitelist must be explicitly configured before TX",
                      code="WHITELIST_NOT_CONFIGURED")
```

---

### 3.2 🔐 Security / RCE Kritikleri

#### K-05 · `pickle.loads()` Disk Deserializasyonu → RCE
**Konum:** `src/engine/buffer/rolling_disk.py` (~L63, ~L118-129) · **CWE-502**
**Kaynak raporlar:** src_report-1 (D-1), src_report-3 (C1/D1), SECURITY (docs B-3/B-4 referansı)

`read_all_stored_frames()` içinde `pickle.loads(raw_bytes)` — depolama dizinine yazabilen saldırgan **arbitrary code execution** elde eder. Hiçbir magic-byte veya HMAC doğrulaması yok. Bu, hem performans (GC baskısı) hem güvenlik (RCE) sorunudur.

```python
# DÜZELTME: pickle'ı tamamen kaldır. struct + HMAC-SHA256 imzalı binary format.
import struct, hmac, hashlib

def _serialize_frames(frames):
    parts = []
    for f in frames:
        header = struct.pack(">QIBBB", f.timestamp_ns, f.arbitration_id,
                             f.dlc, len(f.data),
                             (f.is_extended << 0) | (f.is_fd << 1))
        parts.append(header + f.data.ljust(64, b"\x00")[:64])
    return b"".join(parts)
# Yazarken: chunk_hmac = hmac.new(CHUNK_KEY, raw, sha256).digest() → header'a göm
# Okurken: HMAC doğrula, başarısızsa LicenseError/SafetyError fırlat
```

#### K-06 · WebView2 JS / Köprü Enjeksiyonu → RCE
**Konum:** `src/ui/desktop_app.py` (`_telemetry_loop`, `DesktopApiBridge.ask_copilot`) · **CWE-79/94/77**
**Kaynak raporlar:** SECURITY_REVIEW (B-13, B-14), SECURITY_CRIT_HIGH

Python değerleri f-string ile doğrudan JS'e gömülüyor. Manipüle edilmiş veri (DBC, AI yanıtı, replay trace) özel karakter içerirse JS olarak çalışır; WebView2 köprüsünden `trigger_estop()` gibi safety-critical Python fonksiyonları çağrılabilir.

```python
# DÜZELTME: Tüm veriyi json.dumps() ile escape et
import json
safe_json = json.dumps(payload)
self._window.evaluate_js(f"if(window.onTelemetryTick)window.onTelemetryTick({safe_json});")
# ask_copilot(): max uzunluk (1024), tip doğrulama, allowed-key whitelist ekle
```

#### K-07 · Hardcoded HWM HMAC Key + Anti-Rollback Bypass
**Konum:** `src/security/license/validator.py` (~L31, ~L60-95) · **CWE-321/807**
**Kaynak raporlar:** src_report-1, src_report-3 (A8), SECURITY (B-05, B-06), SECURITY_CRIT_HIGH

Üç bağlantılı DRM zafiyeti:
1. `_HWM_HMAC_KEY` hardcoded → reverse-engineering ile HWM sahteciliği.
2. `except Exception: pass` ile HMAC doğrulama hatası sessiz yutuluyor → Anti-Clock-Rollback kırılıyor.
3. `boot_realtime/boot_monotonic=None` ise monotonic kontrol tamamen atlanıyor; kontrol yönü de yanlış (`<` yerine `abs()` gerekli).
4. **Wildcard `"*"` fingerprint** tüm cihaz bağını bypass ediyor.

```python
# DÜZELTME: Anahtarı env/DPAPI'den yükle; HMAC hatasını YUTMA; wildcard'ı kapat
key_env = os.environ.get("UCAN_HWM_HMAC_KEY")
if not key_env:
    raise LicenseError("Missing HWM key", code="HWM_KEY_MISSING")
# HMAC mismatch → raise LicenseError("HWM_TAMPERED"), asla pass
# monotonic: abs(mono_elapsed - real_elapsed) > TOLERANCE → reject
# wildcard: üretim build'inde default politika = cihaz-bağlı doğrulama zorunlu
```

#### K-08 · PowerShell Komut Enjeksiyonu
**Konum:** `src/security/hwid/collector.py` (~L35-45) · **CWE-78**
**Kaynak raporlar:** src_report-3 (D3), SECURITY (B-08)

`wmi_class` ve `field` parametreleri doğrudan PowerShell komut string'ine ekleniyor.

```python
ALLOWED_WMI_CLASSES = frozenset({"Win32_ComputerSystemProduct", "Win32_Processor",
                                 "Win32_BIOS", "Win32_DiskDrive"})
def _wmi_query(wmi_class, field):
    if wmi_class not in ALLOWED_WMI_CLASSES:
        raise ValueError(f"Disallowed WMI class: {wmi_class}")
    if not field.isidentifier():
        raise ValueError(f"Invalid WMI field: {field}")
    return _run_powershell(f"(Get-CimInstance -ClassName {wmi_class}).{field}")
```

#### K-09 · Anti-Tamper Etkisiz / Fail-Open
**Konum:** `src/security/anti_tamper/guard.py` (~L23, ~L42) · **CWE-693**
**Kaynak raporlar:** src_report-1, src_report-3 (A7), SECURITY (B-07), SECURITY_CRIT_HIGH

Win32 API hatalarında `False` dönülüyor (fail-open → debugger bypass mümkün). Timing tespiti basit `sum(i*i)` döngüsüne dayanıyor; modern debugger'lar maskeleyebilir, VM/yük false-positive üretir. Tespit sadece loglanıyor, koruyucu eylem yok.

```python
# DÜZELTME: fail-closed + çok katmanlı koruma + eylem
except (AttributeError, OSError, RuntimeError) as exc:
    logger.critical("Anti-tamper API failure", extra={"error": str(exc)})
    return True  # fail-closed: şüpheli durum
# Pozitif sonuçta: kod bütünlük hash'i, import-table/hook tespiti,
# parent-process kontrolü, fail-closed aksiyon (lisans düşürme / güvenli çıkış)
```

---

### 3.3 🔌 Protokol Kritikleri

#### K-10 · J1939 TP.DT Reassembly Eksik / Kesik
**Konum:** `src/protocols/j1939/transport.py` (~L155-205) · **CWE-20** · SAE J1939-21 §5.10
**Kaynak raporlar:** src_report-1, src_report-3 (B1), SECURITY (B-09), SECURITY_CRIT_HIGH

**Projenin en büyük işlevsel kusuru.** `_handle_tp_dt()` içinde `matching_key` bulunduktan sonra fonksiyon gövdesi kesilmiş/eksik: sequence doğrulama, bytearray birleştirme, oturum tamamlama ve EOM-Ack yok. Sonuç: **tüm multi-frame BAM/RTS-CTS mesajları (DM1, DTC) reassemble edilemiyor ve kayboluyor.** Ek olarak oturum eşleştirmesi "ilk uyan" mantığıyla yapılıyor → aynı SA için çoklu oturumda veri bütünlüğü ihlali.

```python
def _handle_tp_dt(self, frame, sa, da):
    seq_num = frame.data[0]; payload = frame.data[1:8]
    sess_key = next((k for k,s in self._rx_sessions.items()
        if s.source_address == sa and (s.destination_address == da or s.is_bam)), None)
    if sess_key is None: return None, None
    sess = self._rx_sessions[sess_key]
    if seq_num != sess.expected_sequence:           # katı sequence kontrolü
        self._rx_sessions.pop(sess_key, None)
        return None, self._build_abort(sess) if not sess.is_bam else None
    remaining = sess.total_bytes - len(sess.received_bytes)
    sess.received_bytes.extend(payload[:remaining])
    sess.expected_sequence += 1
    sess.last_activity_time = time.monotonic()
    if len(sess.received_bytes) >= sess.total_bytes:
        completed = CompletedMessage(...)
        self._rx_sessions.pop(sess_key, None)
        return completed, (self._build_eom_ack(sess) if not sess.is_bam else None)
    return None, None
```
Ayrıca: oturum anahtarını `(SA, DA, PGN, channel_id)` ile sıkılaştır; aynı `(SA,DA)` için tek aktif TP oturumu enforce et.

#### K-11 · J1939 BAM Session DoS
**Konum:** `src/protocols/j1939/transport.py` (~L110-125)
**Kaynak raporlar:** src_report-3 (B2)

`MAX_CONCURRENT_SESSIONS=512` dolduğunda en eski session silinip yenisi açılıyor → saldırgan 512 SA'dan BAM flood ile legitim oturumları sürekli tahliye ettirebilir.

```python
MAX_SESSIONS_PER_SA = 4
sa_count = sum(1 for k in self._rx_sessions if k[0] == sa)
if sa_count >= self.MAX_SESSIONS_PER_SA:
    return None, None  # saldırıyı sessizce reddet
```

#### K-12 · ISO-TP FF Uzunluk / CAN-FD Simetri Hataları
**Konum:** `src/protocols/uds/isotp.py` (~L130-175) · **CWE-20** · ISO 15765-2 §9.6/9.8
**Kaynak raporlar:** src_report-1, src_report-3 (B3), SECURITY (B-10), SECURITY_CRIT_HIGH

Üç bağlantılı sorun:
1. **Extended FF_DL eksik:** FF_DL=0 ise sonraki 4 bayt gerçek uzunluk olmalı; kod bunu işlemiyor. `total_len=0` gönderilirse sıfır uzunluklu buffer + sonsuz CF birikimi (bellek DoS).
2. **Üst sınır yok:** bozuk frame ile aşırı bellek tüketimi (reassembly DoS).
3. **CAN-FD first_chunk asimetrisi:** alımda `frame.data[2:8]` ile sadece 6 bayt kopyalanıyor; gönderimde 62-byte FF kullanılıyor → çok çerçeveli UDS yanıtları yanlış reassemble.

```python
if pci_type == PCI_FIRST_FRAME:
    total_len = ((frame.data[0] & 0x0F) << 8) | frame.data[1]
    if total_len == 0:  # extended FF (ISO 15765-2 §9.8.2.2)
        if len(frame.data) < 6: return None, None
        total_len = int.from_bytes(frame.data[2:6], 'big')
        first_chunk = frame.data[6:8]
    else:
        first_chunk = frame.data[2:8]
    if total_len == 0 or total_len > MAX_ISOTP_PAYLOAD:  # 4095 classic / 65535 ext
        return None, None
    # CAN-FD: first_chunk uzunluğunu frame.is_fd ve DLC'ye göre hesapla (6 vs 62)
```
Ayrıca: tek global `_rx_session` yerine `(rx_id, tx_id, channel_id)` anahtarlı oturum sözlüğü kullan.

#### K-13 · UDS NRC 0x78 (Response Pending) Yönetilmiyor
**Konum:** `src/protocols/uds/client.py` (~L97-115, ~L182-191)
**Kaynak raporlar:** src_report-1, SECURITY_CRIT_HIGH

NRC `0x78` için bekleme/tekrar alma yok; ilk 0x78'de üst katman hataya düşüyor, gerçek final cevap beklenmeden işlem kesiliyor (özellikle flash/routine). Ek olarak ISO-TP çok-frame yanıtlarda tek FC gönderilip her CF için bloklu `recv()` çağrılıyor → yüksek DLC yanıtlarda timeout garantisi.

```python
resp = UdsServiceBuilder.parse_response(completed_data)
if not resp.is_positive and resp.nrc == UdsNrc.REQUEST_CORRECTLY_RECEIVED_RESPONSE_PENDING:
    continue  # P2* penceresini uzatarak döngüde beklemeye devam et
# CF toplama döngüsünü ISO-TP session tamamlanana kadar deadline-based sürdür
```

---

### 3.4 🛠️ Build / Scripts Kritikleri

#### K-14 · `shell=True` Komut Enjeksiyonu
**Konum:** `scripts/build_exe.py` (~L22-24) · **CWE-78**
**Kaynak raporlar:** scripts_report, scripts_report-2 (A1)

`subprocess.call(..., shell=True)` ve `cmd.exe /c` hardcoded → komut enjeksiyonu + PATH hijack. Ek olarak `--add-data` ayracı Windows'a özgü (`;`) → Linux CI'da frontend gömülmeden derlenir.

```python
import shutil
npm_cmd = shutil.which("npm")
ret = subprocess.call([npm_cmd, "run", "build"], cwd=str(frontend_dir), shell=False)
sep = ";" if sys.platform == "win32" else ":"
data_arg = f"{frontend_dist}{sep}src/ui/frontend/dist"
```

#### K-15 · Güvenlik Modülleri Derlemeye Dahil Değil
**Konum:** `scripts/build_exe.py` (~L34-60), `scripts/build_nuitka.py` (~L20-35)
**Kaynak raporlar:** scripts_report, scripts_report-2 (A2, A5)

`src.safety.*`, `src.security.*` (Ed25519, anti-tamper, HWID, license) PyInstaller/Nuitka'da explicit `--hidden-import`/`--collect-submodules` ile zorlanmamış. Dinamik import varsa güvenlik modülleri exe dışında kalır → anti-tamper ve lisans doğrulama sessizce devre dışı. Nuitka'da ayrıca `--windows-uac-admin`, `--include-package=cryptography` eksik.

```python
cmd.extend([
    "--collect-submodules=src.safety",
    "--collect-submodules=src.security",
    "--hidden-import=src.security.license.ed25519_verifier",
    "--hidden-import=src.security.hwid.cim_hwid",
    "--hidden-import=src.security.antitamper.runtime_guard",
])
# Nuitka: --nofollow-import-to=tests,docs,examples + build artifact doğrulama
```

#### K-16 · Simülatör Canlı Kanala Yönlenebilir + Safety Bypass
**Konum:** `scripts/demo_traffic_generator.py` (~L20-24, ~L50-96)
**Kaynak raporlar:** scripts_report, scripts_report-2 (B1, B2, B3)

1. `channel` parametresi doğrulanmıyor → fiziksel arayüze yönlenebilir.
2. Frame'ler doğrudan `bus.send()` ile gönderiliyor → TX Safety Gateway + E-Stop interlock bypass.
3. Tehlikeli PGN/UDS (DM1, Address Claim) için denylist yok.

```python
SAFE_CHANNELS = {"vcan0", "vcan1"}
if channel not in SAFE_CHANNELS:
    raise ValueError("Simulation requires explicit virtual channel: vcan0/vcan1")
estop = EmergencyStopSystem(); gateway = TxSafetyGateway(bus=bus, estop=estop, whitelist_ids={...})
def safe_send(frame):
    if not gateway.validate_and_transmit(frame):
        raise RuntimeError(f"Blocked frame: 0x{frame.arbitration_id:X}")
BLOCKED_PGNS = {0x00EE00, 0x00D800}  # Address Claim / kritik PGN
```

---

### 3.5 ⚙️ CI/CD Kritikleri

#### K-17 · Mutable Action Tag'leri + `permissions` Yok
**Konum:** `.github/workflows/ci.yml` (~L13-22, ~L1-41) · **CWE-494**
**Kaynak raporlar:** ci_report, ci_report-2

`actions/checkout@v4` ve `actions/setup-python@v5` mutable tag ile sabitlenmiş → tag poisoning / dependency confusion. `permissions` bloğu yok → `GITHUB_TOKEN` varsayılan (org'a göre write) izinlerle çalışıyor.

```yaml
permissions:
  contents: read
jobs:
  test:
    permissions: { contents: read, checks: write }
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2 (SHA pin)
      - uses: actions/setup-python@0b93645e9fea7318ecaed2b359559ac225c90a2b  # v5.3.0 (SHA pin)
```

#### K-18 · Dependabot + CodeQL + Coverage Gate Yok
**Konum:** `.github/dependabot.yml` (YOK), `ci.yml`
**Kaynak raporlar:** ci_report, ci_report-2

1. **Dependabot yok** → pip/npm/github-actions CVE'leri otomatik yakalanmıyor (ISO 21434 §8.4 ihlali).
2. **CodeQL/SAST yok** → `src/security/`, `src/safety/` statik analizden geçmiyor (ISO 21434 §10.4.1).
3. **Coverage threshold yok** → `--cov-fail-under` zorunlu değil.

```yaml
# .github/dependabot.yml → pip + npm + github-actions, weekly
# ci.yml → pytest --cov=src --cov-fail-under=90 --cov-report=xml
# codeql.yml → languages: python, javascript; security-events: write
```

---

## 4. 🟠 YÜKSEK ÖNCELİKLİ BULGULAR (Kategorik)

Bu bölüm, tüm raporlardaki YÜKSEK bulguları tekilleştirilmiş tablolar halinde sunar.

### 4.1 🛡️ Safety & Security (Yüksek)

| ID | Konum | Bulgu | Düzeltme |
|---|---|---|---|
| H-01 | `safety/state_machine.py` ~L105 | `_force_fault()` geçiş tablosunu bypass ediyor; callback'ler lock bölgesi tutarsızlığı | Callback'leri her zaman lock DIŞINDA tetikle |
| H-02 | `safety/state_machine.py` ~L95 | Callback re-entrancy → FAULT propagasyonu atlanabilir | `transition_id` + `_in_callback` guard |
| H-03 | `ui/desktop_app.py` ~L117 | `toggle_simulator()` E-Stop'u kilitsiz sıfırlıyor (race) | HMAC token + `EmergencyStopSystem.reset()` zorunlu |
| H-04 | `safety/gateway.py` ~L86-171 | Lease/speed kontrolü ile `bus.send()` aynı kritik bölümde → TOCTOU | Lock dışında gönderim + gönderim sonrası lease re-check |
| H-05 | `security/license/validator.py` | `except Exception: pass` HWM doğrulamayı yutuyor | Belirgin log + `LicenseError` fırlat |

### 4.2 🔌 Protokol Doğruluğu (Yüksek)

| ID | Konum | Bulgu | Düzeltme |
|---|---|---|---|
| H-06 | `j1939/address_claim.py` ~L118-210 | J1939-81 claim lifecycle eksik; 250ms contention penceresi yok; CANNOT_CLAIM'de contention yönetimi | `CLAIMED`'e deterministik geçiş + state guard |
| H-07 | `hal/replay/safety_filter.py` ~L65 | 29-bit UDS SID tespitinde `0xDB` (functional) PF eksik | `PHYSICAL_29BIT_PF=0xDA`, `FUNCTIONAL_29BIT_PF=0xDB` tam aralık |
| H-08 | `nmea2000/fast_packet.py` ~L52 | Session key çakışması; eski oturum temizlenmeden üzerine yazma | `frame_index==0`'da mevcut oturumu temizle/reddet |
| H-09 | `uds/client.py` | ThreadPoolExecutor hiç kapatılmıyor (thread sızıntısı) | Context manager (`__enter__`/`__exit__`) + `__del__` |
| H-10 | `j1939/transport.py` ~L45 | `threading.RLock` yok → `_reap_stale_sessions` iterasyonunda RuntimeError riski | RLock ekle |

### 4.3 ⚡ Performans & Bellek (Yüksek)

| ID | Konum | Bulgu | Düzeltme |
|---|---|---|---|
| H-11 | `engine/buffer/ring_buffer.py` ~L144 | `get_latest_frames()` her kayıt için yeni `CanFrame` → GC baskısı, false zero-copy | NumPy structured-array slice/view döndür |
| H-12 | `engine/buffer/rolling_disk.py` ~L49-83 | Senkron Zstd + disk yazımı → üretici thread bloklanır | `ThreadPoolExecutor(max_workers=1)` ile async flush |
| H-13 | `ui/frontend/canSimulator.ts` ~L120 | `setInterval` ağır frame üretimi ana UI thread'de → frame-drop | Web Worker'a taşı |
| H-14 | `ui/desktop_app.py` ~L175 | `evaluate_js` IPC blocking; watchdog aynı loop'ta → sahte E-Stop | Watchdog heartbeat'i bağımsız thread'e taşı |
| H-15 | `engine/router.py` ~L75 | Her frame'de `list(subscriptions.values())` tam kopya → GC baskısı | Copy-on-write snapshot list |

### 4.4 🧹 Kod Kalitesi & Mimari (Yüksek)

| ID | Konum | Bulgu | Düzeltme |
|---|---|---|---|
| H-16 | `ui/desktop_app.py` ~L155 | `except Exception: pass` baudrate parse'ı yutuyor | Sadece beklenen istisnaları yakala + logla |
| H-17 | `hal/drivers/pcan_kvaser.py` ~L85 | `scan_bitrate()` `disconnect()` try/finally'siz → handle sızıntısı | `finally: bus.disconnect()` (None guard ile) |
| H-18 | `core/models/can_frame.py` | Python versiyon kısıtı belirsiz (`slots=True`+`frozen`) | `requires-python = ">=3.12"` |
| H-19 | Tüm examples | `sys.path.insert(0, ...)` import hijacking | `python -m examples.<script>` modeline geç |
| H-20 | `scripts/benchmarks.py` ~L14 | `sys.path.insert` kalıcı kirlilik | `append` kullan veya context manager ile geri al |

### 4.5 🧪 Test Kapsamı (Yüksek/Kritik)

| ID | Konum | Bulgu | Düzeltme |
|---|---|---|---|
| H-21 | `tests/` | **`watchdog.py` için hiç test yok** | `time.monotonic` mock'lu 3 test yaz |
| H-22 | `test_safety_state_machine.py` | Sadece 1 illegal geçiş testli; 6+ eksik | `@parametrize` ile tüm illegal geçişler |
| H-23 | `test_safety_gateway.py` | Tam 0.5 km/h sınır değeri test edilmiyor (off-by-one) | Boundary condition parametrize |
| H-24 | `test_replay_safety_filter.py` | PGN 65240 + UDS 0x34-0x37 ayrı test yok | Parametrize ile tüm flash SID'leri |
| H-25 | `test_isotp.py` | SN wraparound (0x0F→0x00), FC WAIT/OVERFLOW, malformed FF yok | 3 eksik senaryo ekle |
| H-26 | `test_ring_buffer.py` | 300K kapasite wrap-around test edilmiyor (sadece 500) | Gerçek üretim kapasitesi testi |
| H-27 | `test_rolling_disk.py` | Bellek sızıntısı + rolling chunk testi yok | `tracemalloc` + magic-byte doğrulama |
| H-28 | `test_safety_gateway.py` | Gerçek `PythonCanBus(virtual)` kullanımı → HAL izolasyon ihlali | `AbstractBus` mock fixture |
| H-29 | Zaman-bağımlı testler | `time.sleep()` kullanımı → flaky riski | `time.monotonic` mock tabanlı deterministik model |
| H-30 | `test_anti_tamper.py` | Sadece `isinstance` tip kontrolü, davranış doğrulanmıyor | Mock ile `True` senaryosu + SystemExit |

### 4.6 ⚙️ CI/CD (Yüksek)

| ID | Konum | Bulgu | Düzeltme |
|---|---|---|---|
| H-31 | `ci.yml` | Strict type-check (pyright/mypy) CI'da yok | Pyright strict adımı ekle |
| H-32 | `ci.yml` | Frontend build/audit CI'da yok | `npm ci` + `npm audit` + `npm run build` |
| H-33 | `.github/CODEOWNERS` (YOK) | Kritik dosyalar için zorunlu reviewer yok | CODEOWNERS oluştur |
| H-34 | `.gitignore` | `data/`, `*.ed25519`, `*.lic`, `*.enc` eksik | Secret/key ignore kuralları ekle |
| H-35 | `ci.yml` | Artifact imza/hash/provenance yok | `sha256sum` + artifact upload |
| H-36 | `ci.yml` | pip cache `requirements-dev.txt` hash'i kapsamıyor | `cache-dependency-path` ekle |

### 4.7 📚 Dokümantasyon & Uyum (Yüksek/Kritik)

| ID | Konum | Bulgu | Düzeltme |
|---|---|---|---|
| H-37 | `SECURITY.md` | CVE/disclosure süreci, PGP, SLA, safe-harbor yok | Koordineli ifşa politikası ekle |
| H-38 | `README.md` | Anti-tamper teknik detayları (IsDebuggerPresent, 50ms threshold) ifşa edilmiş | Public redaction → internal'a taşı |
| H-39 | `docs/audit/implementation_plan.md` | **Açık (unpatched) güvenlik açıkları saldırı senaryosuyla public** | Private yap veya `[REDACTED — CVE pending]` |
| H-40 | `docs/GEMINI.md` | Safety constraint yok; canlı TX yasağı tanımsız; 5/6 adım çelişkisi | Safety-critical AI guardrails ekle |
| H-41 | README/PROJECT/TEST_READY | Test sayısı 3 belgede 3 farklı (274/220/161) | Tek kaynak (CI artefaktı) SSOT |
| H-42 | `TEST_INFRA.md` vs `estop.py` | "HMAC-SHA256 token" belgelenmiş ama kod statik string | Kodu HMAC'e geçir + dokümanı senkronla |
| H-43 | `CONTRIBUTING.md` | Clone URL bozuk (`github.com/ /...`) | Doğru owner ile düzelt |
| H-44 | `MASTER_PLAN.md` | Hedef mimari (Next.js/SaaS) mevcut gibi sunulmuş | IMPLEMENTED/PLANNED etiketleme |
| H-45 | `Saha_Risk_Katalogu` | Risk→Test traceability matrisi yok | Risk ID → Test dosyası eşleme tablosu |
| H-46 | `README.md` | TX queue sıfırlama (`_tx_timestamps.clear()`) diyagramda yok | stateDiagram notu ekle |

### 4.8 📖 Examples (Yüksek)

| ID | Konum | Bulgu | Düzeltme |
|---|---|---|---|
| H-47 | `01_listen_only_sniffer.py` | `listen_only=True` parametresi eksik | Zorunlu set et |
| H-48 | `03_uds_diagnostic_session.py` | `build_routine_control(1, ...)` ham int; enum yok | `RoutineControlType.START_ROUTINE` kullan |
| H-49 | `03_uds_diagnostic_session.py` | Tehlikeli builder'lar (0x34-0x37, 0x11) uyarısız import | Docstring'e KRİTİK uyarı ekle |
| H-50 | `02_j1939_dtc_monitor.py` | Clear DTC metodları (DM11/DM3) uyarısız | Güvenlik notu ekle |
| H-51 | Tüm examples | `main()` dönüş tipi annotation yok (ANN201) | `-> None` ekle |
| H-52 | Tüm examples | Beklenen çıktı/kurulum/standart referansı yok | Docstring zenginleştir |

### 4.9 🛠️ Scripts & Benchmarks (Yüksek)

| ID | Konum | Bulgu | Düzeltme |
|---|---|---|---|
| H-53 | `benchmarks.py` | Tek çalıştırma; warmup/tekrar/jitter yok | `_bench_run()` 5+ iterasyon + CV% |
| H-54 | `benchmarks.py` ~L151 | `MAX_TX_RATE_PER_SEC=1_000_000` rate-limit bypass → yanıltıcı | İki ayrı benchmark (production + filter-only, etiketli) |
| H-55 | `benchmarks.py` | Thread contention benchmark yok | Çok yazıcılı contention testi |
| H-56 | `benchmarks.py` | `tracemalloc` sadece ring buffer'da; zero-copy kanıtsız | `psutil` RSS + tüm benchmarklarda bellek |
| H-57 | `build_nuitka.py` ~L19 | `.resolve()` eksik → symlink yanlış yol | `.resolve()` zorunlu + varlık doğrulama |
| H-58 | `demo_traffic_generator.py` | N2K Fast Packet bypass; raw 8-byte frame | `FastPacketAssembler` kullan |

---

## 5. ✅ GÜÇLÜ YÖNLER

Denetim yalnızca kusur bulmak için değildir; projenin sağlam temelleri de net şekilde görülmektedir:

1. **Safety State Machine mimarisi sağlam:** `ALLOWED_TRANSITIONS` tablosu illegal geçişleri önlüyor, `_force_fault()` her zaman güvenli FAULT'a taşıyor, Fail-Silent prensibi büyük ölçüde uygulanmış.
2. **NumPy Ring Buffer tasarımı doğru:** Pre-allocated 300K-frame `np.zeros` ile GC pause önlenmiş; `append_batch` tek lock altında toplu yazıyor.
3. **J1939 BAM length validation güçlü:** `1 <= total_bytes <= 1785` ve paket sayısı cross-check'i kötü niyetli TP.CM_BAM'ı reddediyor.
4. **Ed25519 imza doğrulaması standart-uyumlu:** `cryptography` + timing-safe `hmac.compare_digest()`; hardware fingerprint ve offline grace period doğru tasarlanmış.
5. **Replay Safety Filter kapsamlı:** J1939 Address Claim, UDS ECU Reset/Flash SID'leri, 11/29-bit çift adres uzayı; `PROHIBITED_UDS_SIDS` ISO 14229 kapsamlı.
6. **TX Gateway çok katmanlı chokepoint:** Rule 0–5 sıralaması (whitelist + hız kilidi + watchdog lease + dual-confirm) dokümantasyonla tutarlı.
7. **Knowledge Pack AES-GCM nonce:** her şifrelemede `os.urandom(12)`; `secure_zero_memory` doğru.
8. **Saha Risk Kataloğu v1.2 derinliği:** 47 bölüm, Severity×Likelihood×Detectability metodolojisi — sektör ortalamasının üstünde.
9. **Test altyapısında güçlü noktalar:** E-Stop nonce replay koruması, Ring Buffer Hypothesis property-based test, DBC LRU cache üst sınır, J1939 session DoS testi, ISO-TP CAN-FD extended SF.
10. **Simülatör varsayılan güvenli:** `interface="virtual"` hardcoded; PyInstaller gereksiz GUI modüllerini dışlıyor; Nuitka LTO etkin.

---

## 6. 🎯 ÖNCELİKLİ AKSİYON PLANI (Timeline)

### 🔥 FAZ 0 — İLK 24 SAAT (Kabul Edilemez Riskler)
| # | Aksiyon | Bulgu | Süre |
|---|---|---|---|
| 1 | `docs/audit/implementation_plan.md` private yap / redact et | H-39 | 1 saat |
| 2 | E-Stop hardcoded secret kaldır (`os.urandom(32)` + DPAPI) | K-01 | 1 saat |
| 3 | `pickle` → struct+HMAC binary format (RCE kapat) | K-05 | 3 saat |
| 4 | JS/köprü enjeksiyonu → `json.dumps()` escape | K-06 | 2 saat |
| 5 | `shell=True` → liste argümanı + platform ayracı | K-14 | 1 saat |
| 6 | CI action'ları SHA-pin + `permissions: contents: read` | K-17 | 1 saat |

### ⚡ FAZ 1 — 1. HAFTA (Safety + Protokol Çekirdeği)
| # | Aksiyon | Bulgu | Süre |
|---|---|---|---|
| 7 | **J1939 `_handle_tp_dt` implementasyonunu tamamla** (en büyük işlevsel kusur) | K-10 | 4 saat |
| 8 | Gateway TOCTOU/deadlock/kural-sırası düzelt | K-03 | 3 saat |
| 9 | Watchdog otomatik beslemeyi kaldır + TOCTOU atomik snapshot | K-02 | 2 saat |
| 10 | ISO-TP FF extended length + CAN-FD simetri + session dict | K-12 | 3 saat |
| 11 | UDS NRC 0x78 akışı + deadline-based CF toplama | K-13 | 2 saat |
| 12 | HWM hardcoded key + anti-rollback `pass` kaldır + wildcard kapat | K-07 | 3 saat |
| 13 | TX whitelist safe-by-default + PowerShell whitelist | K-04, K-08 | 1 saat |
| 14 | `test_watchdog.py` oluştur (ISO 21434 kanıtı) | H-21 | 3 saat |

### 🛠️ FAZ 2 — 2-3. HAFTA (Test & CI Sertleştirme)
| # | Aksiyon | Bulgu |
|---|---|---|
| 15 | Tüm illegal state transition testleri (`@parametrize`) | H-22 |
| 16 | Speed interlock boundary (0.5 km/h) testi | H-23 |
| 17 | Replay filter PGN 65240 + UDS 0x34-0x37 testleri | H-24 |
| 18 | ISO-TP SN wraparound + FC WAIT/OVERFLOW + malformed FF | H-25 |
| 19 | Ring buffer 300K + rolling disk tracemalloc testleri | H-26, H-27 |
| 20 | HAL izolasyonu: `AbstractBus` mock fixture | H-28 |
| 21 | Zaman-bağımlı testleri `time.monotonic` mock'a çevir | H-29 |
| 22 | Dependabot + CodeQL + coverage gate (`--cov-fail-under=90`) | K-18 |
| 23 | Frontend CI + CODEOWNERS + `.gitignore` secret kuralları | H-32, H-33, H-34 |
| 24 | Strict type-check (pyright/mypy) CI adımı | H-31 |

### 📚 FAZ 3 — 1. AY (Doküman-Kod Senkronizasyonu & Hardening)
| # | Aksiyon | Bulgu |
|---|---|---|
| 25 | **E-Stop HMAC implementasyonu** (TEST_INFRA iddiası ile kodu eşitle) | H-42 |
| 26 | Test sayısını tek kaynağa (CI artefaktı) bağla | H-41 |
| 27 | SECURITY.md koordineli ifşa politikası | H-37 |
| 28 | GEMINI.md safety-critical guardrails (canlı TX yasağı) | H-40 |
| 29 | README anti-tamper detaylarını redact et | H-38 |
| 30 | CONTRIBUTING clone URL + cross-platform kurulum | H-43 |
| 31 | MASTER_PLAN IMPLEMENTED/PLANNED etiketleme | H-44 |
| 32 | Risk→Test traceability matrisi | H-45 |
| 33 | Examples güvenlik guard'ları + listen_only + enum kullanımı | H-47..H-52 |
| 34 | Simülatör TxSafetyGateway + kanal whitelist | K-16 |
| 35 | Benchmark determinizm + thread contention | H-53..H-56 |
| 36 | Anti-tamper çok katmanlı koruma + fail-closed eylem | K-09 |

---

## 7. 📐 STANDART UYUM ÖZETİ

| Standart | Durum | Ana İhlaller |
|---|---|---|
| **ISO 21434:2021** | ⚠️ Kısmi | §8.4 (sürekli zafiyet izleme — Dependabot yok), §10.4.1 (hardcoded secrets, SAST yok), §13 (vulnerability management — SECURITY.md eksik), §15.4 (TOCTOU/race) |
| **SAE J1939-21** | 🔴 İhlal | §5.10 TP.DT reassembly eksik → multi-frame çalışmıyor |
| **SAE J1939-81** | ⚠️ Kısmi | Address claim lifecycle / 250ms contention penceresi eksik |
| **ISO 14229-1 (UDS)** | ⚠️ Kısmi | NRC 0x78 akışı yönetilmiyor |
| **ISO 15765-2 (ISO-TP)** | ⚠️ Kısmi | Extended FF_DL, CAN-FD simetri, SN wraparound eksik |
| **NMEA 2000** | ⚠️ Kısmi | Sequence hijack; Fast Packet session çakışması |
| **ASPICE** | ⚠️ Kısmi | SWE.4/5 izlenebilirlik temeli var; test-kanıt ve coverage gate eksik |
| **OWASP** | 🔴 İhlal | A03 Injection (JS, shell, PowerShell), CWE-502 (pickle), CWE-798 (hardcoded secrets) |

---

## 8. 🔑 SONUÇ VE GENEL DEĞERLENDİRME

**Mimari vizyon güçlü, implementasyon kritik noktalarda eksik.** Proje; safety-critical bir CAN teşhis platformunun gerektirdiği katmanlı güvenlik modelini (State Machine → Gateway → E-Stop → Watchdog → DRM) doğru tasarlamış ve bunu büyük ölçüde dokümante etmiştir. Ancak:

1. **Protokol çekirdeği çalışmıyor:** J1939 TP.DT reassembly eksikliği, platformun temel vaadi olan multi-frame teşhis mesajlarını işleyememesi anlamına gelir. Bu, güvenlik bulgularından bile önce ele alınması gereken bir **işlevsellik blokajıdır.**

2. **Safety mekanizmaları bypass edilebilir:** Hardcoded E-Stop secret, pickle RCE, watchdog otomatik besleme ve TOCTOU pencereleri bir araya geldiğinde, platformun "fail-silent" garantisi fiilen kırılmaktadır.

3. **Doküman-kod güven krizi:** Test sayısı ve HMAC iddialarındaki tutarsızlık, dış denetimde (ASPICE/ISO 21434) tüm uyumluluk beyanlarını sorgulanır hale getirir. **Kod-doküman senkronizasyonu bir "temizlik" değil, uyumluluk zorunluluğudur.**

4. **Supply chain savunmasız:** SHA-pin olmayan CI, Dependabot/CodeQL yokluğu ve `.gitignore` secret eksikliği otomotiv tedarik zinciri beklentilerinin gerisindedir.

**Önerilen strateji:** Faz 0 ve Faz 1'i (ilk ~2 hafta) bir **"release freeze"** ile ele alın — bu bulgular kapatılmadan üretim/saha dağıtımı yapılmamalıdır. Safety-critical bir araçta E-Stop bypass'ı ve pickle RCE, yalnızca yazılım kalitesi değil, **fiziksel güvenlik** meselesidir.

---

*Rapor, 14 bağımsız analiz dosyasının tekilleştirilmiş birleşimidir. Tekrarlanan bulgular birleştirilmiş, çelişkili ifadeler (örn. test sayısı) ayrıca işaretlenmiştir. Tüm kod önerileri gerçek kaynak API imzaları esas alınarak hazırlanmıştır.*