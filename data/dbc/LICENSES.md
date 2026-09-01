# LICENSES.md — DBC-Knowledge-Pack Atıf ve Lisans Zinciri

Bu paket **erişim lisansı vermez**; yalnızca kamuya açık kaynakların lisanslarını
korur. Entegrasyon sırasında bu dosya `data/dbc/` yanına kopyalanmalıdır.

## Kabul edilen kaynaklar ve lisansları

| Kaynak | Lisans | Telif | Kullanım | Dosyalar |
|---|---|---|---|---|
| canboat/canboat | Apache-2.0 | © canboat authors | J1939 + N2K PGN YAML → DBC dönüşümü | `curated/heavy_duty/j1939_canboat.dbc`, `curated/marine/n2k_canboat.dbc`, `curated/heavy_duty/j1939_ccvs1_extra.dbc` |
| commaai/opendbc | MIT | © comma.ai | 57 statik + 39 generator-çıktısı binek DBC | `curated/passenger/*` (opendbc kaynaklı tümü) |
| chris-youngblut-solutions/opendbc-ag | MIT | © Chris Youngblut Solutions | ISO 11783/VDMA/ag-J1939 DBC (J1939 ID'ye çevrildi) | `curated/agriculture/isobus_vdma.dbc`, `j1939_isobus_ag.dbc`, `j1939_isobus_vdma_all.dbc` |
| Open-Agriculture/AgIsoStack-plus-plus | MIT | © Open-Agriculture | PGN sabitleri — doğrulama referansı (dağıtım yok) | — |
| ISOBUS Data Dictionary (isobus.net, AEF/ISO 11783-11 ODB) | Ücretsiz kamuya açık export (telif: AEF/ISO; site kullanım koşulları) | AEF | `SPNs and PGNs.csv` → `curated/isobus_dd11783.dbc` (102 msg / 1341 sig) | `curated/agriculture/isobus_dd11783.dbc` |
| nberlette/canbus + nberlette/bmw-dbc | MIT | © 2021–2022 Nicholas Berlette | BMW E39 DBC + OBD-II multiplexed PID referansı | `curated/passenger/bmw-e39.dbc`, `curated/diagnostics/OBD2.dbc` |
| berumiya/CAN_DBC_6thGenMazda | **CC-BY-4.0** | © berumiya | Mazda 6th-gen HSCAN/MSCAN — **atıf zorunlu**: "Contains data from berumiya/CAN_DBC_6thGenMazda (CC-BY-4.0)" | `curated/passenger/MX5ND_6thGenMazda_HSCAN.dbc`, `MX5ND_6thGenMazda_MSCAN.dbc` |
| shemps/byd-atto3-openpilot-port | MIT | © shemps | BYD Atto3 araç + CAN-FD radar DBC | `curated/passenger/byd_atto3.dbc`, `byd_radar_fd.dbc`, `curated/ev_bms/byd_atto3.dbc` |
| juanmaus/geely-geometry-c-dbc | MIT | © geely-geometry-c-dbc contributors | Geely Geometry C IF-CAN DBC | `curated/passenger/geely_geometry_c_if_can.dbc` |
| andrewdodd/decoda | MIT | © 2022 Andrew Dodd | J1939DA/ISOBUS DD → JSON dönüştürücü — yalnızca **referans/altyapı** incelemesi, kod dağıtımı yok | — |
| SAE J1939-71 yaygın yerleşim (CCVS1 SPN 84) | Standart (üç bağımsız kaynakla teyitli yerleşim) | SAE | `raw/pgn-extras/065265-ccvs1.yaml` | `curated/heavy_duty/j1939_ccvs1_extra.dbc` |
| Üretici-özel J1939 proprietary (Cummins/Scania/Volvo) | Paket içi üretim (projenin OEM decoder tanımlarından) | — | — | `curated/heavy_duty/*_j1939_proprietary.dbc` |

## DO-NOT-INTEGRATE — lisanssız / riskli dosyalar

Bu dosyalar `raw/` altında **araştırma kaydı** olarak durur; lisans durumu
çözülene kadar `curated/`a veya `data/dbc/`ye **kopyalanamaz**:

| Dosya | Kaynak | Sorun |
|---|---|---|
| `raw/vehicle-dbc/renault-mascott-2009.dbc` | robin-thoni/dbc | Lisans belirtilmemiş |
| `dragz/egmpdbc` (içerik indirilmedi) | Hyundai/Kia E-GMP Ioniq5 | Lisans yok |
| `Sterlingarcher2525/ioniq5-can` (içerik indirilmedi) | Ioniq5 RE notları | Lisans yok |
| `krsche/renault-megane-3-rs-can-dbc` (içerik indirilmedi) | Megane 3 RS | Lisans yok |
| `jackm/j1939decode` (içerik indirilmedi) | J1939 C lib | Lisans yok |

## Ücretli / kayıtlı alternatifler (kayıt amaçlı)

- CSS Electronics J1939/ISOBUS/N2K DBC paketleri — ücretli; ücretsiz setimiz
  aynı PGN'leri açık kaynaklarla karşılıyor.
- Heavy-Duty Data Pack (CSS) — e-posta kaydı şartlı ücretsiz; MF4 format.

## Sorumluluk reddi

DBC içerikleri topluluk tarafından tersine mühendislikle üretilmiştir; araç
üreticilerinin resmî verisi değildir. Güvenlik-ilişkili (ASIL) kullanımda
yalnızca referans olarak değerlendirilmelidir.
