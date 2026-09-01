---
title: "ADR 0001: Hexagonal (Ports & Adapters) Architecture"
status: ACCEPTED
date: 2026-08-15
tags:
  - adr
  - architecture
  - core
  - hal
---

# ADR 0001: Hexagonal (Ports & Adapters) Architecture

## Durum
**KABUL EDİLDİ (ACCEPTED)**

## Bağlam
Universal CAN-Bus Tool projesi, hem hafif araç (OBD-II), hem ağır vasıta (J1939), hem de endüstriyel/denizcilik sistemlerinde çalışabilen, çoklu donanım adaptörlerine (SocketCAN, Vector, PCAN, Kvaser, RP1210) bağlanabilen ve ASIL-B/D fonksiyonel güvenlik gereksinimlerini karşılayan bir yapıda olmalıdır.

## Karar
Sistem **Hexagonal Architecture (Ports & Adapters)** prensiplerine göre tasarlandı:
- **Core (`src/core/`):** Tamamen harici kütüphane bağımsız, immutable domain modelleri (`CanFrame`) ve port sözleşmeleri (`TxPort`, `RxSubscription`).
- **HAL (`src/hal/`):** Donanım bağımlılıklarını izole eden adaptörler (`PythonCanBus`, `RP1210Client`, `VirtualBus`).
- **Safety (`src/safety/`):** Donanıma yazma yapan her portun önüne yerleştirilen zorunlu güvenlik kapısı (`TxSafetyGateway`).
- **Protocols & Engine:** Domain modelleri üzerinden haberleşen bağımsız işleme katmanları.

## Sonuçlar
- **Artılar:** Donanım adaptörleri (örn. Nexiq RP1210) gerçek cihaz olmadan `VirtualBus` ile %100 mock'lanıp birim testten geçirilebilir.
- **Eksiler:** Port ve adapter arayüzleri ekstra abstraction katmanı gerektirir.
