---
title: "ADR 0002: TxSafetyGateway As Single Choke-Point for Transmissions"
status: ACCEPTED
date: 2026-08-20
tags:
  - adr
  - safety
  - tx-gateway
  - e-stop
---

# ADR 0002: TxSafetyGateway As Single Choke-Point

## Durum
**KABUL EDİLDİ (ACCEPTED)**

## Bağlam
CAN hattına yanlış veya kontrolsüz mesaj gönderilmesi araçta istenmeyen frenleme, gaz verme veya ECU resetleme gibi güvenlik felaketlerine yol açabilir (ISO 26262 ASIL-D).

## Karar
Hiçbir protokol, engine veya UI bileşeni donanım katmanına (`AbstractBus.send`) doğrudan erişemez. Tüm iletimler `TxPort` arayüzünü uygulayan `TxSafetyGateway` nesnesi üzerinden yapılmak zorundadır.
1. E-Stop durumu
2. Watchdog kira süresi
3. DLC ve çerçeve doğrulaması
4. Allowlist/Denylist filtrelemesi
5. Oran sınırlama (Token Bucket)
6. AUTOSAR E2E CRC/Counter mühürlemesi

## Sonuçlar
- **Artılar:** İletim güvenliği tek merkezden denetlenir; testlerde gateway mock'lanarak tüm güvenlik ihlalleri deterministik simüle edilir.
- **Eksiler:** İletim başına ~2-5 mikrosaniye hesaplama ek yükü (LUT ve bitwise operasyonlar ile minimize edildi).
