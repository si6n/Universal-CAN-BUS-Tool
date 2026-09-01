---
title: "OEM Decoder: {{OEM_NAME}}"
tags:
  - oem
  - j1939
  - decoder
  - spec
---

# OEM Decoder: {{OEM_NAME}}

## 1. Genel Bilgiler
- **OEM Adı:** {{OEM_NAME}}
- **Protokol:** SAE J1939 (Proprietary A `0xEF00` / Proprietary B `0xFF00..0xFFFF`)
- **Modül Dosyası:** `src/protocols/j1939/oem/{{oem_file}}.py`
- **Test Dosyası:** `tests/unit/protocols/test_{{oem_file}}.py`

## 2. PGN / SPN Tablosu

| PGN (Hex / Dec) | SPN | Sinyal Adı | Bit Başlangıç | Bit Uzunluk | Çözünürlük (Gain) | Ofset | Birim | Min / Max |
|---|---|---|---|---|---|---|---|---|
| `0xEF00` | 1001 | DPF Soot Load | 0 | 16 | 0.1 | 0 | g | 0..1000 |

## 3. Akış ve Güvenlik Kuralları
- Eksik veya bozuk frame durumunda `SignalQuality.INVALID` dönülmeli.
- Multi-packet BAM/RTS-CTS desteği için `ReassemblyPipeline` ile entegre çalışmalı.
