# Universal CAN-Bus Diagnostic & Telemetry Tool — Code Review & Düzeltme Devir Dokümanı

**Tarih:** 2026-08-31
**Proje yolu:** `C:\Users\canak\Desktop\Universal-CAN-BUS-Tool` (Python, Windows/WebView2)
**Bu dosyanın amacı:** Oturum yarıda kaldı; yeni devralan yapay zekâ bu dokümanla kaldığı yerden devam etmeli.

---

## ⚠️ 0. DURUM GÜNCELLEMESİ (2026-09-01) — BU DOKÜMANDAKİ AÇIK İŞLER TAMAMLANDI

Bu dokümanın kalan tüm işleri **tamamlandı** ve **commit'lendi**:

- **Dalga 3:** 2 kırmızı test kapatıldı (poller P5 davranışına göre yeniden yazıldı; DBC 0xFFBE→NOT_AVAILABLE MSB kuralıyla). D3 (GUI interface kablolaması), G2 (HWM iki-alan formatı), G3 (current_ts kaldırıldı → ClockProvider) uygulandı.
- **Dalga 4:** B3+B7 (secret split-brain + ctypes), G5+G6 (HWM karantina + atomik yazım), B8 (800ms watchdog), E11, B6 (kilit dışı dispatch), P7 (kilit kapsamı), P6 (self-echo + motor kilidi), D4+D5 (DM PGN tablosu + TP tünelleme), D7 (DLL System32), D8 (kanonik send + privileged_send), D10 (power referans sayacı) — hepsi regresyon testli.
- **Dalga 5:** PROJECT.md VIN PGN 65260, README hizalama, secrun FP sabiti düzeltildi.
- **K1-K4 kararı:** Dördünde de **(b) dürüst doküman hizalaması** seçildi ve uygulandı (RP1210/BLF/CSV iddiaları gerçeğe indirildi; lisans yığını ve E-Stop reset "altyapı hazır / yerel kurtarma" olarak dürüstçe sınıflandırıldı).
- **Test durumu:** 1061 → **1101/1101 PASSED**, ruff 0 hata, kapsam %87.
- **Commit durumu:** Tüm iş 6 tematik commit olarak geçmişe alındı (protocols / safety+security / engine+hal / ui+main / tests / docs). Working tree temizdir (`.scratch/` yerel benchmark altyapısı hariç — commit edilmedi).
- **Hâlâ eksik:** (1) `secrun scan ./` bu ortamda kurulu değil — bir secrun'lu oturumda doğrulanmalı (beklenti: yalnız 22 bilinen FP; son değişiklik doküman + 1 test sabiti). (2) **"Küçükler"** (B9-B17, E8/E10, E12-E15, P11-P16, G11-G15) — tek satırlık listedir, ayrıntı için 78-bulgu review raporu gerekir (bu dokümanda yok). (3) İstenirse (a)-yolları: RP1210 CLI kablolama (K4), BLF/CSV replay parser (K3), lisans akışını composition root'a bağlama (K1), bağımsız E-Stop doğrulayıcı (K2).

**Devralan oturum:** aşağıdaki "yarım kaldı" bölümleri TARİHSEL KAYIT olarak okuyun; yeniden uygulamayın. Yeni iş için 0. bölümün "Hâlâ eksik" listesinden seçin.

---

## 1. Büyük Resim

Projeye 5 aşamalı kapsamlı code review yapıldı (safety → security → hal → protocols → engine/core/ui).
Sonuç: **78 bulgu** (13 Yüksek, 34 Orta, 31 Düşük). `secrun scan` yalnızca 22 yanlış pozitif üretti (test sabitleri); gerçek kimlik bilgisi sızıntısı yok.

Üç kök desen tespit edildi:
1. **"Kütüphane var, entegrasyon yok"** — güvenlik yığını, RP1210, lisans/anti-tamper, ARMED TX akışı, arayüz seçimi ürüne bağlı değil ama README bağlı olduğunu iddia ediyor.
2. **"Test bayrakları üretim imzasında"** — `allow_all_for_testing`, wildcard ortam değişkeni, `user_confirmed=True` varsayılanları.
3. **"Kripto töreni, gerçek yetkilendirme değil"** — E-Stop reset jetonunu aynı süreç üretip tüketiyor.

Ardından onaylı bir düzeltme planı **dalgalar halinde** uygulanmaya başlandı. Kullanıcı her dalga sonunda duraklama ve onay istiyor.

