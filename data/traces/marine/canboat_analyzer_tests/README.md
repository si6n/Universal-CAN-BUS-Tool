# canboat Analyzer Regression Tests (v8.1.0)

canboat'ın resmi golden test corpus'u: `analyzer/tests/` dizininden
(76 dosya, Apache-2.0, © canboat authors).

## Yapı

Her test üçlüden oluşur:

- `*.in` — girdi frame'leri (PLAIN/FAST/actisense formatları)
- `*.out` — analyzer'ın beklenen insan-okur çıktısı (alan alan decode edilmiş)
- `*.err` — beklenen stderr çıktısı (çoğunlukla boş)

## Kapsam

| Test | Konu |
|---|---|
| pgn-test | 60+ PGN'lik tam liste, null-olmayan alanlarla |
| pgn-test-json / -nv / -debug | JSON çıktı varyantları |
| iso-tp-test / -large-payload / -preassembled | ISO-TP (BAM) yeniden birleştirme |
| j1939-pgn-test | J1939 PGN decode |
| pgn-126208-request-130817 | Group Function request akışı |
| pgn-126983-nv, pgn-60928-nv | Not-verifiable alan varyantları |
| pgn-126998-lau-ff | Laurel-alignment UTF-8 fast packet |
| pgn-130823-directory / -truncated | Veri dizini + kesik mesaj |
| pgn-65379-test | Lowrance proprietary |
| pgn-garmin-autopilot | Garmin pilot proprietary |
| pgn-string-encoding | ASCII/LAU/UTF-16 string kodlama |
| actisense-format | Actisense metin formatı |
| dms-format, mixed-format | Derece-dakika-saniye, karışık |
| invalid-pgn-test | Geçersiz PGN davranışı |
| recombine-frames | Fast packet frame birleştirme |
| short-frame / short-reserved | Eksik/rezerve alan mesajları |
| switch-multi-to-one-line | Çok satır→tek satır birleştirme |

## Kullanım

Bunlar decoder'ımız için **bağımsız doğrulama vektörleri**dir: `.in`
frame'lerini DbcSignalDecoder/Nmea2000PgnDecoder'dan geçirip `.out`
alan değerleriyle karşılaştırmak, PGN decode matematiğinin canboat
ile birebir aynı olduğunu kanıtlar.
