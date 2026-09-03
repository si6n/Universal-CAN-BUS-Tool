# DBC-Knowledge-Pack Genişletme — Web Taraması (2026-09-02)

Kapsam: Yalnızca internet taraması. Hiçbir dosya indirilmedi veya `data/dbc/`'ye kopyalanmadı.
Amaç: `data/dbc/` (v3.0.0, 6 kategori, 133 DBC) paketini genişletecek açık kaynak DBC havuzlarını
lisans durumuyla birlikte tespit etmek. Entegrasyon kararı ve indirme sonraki oturumun işidir.

> **SONUÇ (aynı gün, 2026-09-02):** Tier-1'in 7 kaynağı (kona-ev-dbc, jaguar-xf-x250-can,
> leaf_can_bus_messages, model3dbc, autti/abraham, ARCFOX_dbc, open-vehicle-control-system/dbc)
> + alan707/openOBD2 → paket **v3.1.0** olarak entegre edildi: 20 DBC / 27 curated çıktı
> (`curate_batch3_sources.py`), 153 DBC / 13.497 mesaj / 64.683 sinyal, 160/160 cantools-strict,
> `verify_pack.py` temiz, pack pytest 38/38, ana proje DBC testleri 10/10.
> `data/dbc/`'ye deploy edildi (manifest hash'leri 153/153 eşleşiyor). openOBD2'de PID 0x09 adı
> SAE J1979'a göre Bank1→Bank2 düzeltildi + 2 çakışan sinyal strict-hattıyla düşüldü;
> Jaguar hs_bus bozulmasına yol açan sanitize VAL_ regex bug'ı paylaşımlı pipeline'da düzeltildi.
> BogGyver/opendbc (Tier-1 #6) **ertelendi** — commaai fork'u; Lexus/Stellantis/Toyota varyantları
> generated üretim gerektiriyor, ayrı oturum konusu. Tier-2 ve bloklu listeler aşağıdaki gibidir.

## Tier 1 — Entegre edilebilir adaylar (lisans temiz, DBC formatında)

| # | Repo | Kategori | Lisans | İçerik | Pakete katkısı |
|---|------|----------|--------|--------|----------------|
| 1 | [projectgus/kona-ev-dbc](https://github.com/projectgus/kona-ev-dbc) | ev_bms / passenger | MIT | Hyundai Kona Electric: `pcan.dbc` (powertrain), `bcan.dbc` (body), `comp_can.dbc` (A/C), `ccan.dbc` — 4 DBC | E-GMP öncesi Hyundai EV platformu; pakette hiç Hyundai EV yok. Yazar "reverse-engineered, untrustworthy" uyarısı veriyor → doğrulama notuyla gelmeli. Yan repo [hyundai-kona-ev-can-logs](https://github.com/projectgus/hyundai-kona-ev-can-logs) golden-trace adayı da olabilir |
| 2 | [fsfarmscaper/jaguar-xf-x250-can](https://github.com/fsfarmscaper/jaguar-xf-x250-can) | passenger | **DBC'ler CC BY-SA 4.0**, scriptler MIT | Jaguar XF X250 (2008-2015): `ms_bus.dbc` + `hs_bus.dbc` (gösterge/kluster odaklı) | Pakette hiç Jaguar yok → yeni marka. Atıf zorunlu + share-alike |
| 3 | [dalathegreat/leaf_can_bus_messages](https://github.com/dalathegreat/leaf_can_bus_messages) | ev_bms | GPL-3.0 | Nissan LEAF: `EV-can_ZE0/AZE0/ZE1.dbc`, `CAR-can_AZE0.dbc`, `AV-CAN.dbc`, `QC-CAN_ALL.dbc` — 6 DBC, tüm nesiller (ZE0→ZE1 e+) | Pakette yalnız `nissan_leaf_2018_generated` var; bu set EV bus'ı + hızlı şarj + AV bus içeriyor. GPL viral lisans notu gerekir |
| 4 | [autti/abraham](https://github.com/autti/abraham) | passenger | MIT | `lincoln_mkz.dbc` — Lincoln MKZ / Ford Fusion crowdsourced decode | Ford/Lincoln kapsamını genişletir; openpilot ekosisteminin referans aracı |
| 5 | [joshwardell/model3dbc](https://github.com/joshwardell/model3dbc) | passenger / ev | MIT | `Model3CAN.dbc` — Tesla Model 3/Y (404 yıldız, topluluk referansı) | Paketteki comma kaynaklı `tesla_model3_*`'dan bağımsız decode; çapraz doğrulama değeri |
| 6 | [BogGyver/opendbc](https://github.com/BogGyver/opendbc) | passenger | MIT | commaai/opendbc fork'u (848 commit). Paket snapshot'ında olmayanlar: **Lexus** GS300h'17/IS'18/NX300/RX350/RX hybrid (PT generated), **Kia generic**, **Stellantis DASM**, Honda Accord'18 + Fit'18, Toyota Avalon/Camry hybrid/Corolla/Highlander/RAV4/Sienna, VW Golf Mk4, Tesla pre-19.16 CAN | opendbc'den gelen dosyaların paketle aynı lisans zinciri; generated olanlar fork'tan yeniden üretim gerektirir |
| 7 | [alan707/openOBD2](https://github.com/alan707/openOBD2) | diagnostics | MIT | `OBD2.dbc` — standart OBD-II PID'leri | Mevcut `OBD2.dbc` (nberlette) + `obd2_mode01_standard.dbc`'ye üçüncü çapraz kaynak; küçük |
| 8 | [qwec01/ARCFOX_dbc](https://github.com/qwec01/ARCFOX_dbc) | ev_bms | GPL-3.0 | ARCFOX (BAIC EV): `arcfox_EVBUS.dbc`, `arcfox_IBUS1/2.dbc`, `GB27830-2015.dbc` — gerçek BMS bus'u dahil | Yeni Çinli EV markası + ev_bms kategorisine doğrudan BMS bus'u. Not: GB18030 encoding dönüşümü gerekebilir |
| 9 | [open-vehicle-control-system/dbc](https://github.com/open-vehicle-control-system/dbc) | ev / passenger | MIT | Tesla iBooster Gen 2 fren aktüatörü DBC (`ibooster/`) | Küçük (4 commit) ama benzersiz aktüatör tanımı |

## Tier 2 — Entegrasyon öncesi teyit gerekli

| Repo | Konu |
|------|------|
| [BYDcar/opendbc-byd](https://github.com/BYDcar/opendbc-byd) | `byd_tang_phev_2015.dbc` — tek BYD DBC (Tang PHEV 2016). LICENSE dosyası var ama türü taramada teyit edilmedi; opendbc fork'u olduğu için MIT olması muhtemel. Teyitsiz entegre edilmez |
| [FarmLogs/pysobus](https://github.com/FarmLogs/pysobus) | ISOBUS decode kütüphanesi (DBC değil) — agriculture decode çapraz doğrulaması için; lisans teyidi gerekli |
| [blalor/ktm-can](https://github.com/blalor/ktm-can) | KTM motosiklet CAN parser (DBC değil, Python) — motorsiklet dikeyinin tek açık izi; lisans teyidi gerekli |

## Bloklu adaylar (DO-NOT-INTEGRATE listesine yazılması önerilenler)

| Repo | Sorun |
|------|-------|
| [Konik-ai/j1939_dbc](https://github.com/Konik-ai/j1939_dbc) | MIT etiketli ama **nberlette/canbus fork'u**; içeriğindeki `j1939.dbc` resmî SAE J1939 standardından türetilmiş — [issue #6](https://github.com/nberlette/canbus/issues/6) telif ihlali iddiası. Paket zaten nberlette'i yalnız BMW E39 + OBD2 için kullanıyor; J1939 tarafı yasak kalmalı |
| [uhi22/IoniqMotorCAN](https://github.com/uhi22/IoniqMotorCAN) | Lisans yok (`Traces/hyundai_Ioniq28Motor.dbc` telifli). İzin alınmadıkça kopyalanamaz |
| [icecube45/Dash_InfinitiG37](https://github.com/icecube45/Dash_InfinitiG37) | `InfinitiG37.dbc` lisanssız. İnfiniti/Nissan G-serisi kapsama boşluğu — izin istenmeye değer |
| [Trueffelwurm/Car-CAN-Message-DB](https://github.com/Trueffelwurm/Car-CAN-Message-DB) | Lisans yok + format zaten DBC değil (Markdown tablo; Opel Astra H) |

## Format-dönüşümü adayı (DBC değil, dönüştürülüp katkı sağlanabilir)

- **[OBDb](https://github.com/OBDb)** (obdb.community) — 740 araç repo'su, JSON `signalsets/v3/`
  formatı, **CC BY-SA 4.0**. Araç kapsamı opendbc'den çok daha geniş (Audi Q7, VW ID.4,
  Toyota Tundra, Land Rover Defender, Kia Ceed...). Ayrıca `SAEJ1979` standard-PID repo'su.
  DBC'ye dönüşüm aracı yazılırsa binek kapsamını köklü genişletir — ayrı bir proje konusu.

## Kategori boşluk analizi (tarama sonucu)

- **Marine/N2K**: Resmî DBC kapalı standart (NMEA satıyor); tek açık referans canboat
  (`pgns.json`). Paketin `n2k_canboat.dbc`'sinin güncel canboat master'dan yeniden üretilmesi
  (re-sync) dışında genişleme potansiyeli düşük.
- **Heavy duty/J1939**: Resmî tam set SAE'nin ücretli ürünü ([J1939DBC](https://saemobilus.sae.org/media/j1939-enhanced-dbc-j1939dbc_202603)).
  Açık tarafta canboat (pakette var) + CSS Electronics ücretli/kayıtlı set (pakette kayıtlı)
  dışında yeni kaynak çıkmadı. Üretici proprietary dosyaları (Cummins/Scania/...) toplulukta yok.
- **Motorsiklet**: Paketin hiç girmediği dikey. Hazır DBC yok; yalnız KTM parser'ı ve
  [awesome-automotive-can-id](https://github.com/iDoka/awesome-automotive-can-id)'deki
  BMW/Ducati/KTM RE notları var. Yeni kategori açılırsa sıfırdan RE gerektirir.
- **Çin EV**: NIO / XPeng / Zeekr için kamuya açık DBC **bulunamadı** (hiç RE edilmemiş durumda).
  ARCFOX + BYD Tang (yukarıda) mevcut tek bulgular.
- **opendbc upstream drift**: commaai/opendbc master'da statik DBC sayısı hâlâ 57; paketin
  statik kopyası güncel. Sapma yalnız `generator/` çıktılarında — paketteki 39 generated dosyanın
  yeniden üretilip üretilmeyeceği ayrıca karşılaştırılmalı.

## Entegrasyon öncesi kontrol listesi (sonraki oturum için)

1. Her repo için LICENSE dosyasını ham olarak indirip LICENSES.md tablosuna kaynak + lisans + telif satırı ekle (CC BY-SA / GPL olanlarda atıf ve share-alike notu zorunlu).
2. DBC dosyalarını `raw/<repo-adı>/` altına al; `catalog.json` + `manifest.json`'a SHA-256 ile işle.
3. cantools ile parse testi (paketin mevcut `tests/` akışına uyumlu) + GB18030/encoding kontrolü (ARCFOX).
4. Paket versiyonunu v3.1.0'a çıkar; CHANGELOG'a kaydet.

---

# Tur-2 Taraması (2026-09-02, devam)

İkinci tur: GitHub topic sayfaları (191 repo, yıldız sıralı), kapsanmayan markalar (Audi,
Mercedes, Renault), açık kaynak ECU'lar, treyler/otobüs standartları ve BogGyver fork
diff'i. Ana bulgu: **BogGyver fork'unda pakete eklenmeye hazır 28 committed MIT dosyası var.**

> **SONUÇ (aynı gün):** 28 dosya **Batch-4 olarak entegre edildi** → paket **v3.2.0**
> (181 DBC / 14.961 mesaj / 75.603 sinyal; passenger 120→148; Lexus yeni marka).
> `curate_batch4_sources.py` + `raw/opendbc-boggyver/`; tesla_can_pre1916'nın kesik
> `VAL_ 921 DAS_lssState` satırındaki sarkan değer düşürüldü (29 çakışan placeholder
> sinyal strict-hattıyla düşüldü, CHANGELOG'da). verify_pack temiz, pack pytest 38/38,
> ana proje DBC testleri 10/10, `data/dbc` hash 181/181 + strict 189/189.

## Entegrasyona hazır — BogGyver/opendbc (MIT, dosyalar repoda committed, generator gerekmez)

`data/dbc/passenger` ile diff: 121 DBC'nin 28'i pakette yok. Not: `generator/*` kaynakları
paketin `raw/opendbc` klonunda zaten var (out of scope).

**Statik (7):** `hyundai_kia_generic.dbc` (paketin 2015 ccan/mcan'ını generic'le tamamlar),
`stellantis_dasm.dbc` (yeni marka ailesi), `tesla_can_pre1916.dbc`, `vw_golf_mk4.dbc`,
`vw_mqb_2010.dbc` (mevcut vw_mqb'den farklı varyant), `chrysler_pacifica_2017_hybrid.dbc`,
`tesla_radar.dbc`

**Generated (21):** **Lexus ×6** — GS300h'17, IS'18, NX300'18, NX300h'18, RX350'16,
RX Hybrid'17 (paketin ilk Lexus'ları); **Honda ×6** — Accord'18, CR-V EX'17, CR-V
Executive'16, Fit EX'18, Fit Hybrid'18, Odyssey China'18; **Toyota ×9** — Avalon'17,
Camry Hybrid'18, Corolla'17, Highlander'17, Highlander Hybrid'18, Nodsu Hybrid, Prius'17,
RAV4'17, Sienna XLE'18

## Yeni keşifler (değerlendirme notları)

| Kaynak | Durum |
|--------|-------|
| [spot2000/Volkswagen-MEB-EV-CAN-parameters](https://github.com/spot2000/Volkswagen-MEB-EV-CAN-parameters) | MEB (ID.3/ID.4/Enyaq) UDS PID listesi (CSV, 47 yıldız) — teşhis katmanı için değerli ama **lisans YOK** → DO-NOT-INTEGRATE; yazardan izin istenmeye değer |
| [sunnypilot/opendbc-archive](https://github.com/sunnypilot/opendbc-archive) | Eski opendbc arşivi — pakete göre yeni içerik yok → atlandı |
| commaai/opendbc son sürümleri | Audi Q5 / Porsche Macan port'ları eklendi ama **yeni DBC dosyası yok** (vw_mlb/vw_mqb üzerinden fingerprint portu); pack statik seti master ile güncel |
| [ljames28/Renault-Zoe-PH2-ZE50-Canbus-LBC-Information](https://github.com/ljames28/Renault-Zoe-PH2-ZE50-Canbus-LBC-Information), [rand12345/Zoe-PH1-EV-CAN-data](https://github.com/rand12345/Zoe-PH1-EV-CAN-data) | Zoe LBC/batarya CAN log'ları — DBC değil; **Golden-Traces adayı** (Zoe boşluğunu kapatır) |
| [yeongrokgim/twizy-dbc-for-torque-pro](https://github.com/yeongrokgim/twizy-dbc-for-torque-pro) | DBC değil CSV + lisanssız → atlandı; temel referans dexterbg'nin Twizy tablosu (OVMS) |

## Boşluk teyitleri (Tur-2)

- **ISO 11992 (treyler) / FMS:** kamuya açık DBC yok; uygulama katmanı J1939 türevi —
  mevcut j1939_canboat.dbc + J1939DA duvarı notu geçerli.
- **rusEFI / Speeduino:** resmî DBC yok; CAN broadcast layout dokümante (RealDash CAN
  protokolü) — istenirse küçük bir "paket içi üretim" DBC yazılabilir (OEM proprietary
  üretimindeki desen gibi).
- **KCD/ARXML dönüşüm yolu:** araç-KCD koleksiyonu çıkmadı; gerektiğinde
  [canmatrix](https://github.com/ebroecker/canmatrix) (KCD/ARXML/DBF → DBC) +
  [julietkilo/kcd](https://github.com/julietkilo/kcd) format spesifikasyonu hazır.
- **Mercedes yeni nesil (W205/206):** kamuya açık DBC yok; e350 2010 pakette mevcut.
- **Motorsiklet:** arama altyapısı defalarca timeout → kesin sonuç yok; mevcut tek izler
  awesome-automotive-can-id motosiklet bölümü (BMW/Ducati/KTM RE notları) + blalor/ktm-can
  (lisans teyidi hâlâ beklemede).