### Çalışma kuralları (kullanıcı tercihleri — devralan uymalı)
- Kullanıcı **Türkçe** iletişim kurar; raporlar Türkçe yazılmalı.
- **Aşama/dalga bazlı onay kapıları:** her dalga bitince DUR, kullanıcıdan "devam" bekle. Onaysız sonraki dalgaya geçme.
- Bulgular önem sırasıyla; her bulguda dosya/satır/kanıt/etki/çözüm.
- **Commit istenmedi** — değişiklikler çalışma ağacında bırakılacak. Depoda ayrıca önceki çoklu-ajan oturumundan kalma commit'lenmemiş değişiklikler var; **bizim değişikliklerimiz yalnızca bu dokümanda listelenen dosyalarda.**
- Doğrulama üçlüsü her dalgada: `python -m pytest -q -p no:cacheprovider` + `python -m ruff check .` + `secrun scan ./` (repo kökünden).

---

## 2. Tamamlanan Dalgalar (doğrulanmış)

### Dalga 0 — Taban çizgisi ✅
- Taban: **1061 test yeşil**, ruff temiz.
- Not: `tests/unit/test_uds_client.py` kaynaklı aralıklı bir pytest koleksiyon hatası görülmüştü; 12+ tekrarda üretilmedi. CI'da izlenmeli.

### Dalga 1 — P0 düzeltmeleri ✅ (1070/1070 yeşil)
| Bulgu | Dosya | Değişiklik |
|---|---|---|
| E1 | `src/ui/desktop_app.py` | 64B'yi aşan J1939 yeniden-birleştirme `dlc=len(data)` ile ValueError fırlatıp telemetri thread'ini öldürüyordu → veri 64B'ye kırpıldı, `length_to_dlc`, try/except + `& 0x1FFFFFFF` ID maskesi |
| D2 | `src/hal/rp1210/client.py` | `read_message`: RP1210 hata kodları ≥128 veri uzunluğu sanılıyordu → `0 < ret < 128` veri koşulu |
| D1 | `src/hal/drivers/pcan_kvaser.py` | `state="PASSIVE"` string'i sürücü enum denetimini geçemiyordu → `can.BusState.PASSIVE` |
| E2 | `src/ui/desktop_app.py` | `_push_frame_to_ui` f-string JS enterpolasyonu → `json.dumps` payload (enjeksiyon kapandı) |
| P2 | `src/protocols/j1939/transport.py` | RTS çarpışmasında yeni oturumun CTS'i düşüyordu → `_pending_tx_frames`'e kuyruklanıyor |

9 regresyon testi eklendi: `test_desktop_app.py` (3), `test_rp1210.py` (4), `test_python_can_bus.py` (1), `test_j1939_transport.py` (1).

### Dalga 2 — Güvenlik varsayılanları ✅ (1074/1074 yeşil)
| Bulgu | Dosya | Değişiklik |
|---|---|---|
| B1 | `src/safety/gateway.py` | `allow_all_for_testing` yapıcıdan kaldırıldı → yalnız `TxSafetyGateway.for_testing()` fabrikası; 14 çağrı yeri migrate edildi (testler + `scripts/demo_traffic_generator.py`) |
| P1 | `src/protocols/uds/client.py` | `user_confirmed` varsayılanları `False` (`write_did`, `request_download`, `ecu_reset`, `start_routine`, `_send_payload`, `_send_and_receive`); `src/protocols/uds/flasher.py` artık `config.user_confirmed`'ı kritik çağrılara iletiyor; 5 mutlu-yol testine açık `user_confirmed=True` eklendi |
| P9 | `src/protocols/uds/flasher.py` | `gateway` zorunlu bağımlılık; E-Stop denetimi koşulsuz |
| B2 | `src/safety/multiplexer.py` | kritiklik/onay yapıcıdan kaldırıldı → `send()`'in çağrı-bazlı keyword parametreleri |
| G4 | `src/security/license/validator.py` | `UCAN_ALLOW_WILDCARD_LICENSE` ortam değişkeni arka kapısı kaldırıldı (yalnız açık yapıcı opt-in) |
| E5 | `src/safety/gateway.py` + `src/engine/pipeline/reassembly_pipeline.py` | Gateway'e `whitelist_masks` `(değer, maske)` desteği; pipeline'a `j1939_protocol_response_masks()` + `PROTOCOL_RESPONSE_11BIT_IDS` yardımcıları; reddedilen protokol yanıtları artık `warning` seviyesinde |

