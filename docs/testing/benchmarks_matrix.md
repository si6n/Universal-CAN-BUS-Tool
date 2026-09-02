# Benchmark Vektörleri

Universal-CAN-BUS-Tool `MASTER_PLAN.md` Bölüm 18'deki benchmark vektör setinin
Golden-Traces arşivindeki **gerçek izlerle** eşlemesi. Her vektör tekrarlanabilir
şekilde `extract_benchmark_vectors.py` ile üretilir ve `expected/` altında golden
YAML ile doğrulanır.

## Üretim
```bash
python scripts/extract_benchmark_vectors.py [--force]
```

## Vektör Durum Tablosu

| # | Vektör | Durum | Kare | Süre | Kaynak |
|---|--------|-------|-----:|------|--------|
| 1 | j1939_dm1_single | ✅ | 500 | 166.8s | j1939-hcrl_benign_dataset.asc |
| 2 | j1939_dm1_bam_multiframe | ✅ | 11,140 | 1338.6s | j1939-hcrl_attack4.asc |
| 3 | j1939_cmdt_rts_cts | ✅ | 7,572 | 4290.4s | j1939-hcrl_benign_dataset.asc |
| 4 | j1939_address_claim_win | ✅ | 200 | 721.8s | kees.asc |
| 5 | j1939_address_claim_loss | ✅ | 14 | 67207.4s | 2014_KW_T270_cross_country_can_log.asc |
| 6 | j1939_dm11_clear_ack | ✅ | 300 | 74.7s | j1939-hcrl_benign_dataset.asc |
| 7 | n2k_engine_rapid | ✅ | 500 | 29.4s | maneuvers.asc |
| 8 | n2k_fast_packet_dynamic | ✅ | 500 | 27.5s | kees.asc |
| 9 | n2k_transmission_dynamic | ✅ | 652 | 325.4s | maneuvers.asc |
| 10 | n2k_fluid_level | ✅ | 200 | 21.0s | dirona-actisense-serial.asc |
| 11 | volvo_mid128_pid100 | ✅ | 500 | 497.0s | vspy_Bus Traffic DD15 post crash DDEC Reports and DDDL with time stamp Tennessee 2014 5-28-2014 1-36-06 pm_j1708.asc |
| 12 | volvo_evc_prop_a | ⚠️ no_source | - | - | yok (arşiv boşluğu) |
| 13 | uds_iso15765_flow_control | ✅ | 2,031 | 28.9s | vspy_Bus Traffic DD15 DDEC Reports from Tennessee 2014 5-28-2014 11-57-21 am.asc |
| 14 | uds_routine_compression | ✅ | 2 | 0.0s | vspy_Bus Traffic DD15 DDEC Reports from Tennessee 2014 5-28-2014 11-57-21 am.asc |
| 15 | canfd_64byte_high_load | ⚠️ no_source | - | - | yok (arşiv boşluğu) |
| 16 | road_correlated_signal | ✅ | 5,397 | 33.1s | correlated_signal_attack_1.asc |

## no_source Vektörler

Aşağıdaki vektörler için arşivde gerçek veri bulunmadığından vektör üretilmedi:

- **volvo_evc_prop_a**: no_source: Derin tarama (2026-08-31): 298 dosya üzerinde 'volvo' geçen hiçbir ham/çevrilmiş kayıt yok; tüm J1939 ağır vasıta verisi Cummins/Detroit Diesel (KW T270, Cascadia DD15).
- **canfd_64byte_high_load**: no_source: Derin tarama (2026-08-31): her iki CAN-FD zip'i ve 3 dönüştürülmüş ASC (Flooding/Fuzzing/Malfunction) tekrar tarandı; maks DLC 13 (32B), DLC 14 (48B)/DLC 15 (64B) kare yok.

Bu vektörler sentetik olarak üretilmedi (uydurma veri yasağı).
Arşive yeni gerçek kayıt eklendiğinde vektör tanımı kolayca tamamlanabilir.
