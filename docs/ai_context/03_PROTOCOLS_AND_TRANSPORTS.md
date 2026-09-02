---
title: "AI Context: Protocols & Transport Stacks"
tags:
  - ai-context
  - protocols
  - j1939
  - uds
  - obd2
  - isotp
updated: 2026-09-01
---

# Protocols & Transport Stacks Context Card

Bu kart, projedeki CAN iletişim protokollerinin ve çok paketli (multi-packet) taşıma katmanlarının çalışma kurallarını özetler.

## 1. SAE J1939 Ağır Vasıta Protokolü

- **29-bit CAN ID Yapısı:**
  - Priority (3 bit)
  - Parameter Group Number - PGN (18 bit): DP (1 bit), EDP (1 bit), PF (8 bit), PS (8 bit)
  - Source Address - SA (8 bit)
- **Transport Protocol (SAE J1939-21):**
  - **BAM (Broadcast Announce Message):** PGN 60416 (TP.CM_BAM) ile başlar, PGN 60160 (TP.DT) ile paketler 50-200ms aralıklarla tüm bus'a yayınlanır.
  - **RTS/CTS (Point-to-Point):** PGN 60416 TP.CM_RTS -> TP.CM_CTS -> TP.DT -> TP.EndofMsgAck el sıkışmalı akış kontrolü.
- **Diagnostic Messages (SAE J1939-73):**
  - `DM1` (Active DTCs - PGN 65226)
  - `DM2` (Previously Active DTCs - PGN 65227)
  - `DM3`..`DM11` (DTC Clear, Freeze Frames vb.)
- **Address Claiming (SAE J1939-81):**
  - PGN 60928 (Address Claim) ile 64-bit NAME önceliğine göre adres çakışma çözümü.

## 2. ISO 14229 UDS (Unified Diagnostic Services)

- **Temel Servisler:**
  - `0x10`: Diagnostic Session Control (Default, Extended, Programming)
  - `0x22`: Read Data By Identifier (DID)
  - `0x2E`: Write Data By Identifier (DID)
  - `0x19`: Read DTC Information
  - `0x27`: Security Access (Seed & Key)
  - `0x3E`: Tester Present (Zero Subfunction / Keep-Alive)
- **Negative Response Code (NRC):**
  - Format: `[0x7F, RequestSID, NRC_Byte]` (örn. `0x78` ResponsePending, `0x22` ConditionsNotCorrect, `0x35` InvalidKey).

## 3. ISO 15765-2 DoCAN (ISO-TP)

UDS ve diagnostik mesajlarının 8 bayttan uzun olması durumunda kullanılan taşıma katmanı:
- **Single Frame (SF):** `PCI Byte 0x0_` + Veri (1-7 bayt).
- **First Frame (FF):** `PCI Bytes 0x1_ 0x__` (12-bit Toplam Uzunluk) + Veri başlangıcı.
- **Flow Control (FC):** `PCI Bytes 0x3_ 0xFS 0xBS 0xSTmin` (FS: ClearToSend=0, Wait=1, Overflow=2; BS: Block Size; STmin: Separation Time).
- **Consecutive Frame (CF):** `PCI Bytes 0x2_ (Sn: 0..F)` + Veri parçaları.

## 4. SAE J1979 OBD-II (Mode 01 - Current Data)

- 11-bit Standart ID (`0x7DF` Broadcast, `0x7E0..0x7E7` Yanıtlar).
- Standart PID veritabanı (`0x00..0xFF`): Motor devri (PID 0x0C), Araç hızı (PID 0x0D), Soğutma sıvısı sıcaklığı (PID 0x05) vb.
- Fiziksel değer dönüştürücü: Ham baytları formüllerle ölçekleyip mühendislik birimlerine (`RPM`, `km/h`, `°C`, `kPa`, `%`) dönüştürür.