4 regresyon testi: `test_safety_gateway.py` (3: maske ailesi, masks-only fail-closed değil, yapıcı imzası denetimi), `test_reassembly_pipeline.py` (1: yardımcı maske doğrulaması).

---

## 3. YARIM KALAN: Dalga 3 (GÖREV BURADAN DEVAM EDECEK)

**Durum:** 5 madde tamamlandı, 2 test eski davranışı beklediği için KIRMIZI, 3 madde hiç başlanmadı.

### 3.1 Tamamlanan Dalga 3 maddeleri
| Bulgu | Dosya | Değişiklik |
|---|---|---|
| E6 | `src/engine/pipeline/reassembly_pipeline.py` | VIN dalı `target_pgn in (PGN_VIN, 65259)` → `target_pgn == PGN_VIN` (65259 Component Identification artık VIN olarak çözümlenmiyor) |
| P4 | `src/protocols/uds/client.py` | Yapıcıda `bus is None and rx_sub is None` → ValueError (RX yolu yoksa fail-fast); `_send_and_receive` başında `self.bus is None` → `ProtocolError(code="UDS_NO_RX_PATH")` |
| P5 | `src/protocols/obd/poller.py` | `_schedule_retry` backoff dalında `job.state = RETRY_BACKOFF` + `self._active_job = None` (aktif yuva serbest bırakılıyor; backoff bitince `step()` işi yeni deadline ile yeniden seçip GERÇEKTEN yeniden gönderiyor). `tests/unit/test_obd_poller.py`'deki exhaustion testi yeni davranışa güncellendi + `test_poller_retry_retransmits_after_backoff` eklendi |
| E4 | `src/engine/decoder/dbc_decoder.py` | 8/16/24/32-bit işaretsiz sinyallerde artık `J1939SentinelFilter` MSB aralıkları kullanılıyor (`_SENTINEL_CHECKS` eşlemesi modül düzeyinde tanımlı): `0xFE**`→ERROR, `0xFF**`→NOT_AVAILABLE, RESERVED→ERROR, PARAMETER_SPECIFIC→VALID. 2/4-bit discrete eski kesin-değer semantiğinde bırakıldı. Regresyon testi `tests/unit/test_dbc_decoder.py::test_sentinel_msb_ranges_flagged_for_16bit_signals` (EEC1 hat ID'si `0x0CF00400` — DBC'nin `0x80000000` extended bayrağı düşürülmüş hali) |
| P8 | `src/protocols/uds/flasher.py` | `execute_flash` içinde `recovery_needed` bayrağı (adım 2 sonrası True); except bloğunda `_best_effort_recovery()` → Hard Reset (0x11 0x01) denemesi, hatalar yutulur/loglanır, orijinal hata yeniden fırlatılır. 2 regresyon testi `tests/unit/test_protocol_binary_conformance.py`'de |

### 3.2 ⚠️ ŞU AN KIRMIZI OLAN 2 TEST (devralanın ilk işi)
Tam paket koşusu: **2 failed, 1076 passed**.

**a) `tests/e2e/test_challenger_diagnostics.py::TestPollerConcurrencyAndStarvationStress::test_poller_nrc_0x21_busy_backoff_and_retry_exhaustion`**
- Neden: Test, P5 öncesi davranışı bekliyor — ardışık NRC 0x21 kareleri yeniden gönderim olmadan `retry_count`'u artırıyordu. P5 sonrası iş backoff'ta park halindeyken (`_active_job=None`) gelen tekrar NRC'ler yok sayılıyor (bu DOĞRU davranış: bekleyen istek yokken gelen yanıt gürültüdür).
- Yapılacak: Testi yeniden yaz — her retry döngüsü `clock.advance(backoff+pay)` + `poller.step()` (yeniden gönderim) + NRC enjeksiyonu şeklinde ilerlesin. `DeterministicClock` sınıfının `advance(seconds)` metodu var (dosya içi, satır ~71). Beklenen akış: step→NRC(retry 1)→advance+step→NRC(retry 2)→advance+step→NRC(retry 3)→advance+step→NRC(retry 4 > MAX=3 → FAILED). Backoff gecikmeleri: 0.05, 0.1, 0.2 s (`BASE_BACKOFF_S * 2**(n-1)`); rate limiter min aralığı 0.025 s (40 Hz) — advance değerleri bunu aşmalı.

**b) `tests/unit/test_dbc_validity_filter.py::test_dbc_signal_parameter_error_discrete_values_detected`**
- Neden: Test, 16-bit `0xFFFE` için ERROR bekliyor (eski max-1/max kesin-değer sözleşmesi). E4 sonrası J1939-71 MSB kuralı geçerli: `0xFFFE` (MSB=0xFF) → **NOT_AVAILABLE**. Test J1939-71 ile çelişen eski davranışı kodluyordu.
- Yapılacak: `data=b"\x00\x0e\xfe\xfe\xff\x00\x00\x00"` yerine `data=b"\x00\x0e\xfe\xff\xfe\x00\x00\x00"` kullan ve beklentileri güncelle:
  - `EngineSpeed`: raw 65534 (0xFFFE) → `is_valid False`, `status == SignalStatus.NOT_AVAILABLE` (artık ERROR değil)
  - `ActualEnginePercentTorque`: raw 254 (0xFE) → ERROR (değişmedi; byte 2 = 0xFE)
  - `EngineStarterMode`: raw 14 (byte1=0x0E, alt nibble) → ERROR (4-bit discrete: max-1)
  - Test yorumunu "J1939-71 MSB sentinel aralıkları" diye güncelle.

### 3.3 BAŞLANMAMIŞ Dalga 3 maddeleri (karar gerektirmeyenler)

**D3 — GUI arayüz kablolaması** (`src/ui/desktop_app.py`, `src/main.py`)
- Sorun: GUI her zaman `interface="virtual"` kuruyor; `main.py:99` `args.interface`'i desktop app'e hiç geçirmiyor; `_reconnect_bus` da sanal sabitli. README'in `--interface=pcan/kvaser` örnekleri sessizce simülatörde çalışıyor.
- Yapılacak: `UniversalCanDesktopApp.__init__`'e `interface: str = "virtual"` parametresi ekle; kurulum ve `_reconnect_bus`'ta `PythonCanBus(interface=self.interface_val, ...)`; `update_settings`'e `"interface"` anahtarı (değişince `reconnect_needed`); `main.py` GUI yolunda `interface=args.interface` geçir. NOT: `UniversalCanDesktopApp.run()` frontend `dist/index.html` bulamazsa erken döner — GUI uçtan uca test edilemeyebilir; en azından constructor/reconnect birim düzeyinde doğrula.

**G2 — Lisans grace periyodu kalıcılığı** (`src/security/license/validator.py`)
- Sorun: `last_online_sync_ts` her kurulumda `time.time()`'a sıfırlanıyor → 7 günlük çevrimdışı süre hiç dolmaz.
- Yapılacak: HWM dosyasıyla birlikte HMAC'li kalıcı depolama. HWM formatı şu an `"{ts}.{hmac_hex}"` (satır ~82-101 okuma, ~138-143 yazma). Öneri: formatı `"{ts}:{last_online_sync_ts}.{hmac}"` şeklinde genişlet (HMAC her iki alanı da kapsasın); eski tek alanlı dosyaları geriye uyumlu oku. `__init__`'te geri yükle, `verify_token` yazımında güncelle. **Dikkat:** `tests/unit/test_license_validator.py` ve `tests/unit/test_adversarial_stress.py`/`test_adversarial_final_gate.py` içindeki HWM dosyalı testler etkilenir.

**G3 — Saat enjeksiyonunun taşınması** (`src/security/license/validator.py`)
- Sorun: `verify_token(token_str, current_ts=...)` çağıranın saat vermesine izin veriyor → anti-rollback mekanizması bypass edilebilir.
- Yapılacak: `current_ts` parametresini KALDIR; yapıcıya `clock: ClockProvider | None = None` ekle (`src/core/contracts/ports.py::ClockProvider`, varsayılan `SystemClockProvider`); `verify_token` `now = int(self.clock.now_monotonic())` kullansın. **Etki alanı büyük:** `verify_token(..., current_ts=X)` çağrıları ~20 testte geçiyor (`test_license_validator.py` ~6, `test_adversarial_stress.py` ~8, `test_adversarial_final_gate.py` ~6). Her testte sahte `ClockProvider` kur ve `current_ts` argümanlarını kaldır. Monotonic tabanlı denetimlerin (`boot_monotonic` karşılaştırmaları) yeni saat sağlayıcıyla tutarlı kaldığını doğrula.

### 3.4 Dalga 3 kapanış doğrulaması
Yukarıdakiler bitince repo kökünden:
```
python -m pytest -q -p no:cacheprovider   # ~1081 test yeşil olmalı
python -m ruff check .                     # temiz
secrun scan ./                             # yalnız 22 bilinen yanlış pozitif
```
Ardından kullanıcıya rapor + DUR (kullanıcı dalga aralarında onay istiyor).

---

## 4. KULLANICI KARARI BEKLEYEN MADDELER (K1-K4)

Dalga 3'ün bazı maddeleri ve Dalga 4/5'in bir kısmı bu kararlara bağlı. Kullanıcıya soruldu, henüz yanıt yok:

| # | Konu | Seçenekler |
|---|---|---|
| K1 | Lisans/anti-tamper yığını (G1/E7) | (a) composition root'a bağla, (b) README iddialarını kaldır |
| K2 | E-Stop reset UX (E3/B5) | (a) UI'da gerçek operatör challenge akışı, (b) "demo" sınıflandırması |
| K3 | CSV/BLF replay (D9) | (a) uygula, (b) dokümandan çıkar |
| K4 | RP1210 sürücüsü (D6) | (a) `RP1210Bus`'ı tamamla, (b) README/CLI'den çıkar |

---

## 5. KALAN DALGALAR (özet)

### Dalga 4 — Sağlamlaştırma ve hijyen (~3-4 gün)
- **B3** `secret_provider.py`: DPAPI/fallback split-brain — `get_secret` KeyError yolunda fallback deposunu da denetlesin
- **G5/G6** `license/validator.py`: HWM anahtar kaybı kurtarma kodu; HWM yazımı temp+replace atomik
- **B7** `secret_provider.py`: DPAPI ctypes tamponlarını isimli referansa bağla (GC yaşam süresi)
- **E11** `rolling_disk.py`: anahtar kaybı davranış belgesi
- **B6** `state_machine.py`: illegal geçiş dalında callback'ler kilit dışına
- **P7** `j1939/transport.py`: RTS/ABORT dalları `_sessions_lock` içine
- **P6** `address_claim.py`: `other_name == self.name` yok say + motor içi kilit
- **B8** `watchdog.py`: varsayılan 800.0 ms
- **D4/D5** `hal/replay/safety_filter.py`: PGN tablosunu J1939-73'ten türet (DM4=65229, DM5=65230 eklenmeli; etiketler yanlış), TP.CM/TP.DT tünelleme politikası
- **D7** `rp1210/client.py`: DLL arama sırası mutlak System32 önce
- **D8** `hal/base.py`: tek kanonik TX metodu + gateway için açık privileged port (`hasattr("_send_raw")` recursion tuzağı)
- **D10** `win32_power.py`: referans sayacı
- Küçükler: B9 (nonces budama), B10 (last_event koru), B11 (ölü dal), B13 (token mesajı), B14 (offset çakışma denetimi), B16/B17, E8 (decoder cache clear), E10 (ValueError yakala), E12-E15, P11-P16, G11-G15

### Dalga 5 — Doküman hizalama (~0.5 gün)
- README: arayüz tablosu/CLI örnekleri gerçek duruma göre, RP1210 ve BLF/CSV iddiaları (K3/K4 kararına göre), test sayısı tek kaynağa (CI artefaktı), 800 ms watchdog ifadesi
- PROJECT.md: Feature 15 VIN PGN düzeltmesi, milestone durumları
- `tests/e2e/test_phase2_e2e.py:278` sabit adı `estop_production_key...` → `estop_test_fixture...` (secrun yeniden doğrula)

---

## 6. Hızlı Referans

- Doğrulama: repo kökünden `python -m pytest -q -p no:cacheprovider && python -m ruff check . && secrun scan ./`
- Test sayısı seyri: taban 1061 → Dalga 1 sonrası 1070 → Dalga 2 sonrası 1074 → Dalga 3 hedef ~1081
- Protokol matematiği review sırasında doğrulandı: CRC-8 tabloları + SAE J1850 check vektörü (0x4B), ISO-TP bayt düzenleri, J1939 NAME/DTC çözümleme, N2K Fast Packet — bunlara dokunurken dikkat.
- `secrun scan ./` çıkışı 22 yanlış pozitif (test sabitleri) — normal kabul ediliyor; YENİ isabet çıkarsa incele.
- Görev listesi (Qoder tasks) Dalga 3 için #11 numarada açık.
