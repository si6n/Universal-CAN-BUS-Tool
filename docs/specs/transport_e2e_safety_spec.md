# Universal CAN-Bus Tool: Transport Protocols & E2E Safety Specification Catalog (R3 & R4)

**Document Version**: 1.0.0  
**Author**: `survey_spec_miner_3`  
**Classification**: Engineering & Protocol Specification  
**Status**: Authoritative Reference for Implementation & Conformance  
**Targets**: SAE J1939-21, ISO 15765-2:2016 (DoCAN), AUTOSAR E2E Profile 1 & 2, SAE J1850 CRC-8, OEM Profiles (Toyota, VAG MQB, Volvo)

---

## Executive Summary & Scope

This specification defines the complete mathematical, architectural, and protocol standards for:
- **Requirement 3 (R3)**: Multi-Packet Transport & Auto-Reassembly Pipeline covering SAE J1939 Transport Protocol (BAM & RTS/CTS CMDT) and ISO 15765-2:2016 DoCAN (ISO-TP) with dynamic session tracking, memory bounding, and zero-copy handover to `DbcSignalDecoder`.
- **Requirement 4 (R4)**: Checksum & Rolling Counter (E2E Safety) Validation Engine covering AUTOSAR E2E Profile 1 (0x1D), AUTOSAR E2E Profile 2 (0x2F), SAE J1850 CRC-8, and OEM-specific safety algorithms (Toyota additive checksum + counter, VAG MQB AUTOSAR CRC-8 + counter, Volvo ones-complement sum + counter) for bidirectional Rx verification and Tx packaging.

---

# Table of Contents
1. [Requirement 3: SAE J1939-21 Transport Protocol (BAM & CMDT)](#1-requirement-3-sae-j1939-21-transport-protocol)
2. [Requirement 3: ISO 15765-2:2016 DoCAN (ISO-TP)](#2-requirement-3-iso-15765-22016-docan-iso-tp)
3. [Requirement 3: Multi-Packet Pipeline & DBC Decoder Handover](#3-requirement-3-multi-packet-pipeline--dbc-decoder-handover)
4. [Requirement 4: Mathematical CRC Foundations & Lookup Tables](#4-requirement-4-mathematical-crc-foundations--lookup-tables)
5. [Requirement 4: AUTOSAR E2E Profile 1 Specification](#5-requirement-4-autosar-e2e-profile-1-specification)
6. [Requirement 4: AUTOSAR E2E Profile 2 Specification](#6-requirement-4-autosar-e2e-profile-2-specification)
7. [Requirement 4: SAE J1850 & OEM Safety Profiles (Toyota, VAG MQB, Volvo)](#7-requirement-4-sae-j1850--oem-safety-profiles)
8. [Requirement 4: Rx Validation & Tx Packaging Architecture](#8-requirement-4-rx-validation--tx-packaging-architecture)
9. [Authoritative Test Vectors & Empirical Matrices](#9-authoritative-test-vectors--empirical-matrices)
10. [Edge Cases, Error Handling & Security Matrix](#10-edge-cases-error-handling--security-matrix)
11. [Discovered Features & Interface Catalog](#11-discovered-features--interface-catalog)

---

# 1. Requirement 3: SAE J1939-21 Transport Protocol

The SAE J1939-21 specification details transport layer mechanisms for packaging and transmitting messages with payload lengths exceeding 8 bytes (from 9 up to 1785 bytes).

## 1.1 CAN Identifier Structure & Parameter Group Numbers

All J1939 TP frames utilize 29-bit extended CAN arbitration IDs:
```
Bit: 28 27 26 | 25 | 24 | 23 ... 16 | 15 ... 8 | 7 ... 0
     Priority | R  | DP | PDU Format | PDU Spec | Source Addr
```

Two designated Parameter Group Numbers (PGNs) govern the transport protocol:
1. **Connection Management (TP.CM)**: PGN `60416` (`0x00EC00`), $PF = 236$ (`0xEC`), $PS = \text{Destination Address}$ ($DA$).
   - Standard Priority: `6` or `7` $\rightarrow$ CAN ID: `0x18EC<DA><SA>`
2. **Data Transfer (TP.DT)**: PGN `60160` (`0x00EB00`), $PF = 235$ (`0xEB`), $PS = \text{Destination Address}$ ($DA$).
   - Standard Priority: `6` or `7` $\rightarrow$ CAN ID: `0x18EB<DA><SA>`

---

## 1.2 Protocol Control Bytes & Message Formats

### 1.2.1 Broadcast Announce Message (BAM)
Used to broadcast multi-packet data to all nodes on the network ($DA = 255 / 0xFF$). BAM operates unacknowledged.

**TP.CM_BAM Packet Structure** (Arbitration ID: `0x18ECFF<SA>`):
| Byte Index | Field Description | Value / Encoding |
|:---|:---|:---|
| `Byte 0` | Control Byte | `0x20` (32 decimal = TP.CM_BAM) |
| `Byte 1..2` | Total Message Size ($L$) | $1 \le L \le 1785$ bytes, 16-bit Little-Endian |
| `Byte 3` | Total Packet Count ($N$) | $N = \lceil L / 7 \rceil = (L + 6) // 7 \in [1, 255]$ |
| `Byte 4` | Reserved | `0xFF` |
| `Byte 5..7` | Target PGN | 24-bit Little-Endian (`PGN_Low, PGN_Mid, PGN_High`) |

**TP.DT Packet Structure** (Arbitration ID: `0x18EBFF<SA>`):
| Byte Index | Field Description | Value / Encoding |
|:---|:---|:---|
| `Byte 0` | Sequence Number ($S$) | $1 \le S \le N$, strictly incrementing from 1 to $N$ |
| `Byte 1..7` | Data Payload Chunk | Up to 7 bytes of data chunk $[(S-1)\times 7 : S\times 7]$. Unused bytes in packet $N$ MUST be padded with `0xFF`. |

### 1.2.2 Connection Mode Data Transfer (CMDT RTS/CTS)
Used for reliable point-to-point transfers between a specific Source Address ($SA$) and Destination Address ($DA \ne 255$).

**TP.CM Control Byte Formats**:

1. **Request To Send (TP.CM_RTS, Control Byte `0x10`)** — Transmitter $\rightarrow$ Receiver (`0x18EC<DA><SA>`):
   - `Byte 0`: `0x10` (16 decimal)
   - `Byte 1..2`: Total message size in bytes ($L \in [1, 1785]$, Little-Endian)
   - `Byte 3`: Total number of packets ($N = (L + 6) // 7 \in [1, 255]$)
   - `Byte 4`: Maximum packets that can be sent in response to CTS (`0xFF` or burst limit)
   - `Byte 5..7`: Target PGN (24-bit Little-Endian)

2. **Clear To Send (TP.CM_CTS, Control Byte `0x11`)** — Receiver $\rightarrow$ Transmitter (`0x18EC<SA><DA>`):
   - `Byte 0`: `0x11` (17 decimal)
   - `Byte 1`: Number of packets receiver is ready to receive ($M \in [1, N]$, or `0x00` for Hold/Wait)
   - `Byte 2`: Next sequence number expected ($S_{next} \in [1, N]$)
   - `Byte 3..4`: Reserved (`0xFF 0xFF`)
   - `Byte 5..7`: Target PGN (24-bit Little-Endian)

3. **End of Message Acknowledgment (TP.CM_EndOfMsgACK, Control Byte `0x13`)** — Receiver $\rightarrow$ Transmitter (`0x18EC<SA><DA>`):
   - `Byte 0`: `0x13` (19 decimal)
   - `Byte 1..2`: Total message size in bytes ($L$, Little-Endian)
   - `Byte 3`: Total number of packets received ($N$)
   - `Byte 4`: Reserved (`0xFF`)
   - `Byte 5..7`: Target PGN (24-bit Little-Endian)

4. **Connection Abort (TP.Conn_Abort, Control Byte `0xFF`)** — Either Node $\rightarrow$ Peer (`0x18EC<Peer><Self>`):
   - `Byte 0`: `0xFF` (255 decimal)
   - `Byte 1`: Connection Abort Reason Code:
     - `0x01`: `ABORT_REASON_SEQUENCE_ERROR` (Unexpected sequence number or already connected)
     - `0x02`: `ABORT_REASON_SESSION_COLLISION` (Resource limit reached or session collision on active SA/DA)
     - `0x03`: `ABORT_REASON_TIMEOUT` (T1, T2, T3, or T4 timer expired)
     - `0x04`: `ABORT_REASON_UNEXPECTED_CONTROL` (Unexpected CTS received or invalid control byte)
     - `0x05`: `ABORT_REASON_MAX_RETRANSMIT` (Maximum retransmission count exceeded)
   - `Byte 2..4`: Reserved (`0xFF 0xFF 0xFF`)
   - `Byte 5..7`: Target PGN (24-bit Little-Endian)

---

## 1.3 Timing Parameters & State Machines

### 1.3.1 Standard J1939-21 Timers
```
+-------------------------------------------------------------------------------+
| Timer | Description                               | Nominal | Min    | Max    |
|-------|-------------------------------------------|---------|--------|--------|
| Tr    | Response Time (BAM packet interval / CTS) | 50-200ms| 50 ms  | 200 ms |
| Th    | Holding Time (CTS Hold duration)          | 500 ms  | 0 ms   | 500 ms |
| T1    | Time between packets (TP.DT timeout)      | 750 ms  | --     | 750 ms |
| T2    | Time to respond with CTS after RTS        | 1250 ms | --     | 1250 ms|
| T3    | Time to respond with EndOfMsgACK          | 1250 ms | --     | 1250 ms|
| T4    | Maximum connection hold time              | 1050 ms | --     | 1050 ms|
+-------------------------------------------------------------------------------+
```

### 1.3.2 Receiver State Machine Diagram
```
                     +----------------------+
                     |         IDLE         |
                     +----------------------+
                       /                  \
   Rx TP.CM_BAM       /                    \  Rx TP.CM_RTS (DA == MyAddr)
  (DA == 255)        /                      \
                    v                        v
          +-------------------+    Send CTS  +-------------------+
          |  BAM_REASSEMBLY   |  <---------  |  CMDT_REASSEMBLY  |
          +-------------------+              +-------------------+
            |     |        |                    |     |        |
    Seq OK  |     | Seq    | T1 > 750ms Seq OK  |     | Seq    | T1 > 750ms
  (S == S+1)|     | Error  | Timeout  (S == S+1)|     | Error  | Timeout
            v     v        v                    v     v        v
         [Append] [Silent] [Silent]          [Append] [Send    [Send
         [Data  ] [Drop  ] [Drop  ]          [Data  ]  Abort    Abort
            |                                   |      Reason 1 Reason 3]
            | S == N                            | S == N
            v                                   v
   +--------------------+             +--------------------+
   | EMIT COMPLETED MSG |             | SEND EndOfMsgACK   |
   +--------------------+             +--------------------+
            |                                   |
            v                                   v
   +--------------------+             +--------------------+
   |   CLOSE SESSION    |             | EMIT COMPLETED MSG |
   +--------------------+             +--------------------+
```

---

# 2. Requirement 3: ISO 15765-2:2016 DoCAN (ISO-TP)

ISO 15765-2 governs network layer segmentation and flow control for diagnostic communication (UDS ISO 14229 / OBD-II) across Classic CAN and CAN FD.

## 2.1 Addressing Modes

1. **Standard 11-bit Normal Addressing**:
   - 11-bit CAN ID designates transmitter/receiver (e.g., Request `0x7E0`, Response `0x7E8`).
   - N_PCI byte starts at index 0 of frame payload.
2. **Extended 29-bit Normal Fixed Addressing (ISO 15765-2 §9.2.3)**:
   - Physical Request: `0x18DA<Target Addr><Source Addr>`
   - Functional Broadcast: `0x18DB33<Source Addr>` (`0x33` is standard functional broadcast target)
   - Physical Response: `0x18DA<Source Addr><Target Addr>`
3. **Extended Addressing (8-bit N_TA in Byte 0)**:
   - `Byte 0` = Target Address ($N\_TA$). `Byte 1` = N_PCI byte.
4. **Mixed Addressing (8-bit N_AE in Byte 0)**:
   - `Byte 0` = Address Extension ($N\_AE$). `Byte 1` = N_PCI byte.

---

## 2.2 Network Protocol Control Information (N_PCI) Formats

| N_PCI Type | Type Code (High Nibble) | Low Nibble / Parameters | Payload Capacity |
|:---|:---|:---|:---|
| **Single Frame (SF)** | `0x0` | `SF_DL (1..7)` on Classic CAN; `0x0` on CAN FD (with `SF_DL` in byte 1) | Classic: $\le 7$ B; CAN FD: $\le 62$ B |
| **First Frame (FF)** | `0x1` | `FF_DL High Nibble` (Standard 12-bit) or `0x0` (Extended 32-bit) | Standard: $8 \le L \le 4095$ B; Extended: $L > 4095$ B |
| **Consecutive Frame (CF)** | `0x2` | Sequence Number `SN (0..15)` | Classic: 7 B/frame; CAN FD: 63 B/frame |
| **Flow Control (FC)** | `0x3` | FlowStatus `FS (0=CTS, 1=WAIT, 2=OVFLW)` | Controls pacing via `BS` and `STmin` |

### 2.2.1 Detailed Byte Layouts

1. **Single Frame (Classic CAN)**:
   - `Byte 0`: `(0x0 << 4) | (SF_DL & 0x0F)` (where $1 \le \text{SF\_DL} \le 7$). *Reject $\text{SF\_DL} = 0$.*
   - `Bytes 1..SF_DL`: Diagnostic Payload.
   - `Bytes (SF_DL + 1)..7`: Padding byte (`0xCC` / `0xAA` / `0x00`).

2. **Single Frame (CAN FD Extended SF)**:
   - `Byte 0`: `0x00`
   - `Byte 1`: `SF_DL` ($1 \le \text{SF\_DL} \le 62$)
   - `Bytes 2..(2 + SF_DL)`: Diagnostic Payload.
   - Trailing: Padded to nearest discrete CAN FD DLC (8, 12, 16, 20, 24, 32, 48, 64).

3. **Standard 12-bit First Frame ($8 \le \text{Total Bytes} \le 4095$)**:
   - `Byte 0`: `(0x1 << 4) | ((Total_Bytes >> 8) & 0x0F)`
   - `Byte 1`: `Total_Bytes & 0xFF`
   - `Bytes 2..7` (Classic CAN) or `Bytes 2..63` (CAN FD): First chunk of data (6 bytes or 62 bytes).

4. **Extended 32-bit First Frame ($\text{Total Bytes} > 4095$)**:
   - `Byte 0`: `0x10`
   - `Byte 1`: `0x00`
   - `Bytes 2..5`: 32-bit Big-Endian payload length ($L > 4095$)
   - `Bytes 6..7` (Classic CAN) or `Bytes 6..63` (CAN FD): First chunk of data (2 bytes or 58 bytes).

5. **Consecutive Frame (CF)**:
   - `Byte 0`: `(0x2 << 4) | (SN & 0x0F)`
   - Sequence number sequence: $SN = 1, 2, 3, \dots, 14, 15, 0, 1, \dots$
   - `Bytes 1..7` (Classic) or `Bytes 1..63` (CAN FD): Payload chunk.

6. **Flow Control Frame (FC)**:
   - `Byte 0`: `(0x3 << 4) | (FS & 0x0F)`
     - `FS = 0` (`FS_CTS`): Continue To Send.
     - `FS = 1` (`FS_WAIT`): Wait (Sender holds transmission; max consecutive WAIT count $WFT_{max} = 16$).
     - `FS = 2` (`FS_OVERFLOW`): Buffer Overflow / Memory allocation failed at receiver.
   - `Byte 1`: `BlockSize` ($BS$): $0 = \text{Send all remaining frames}$; $1..255 = \text{Send } BS \text{ CFs then wait for FC}$.
   - `Byte 2`: `STmin` (Separation Time minimum):
     - `0x00 - 0x7F`: $0 \dots 127$ ms
     - `0xF1 - 0xF9`: $100 \dots 900$ µs ($0.1 \dots 0.9$ ms)
     - `0x80 - 0xF0` and `0xFA - 0xFF`: Reserved (clamped to 127.0 ms).
   - `Bytes 3..7`: Padded with `0xCC`.

---

## 2.3 Network Layer Timing Limits (ISO 15765-2 Table 18/21)

```
+-------------------------------------------------------------------------------+
| Parameter | Description                               | Timeout Limit         |
|-----------|-------------------------------------------|-----------------------|
| N_As      | CAN frame transmission time (Sender)      | 1000 ms               |
| N_Ar      | CAN frame transmission time (Receiver)    | 1000 ms               |
| N_Bs      | Time between FF and reception of FC (Tx)  | 1000 ms               |
| N_Br      | Receiver processing time before sending FC| < 900 ms (Performance)|
| N_Cs      | Sender spacing between FC/CF and next CF  | Governed by STmin     |
| N_Cr      | Time between Consecutive Frames (Rx)      | 1000 ms               |
+-------------------------------------------------------------------------------+
```

---

# 3. Requirement 3: Multi-Packet Pipeline & DBC Decoder Handover

## 3.1 Architecture Overview

```
                      +-----------------------------+
                      |       Raw CAN Ingestion     |
                      |   (CanFrame from HAL / Bus) |
                      +-----------------------------+
                                     |
                                     v
                      +-----------------------------+
                      | MultiPacketReassemblyEngine |
                      +-----------------------------+
                       /              |             \
                      /               |              \
           [J1939 TP.CM / DT]   [ISO-TP SF/FF/CF]   [Single-Frame DBC]
                     |                |                      |
                     v                v                      |
           +-----------------+  +-----------------+          |
           | J1939 Reassembler| | ISO-TP Reassembler|         |
           +-----------------+  +-----------------+          |
                     \                /                      |
           Completed  \              / Completed             |
           J1939 Msg   v            v  ISO-TP Msg            |
                      +-----------------------------+        |
                      |   Synthetic Frame Generator |        |
                      | (ArbitrationID = PGN << 8)  |        |
                      +-----------------------------+        |
                                     |                       |
                                     +-----------------------+
                                     |
                                     v
                      +-----------------------------+
                      |      DbcSignalDecoder       |
                      |  - SignalStatus: VALID      |
                      |  - NOT_AVAILABLE (0xFF..)   |
                      |  - ERROR (0xFE..)           |
                      |  - Physical Unit Scaling    |
                      +-----------------------------+
```

## 3.2 Handover Logic & Signal Validity
When a J1939 multi-packet message (e.g. DM1 Active DTCs PGN `65226`, DM2 Previously Active DTCs PGN `65227`, Vehicle Identification VIN PGN `65259`, Component ID PGN `65249`) is completely reassembled:
1. Reconstruct 29-bit CAN ID:
   $$\text{ArbitrationID} = 0x18000000 \mid ((\text{PGN} \& 0x3FFFF) \ll 8) \mid (\text{SourceAddress} \& 0xFF)$$
2. Construct synthetic `CanFrame`:
   ```python
   synthetic_frame = CanFrame.create(
       channel_id=msg.channel_id,
       arbitration_id=arbitration_id,
       data=msg.data,
       is_extended=True,
       timestamp_ns=msg.timestamp_ns,
   )
   ```
3. Pass directly to `DbcSignalDecoder.decode_frame(synthetic_frame)`.
4. Parse raw bitfields against indicator masks:
   - For unsigned signal of bit length $B \in \{2, 4, 8, 16, 32\}$:
     - If raw value $= 2^B - 1 \rightarrow$ `SignalStatus.NOT_AVAILABLE`
     - If raw value $= 2^B - 2 \rightarrow$ `SignalStatus.ERROR`
     - Otherwise $\rightarrow$ `SignalStatus.VALID`

---

# 4. Requirement 4: Mathematical CRC Foundations & Lookup Tables

CRC-8 error detection utilizes polynomial division over Galois Field $\text{GF}(2)$.

## 4.1 CRC Polynomial Formulations

1. **SAE J1850 & AUTOSAR Profile 1**:
   $$P(x) = x^8 + x^4 + x^3 + x^2 + 1 \quad \rightarrow \quad \mathbf{0x1D} \quad (\text{Normal}), \quad \mathbf{0x11D} \quad (\text{Representation})$$
2. **AUTOSAR Profile 2**:
   $$P(x) = x^8 + x^5 + x^3 + x^2 + x + 1 \quad \rightarrow \quad \mathbf{0x2F} \quad (\text{Normal}), \quad \mathbf{0x12F} \quad (\text{Representation})$$

## 4.2 Complete 256-Entry Lookup Tables

### Table 1: CRC-8 Polynomial `0x1D` (SAE J1850 / AUTOSAR Profile 1)
```python
CRC8_TABLE_0x1D = [
    0x00, 0x1D, 0x3A, 0x27, 0x74, 0x69, 0x4E, 0x53, 0xE8, 0xF5, 0xD2, 0xCF, 0x9C, 0x81, 0xA6, 0xBB,
    0xCD, 0xD0, 0xF7, 0xEA, 0xB9, 0xA4, 0x83, 0x9E, 0x25, 0x38, 0x1F, 0x02, 0x51, 0x4C, 0x6B, 0x76,
    0x87, 0x9A, 0xBD, 0xA0, 0xF3, 0xEE, 0xC9, 0xD4, 0x6F, 0x72, 0x55, 0x48, 0x1B, 0x06, 0x21, 0x3C,
    0x4A, 0x57, 0x70, 0x6D, 0x3E, 0x23, 0x04, 0x19, 0xA2, 0xBF, 0x98, 0x85, 0xD6, 0xCB, 0xEC, 0xF1,
    0x13, 0x0E, 0x29, 0x34, 0x67, 0x7A, 0x5D, 0x40, 0xFB, 0xE6, 0xC1, 0xDC, 0x8F, 0x92, 0xB5, 0xA8,
    0xDE, 0xC3, 0xE4, 0xF9, 0xAA, 0xB7, 0x90, 0x8D, 0x36, 0x2B, 0x0C, 0x11, 0x42, 0x5F, 0x78, 0x65,
    0x94, 0x89, 0xAE, 0xB3, 0xE0, 0xFD, 0xDA, 0xC7, 0x7C, 0x61, 0x46, 0x5B, 0x08, 0x15, 0x32, 0x2F,
    0x59, 0x44, 0x63, 0x7E, 0x2D, 0x30, 0x17, 0x0A, 0xB1, 0xAC, 0x8B, 0x96, 0xC5, 0xD8, 0xFF, 0xE2,
    0x26, 0x3B, 0x1C, 0x01, 0x52, 0x4F, 0x68, 0x75, 0xCE, 0xD3, 0xF4, 0xE9, 0xBA, 0xA7, 0x80, 0x9D,
    0xEB, 0xF6, 0xD1, 0xCC, 0x9F, 0x82, 0xA5, 0xB8, 0x03, 0x1E, 0x39, 0x24, 0x77, 0x6A, 0x4D, 0x50,
    0xA1, 0xBC, 0x9B, 0x86, 0xD5, 0xC8, 0xEF, 0xF2, 0x49, 0x54, 0x73, 0x6E, 0x3D, 0x20, 0x07, 0x1A,
    0x6C, 0x71, 0x56, 0x4B, 0x18, 0x05, 0x22, 0x3F, 0x84, 0x99, 0xBE, 0xA3, 0xF0, 0xED, 0xCA, 0xD7,
    0x35, 0x28, 0x0F, 0x12, 0x41, 0x5C, 0x7B, 0x66, 0xDD, 0xC0, 0xE7, 0xFA, 0xA9, 0xB4, 0x93, 0x8E,
    0xF8, 0xE5, 0xC2, 0xDF, 0x8C, 0x91, 0xB6, 0xAB, 0x10, 0x0D, 0x2A, 0x37, 0x64, 0x79, 0x5E, 0x43,
    0xB2, 0xAF, 0x88, 0x95, 0xC6, 0xDB, 0xFC, 0xE1, 0x5A, 0x47, 0x60, 0x7D, 0x2E, 0x33, 0x14, 0x09,
    0x7F, 0x62, 0x45, 0x58, 0x0B, 0x16, 0x31, 0x2C, 0x97, 0x8A, 0xAD, 0xB0, 0xE3, 0xFE, 0xD9, 0xC4,
]
```

### Table 2: CRC-8 Polynomial `0x2F` (AUTOSAR Profile 2 / VAG MQB)
```python
CRC8_TABLE_0x2F = [
    0x00, 0x2F, 0x5E, 0x71, 0xBC, 0x93, 0xE2, 0xCD, 0x57, 0x78, 0x09, 0x26, 0xEB, 0xC4, 0xB5, 0x9A,
    0xAE, 0x81, 0xF0, 0xDF, 0x12, 0x3D, 0x4C, 0x63, 0xF9, 0xD6, 0xA7, 0x88, 0x45, 0x6A, 0x1B, 0x34,
    0x73, 0x5C, 0x2D, 0x02, 0xCF, 0xE0, 0x91, 0xBE, 0x24, 0x0B, 0x7A, 0x55, 0x98, 0xB7, 0xC6, 0xE9,
    0xDD, 0xF2, 0x83, 0xAC, 0x61, 0x4E, 0x3F, 0x10, 0x8A, 0xA5, 0xD4, 0xFB, 0x36, 0x19, 0x68, 0x47,
    0xE6, 0xC9, 0xB8, 0x97, 0x5A, 0x75, 0x04, 0x2B, 0xB1, 0x9E, 0xEF, 0xC0, 0x0D, 0x22, 0x53, 0x7C,
    0x48, 0x67, 0x16, 0x39, 0xF4, 0xDB, 0xAA, 0x85, 0x1F, 0x30, 0x41, 0x6E, 0xA3, 0x8C, 0xFD, 0xD2,
    0x95, 0xBA, 0xCB, 0xE4, 0x29, 0x06, 0x77, 0x58, 0xC2, 0xED, 0x9C, 0xB3, 0x7E, 0x51, 0x20, 0x0F,
    0x3B, 0x14, 0x65, 0x4A, 0x87, 0xA8, 0xD9, 0xF6, 0x6C, 0x43, 0x32, 0x1D, 0xD0, 0xFF, 0x8E, 0xA1,
    0xE3, 0xCC, 0xBD, 0x92, 0x5F, 0x70, 0x01, 0x2E, 0xB4, 0x9B, 0xEA, 0xC5, 0x08, 0x27, 0x56, 0x79,
    0x4D, 0x62, 0x13, 0x3C, 0xF1, 0xDE, 0xAF, 0x80, 0x1A, 0x35, 0x44, 0x6B, 0xA6, 0x89, 0xF8, 0xD7,
    0x90, 0xBF, 0xCE, 0xE1, 0x2C, 0x03, 0x72, 0x5D, 0xC7, 0xE8, 0x99, 0xB6, 0x7B, 0x54, 0x25, 0x0A,
    0x3E, 0x11, 0x60, 0x4F, 0x82, 0xAD, 0xDC, 0xF3, 0x69, 0x46, 0x37, 0x18, 0xD5, 0xFA, 0x8B, 0xA4,
    0x05, 0x2A, 0x5B, 0x74, 0xB9, 0x96, 0xE7, 0xC8, 0x52, 0x7D, 0x0C, 0x23, 0xEE, 0xC1, 0xB0, 0x9F,
    0xAB, 0x84, 0xF5, 0xDA, 0x17, 0x38, 0x49, 0x66, 0xFC, 0xD3, 0xA2, 0x8D, 0x40, 0x6F, 0x1E, 0x31,
    0x76, 0x59, 0x28, 0x07, 0xCA, 0xE5, 0x94, 0xBB, 0x21, 0x0E, 0x7F, 0x50, 0x9D, 0xB2, 0xC3, 0xEC,
    0xD8, 0xF7, 0x86, 0xA9, 0x64, 0x4B, 0x3A, 0x15, 0x8F, 0xA0, 0xD1, 0xFE, 0x33, 0x1C, 0x6D, 0x42,
]
```

---

# 5. Requirement 4: AUTOSAR E2E Profile 1 Specification

AUTOSAR E2E Profile 1 (AUTOSAR CP R4.4 / R20-11) is widely deployed for powertrain, steering, and braking frames.

## 5.1 Protocol Parameters
- **CRC Polynomial**: `0x1D` ($x^8 + x^4 + x^3 + x^2 + 1$)
- **Initial CRC Value**: `0xFF`
- **Final XOR Value**: `0xFF`
- **Data ID**: 16-bit identifier per message ($0 \le \text{DataID} \le 65535$)
- **Counter Range**: 4 bits ($0 \dots 14$ in Profile 1A, $15$ represents error; or $0 \dots 15$ in Profile 1B/1C)
- **Max Delta Counter**: Default `2` (tolerates 1 dropped frame without fault)

## 5.2 Variants

| Variant | Data ID Mode | CRC Calculation Sequence | Counter Mode |
|:---|:---|:---|:---|
| **Profile 1A** | Nibble in data (`DataIDNibble = (DataID >> 8) & 0x0F`) | CRC over Payload + DataID_Low | 4-bit ($0 \dots 14$) |
| **Profile 1B** | Both bytes included | CRC over DataID_Low + Payload, then $\text{CRC} = \text{CRC} \oplus \text{DataID\_High}$ | 4-bit ($0 \dots 15$) |
| **Profile 1C** | Both bytes fed into CRC | CRC over DataID_Low + DataID_High + Payload | 4-bit ($0 \dots 15$) |

## 5.3 Frame Layout (Profile 1 Standard)
```
Byte 0: [ CRC-8 Checksum (8 bits) ]
Byte 1: [ Counter (4 bits, bits 0..3) | Custom / Status (4 bits, bits 4..7) ]
Byte 2..7: Protected Application Data
```

---

# 6. Requirement 4: AUTOSAR E2E Profile 2 Specification

AUTOSAR E2E Profile 2 (AUTOSAR CP R4.4 / R20-11) provides higher fault detection capability for ASIL D chassis safety systems.

## 6.1 Protocol Parameters
- **CRC Polynomial**: `0x2F` ($x^8 + x^5 + x^3 + x^2 + x + 1$)
- **Initial CRC Value**: `0xFF`
- **Final XOR Value**: `0xFF`
- **Counter Range**: 4 bits ($0 \dots 15$, increments $+1 \pmod{16}$)
- **Data ID List**: Array of 16 distinct 8-bit Data IDs: $\text{DataIDList} = [D_0, D_1, \dots, D_{15}]$.
  - For transmission $k$ with counter value $C_k$, the Data ID used is $D = \text{DataIDList}[C_k]$.

## 6.2 CRC Calculation Algorithm
$$\text{CRC} = \text{CRC8\_Update}\Big(\text{CRC8\_Update}(\text{Init}=0xFF, \text{Payload}[\text{excl. CRC}]), \text{DataIDList}[\text{Counter}]\Big) \oplus 0xFF$$

## 6.3 Frame Layout (Profile 2 Standard)
```
Byte 0: [ CRC-8 Checksum (8 bits) ]
Byte 1: [ Counter (4 bits, bits 0..3) | Sequence Status (4 bits, bits 4..7) ]
Byte 2..7: Protected Application Data
```

---

# 7. Requirement 4: SAE J1850 & OEM Safety Profiles

## 7.1 SAE J1850 CRC-8
- **Polynomial**: `0x1D`
- **Init**: `0xFF`, **Final XOR**: `0xFF`
- **Reflect In**: `False`, **Reflect Out**: `False`
- **Standard Verification Test**: `b"123456789"` $\rightarrow \mathbf{0x4B}$.

---

## 7.2 Toyota Safety Profile (TSS2 / ADAS / Powertrain)

Toyota uses an additive/modulo-256 checksum and a 4-bit or 8-bit rolling counter.

### Bit Layout (Standard 8-Byte Frame):
- `Bytes 0..6`: Application Data (with `COUNTER` in Byte 6 or 1)
- `Byte 7`: `CHECKSUM` (8 bits)

### Checksum Mathematical Routine:
$$\text{Checksum} = \left( \sum_{i=0}^{6} \text{Payload}[i] + (\text{CAN\_ID} \gg 8) + (\text{CAN\_ID} \& 0xFF) + \text{DLC} \right) \& 0xFF$$

*Alternative TSS2/Denso Routine (without DLC addition)*:
$$\text{Checksum} = \left( \sum_{i=0}^{6} \text{Payload}[i] + (\text{CAN\_ID} \gg 8) + (\text{CAN\_ID} \& 0xFF) \right) \& 0xFF$$

### Rolling Counter:
- Counter steps $0 \rightarrow 1 \rightarrow \dots \rightarrow 15 \rightarrow 0$ (4-bit) or $0 \rightarrow 255 \rightarrow 0$ (8-bit).
- Incremented strictly once per transmitted CAN frame.

---

## 7.3 VAG MQB Platform Safety Profile (Volkswagen, Audi, SEAT, Škoda)

VAG MQB uses AUTOSAR CRC-8 (`0x2F`) with a per-message 16-bit Data ID and a 4-bit rolling counter.

### Bit Layout:
- `Byte 0`: `CHECKSUM` / `CRC` (8 bits)
- `Byte 1`: `COUNTER` (bits 0..3: $0 \dots 15$) | `Status` (bits 4..7)
- `Bytes 2..7`: Application Data

### Calculation Routine:
$$\text{PayloadWithID} = \text{Payload}[1:8] + \text{DataID}.\text{to\_bytes}(2, \text{byteorder}=\text{"little"})$$
$$\text{CRC} = \text{CRC8\_0x2F}(\text{Init}=0xFF, \text{PayloadWithID}) \oplus 0xFF$$

---

## 7.4 Volvo SPA / CMA & Heavy Duty / Marine Safety Profile

Volvo uses an 8-bit Ones-Complement Sum or CRC-8 combined with a 3-bit, 4-bit, or 8-bit sequence counter.

### Bit Layout:
- `Bytes 0..6`: Application Data (contains `Counter` in bits 0..3 of Byte 1 or Byte 6)
- `Byte 7`: `Checksum` (8 bits)

### Ones-Complement Checksum Routine:
$$\text{Sum} = \sum_{i=0}^{6} \text{Payload}[i]$$
$$\text{Checksum} = (\sim \text{Sum}) \& 0xFF$$

---

# 8. Requirement 4: Rx Validation & Tx Packaging Architecture

```
                                  +-----------------------+
                                  |    E2ESafetyEngine    |
                                  +-----------------------+
                                   /                     \
                   [Rx Path]      /                       \      [Tx Path]
                                 v                         v
                   +-----------------------+     +-----------------------+
                   |   E2ESafetyValidator  |     |   E2ESafetyPackager   |
                   +-----------------------+     +-----------------------+
                     |                       |     |                       |
            (Validate CRC)          (Track Counter)| (Increment Counter)   | (Compute CRC)
                     |                       |     |                       |
                     v                       v     v                       v
               Verdict: OK             Sequence    Inject Counter Nibble   Inject CRC Byte
               CRC_MISMATCH            Tracking    & Assemble Outgoing     into Payload
               WRONG_SEQUENCE          Per CAN ID  CAN Frame               (Ready to TX)
               REPEATED / SOME_LOST
```

## 8.1 Rx Validation State Machine & Verdicts

For every incoming frame with configured E2E protection:
1. **CRC Verification**:
   - Extract received CRC byte $C_{rx}$.
   - Compute expected CRC $C_{calc}$ over payload according to the configured profile.
   - If $C_{rx} \ne C_{calc} \rightarrow$ Return verdict `E2EStatus.CRC_ERROR`.
2. **Rolling Counter Delta Evaluation**:
   - Extract received counter $K_{curr} \in [0, M-1]$.
   - If first frame received $\rightarrow$ Set $K_{prev} = K_{curr}$, return `E2EStatus.INITIAL`.
   - Calculate delta:
     $$\Delta = (K_{curr} - K_{prev}) \bmod M$$
   - Evaluate verdict:
     - $\Delta == 1 \rightarrow$ `E2EStatus.OK` (Normal consecutive progression)
     - $\Delta == 0 \rightarrow$ `E2EStatus.REPEATED` (Duplicate frame detected)
     - $2 \le \Delta \le \text{MaxDeltaCounter} \rightarrow$ `E2EStatus.SOME_LOST` (Frames dropped on bus)
     - $\Delta > \text{MaxDeltaCounter} \rightarrow$ `E2EStatus.WRONG_SEQUENCE` (Severe sequence jump / out of order)

## 8.2 Tx Packaging Pipeline

When transmitting a safety-critical frame:
1. Fetch and increment the message's internal rolling counter:
   $$K_{next} = (K_{last} + 1) \bmod M$$
2. Write $K_{next}$ into designated payload byte/nibble.
3. Compute CRC over the updated payload using the configured profile, polynomial, and Data ID.
4. Write computed CRC into the designated CRC byte offset.
5. Transmit fully formed `CanFrame`.

---

# 9. Authoritative Test Vectors & Empirical Matrices

## 9.1 CRC-8 Standard Test Vectors

| Test Input (ASCII / Hex) | Polynomial | Initial Value | Final XOR | Expected CRC Result |
|:---|:---|:---|:---|:---|
| `"123456789"` (`0x31..0x39`) | `0x1D` | `0xFF` | `0xFF` | **`0x4B`** |
| `"123456789"` (`0x31..0x39`) | `0x2F` | `0xFF` | `0xFF` | **`0xDF`** |
| `00 00 00 00` | `0x1D` | `0xFF` | `0xFF` | **`0x59`** |
| `00 00 00 00` | `0x2F` | `0xFF` | `0xFF` | **`0x9C`** |
| `FF FF FF FF` | `0x1D` | `0xFF` | `0xFF` | **`0x74`** |
| `FF FF FF FF` | `0x2F` | `0xFF` | `0xFF` | **`0x89`** |

## 9.2 AUTOSAR Profile 1 Test Vector
- **Data ID**: `0x0123` (`Low = 0x23, High = 0x01`)
- **Counter**: `0x05`
- **Data Payload (Bytes 1..7)**: `0x05, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66`
- **Profile 1C Input Buffer**: `0x23, 0x01, 0x05, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66`
- **Calculated CRC-8 (`0x1D`)**: **`0x0F`**
- **Assembled Frame**: `0x0F, 0x05, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66`

## 9.3 AUTOSAR Profile 2 Test Vector
- **Data ID List**: `[0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F]`
- **Counter**: `0x02` $\rightarrow$ Selected Data ID = `0x12`
- **Payload (Bytes 1..7)**: `0x02, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF`
- **Calculation Input**: `0x02, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x12`
- **Calculated CRC-8 (`0x2F`)**: **`0x7B`**
- **Assembled Frame**: `0x7B, 0x02, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF`

## 9.4 OEM Profiles Test Vectors

1. **Toyota Additive Checksum**:
   - `CAN_ID = 0x2E4` (`0x02, 0xE4`)
   - `Payload (Bytes 0..6)`: `10 20 30 40 50 60 01` (Counter = 1 in Byte 6)
   - `DLC = 8`
   - `Sum = 0x10 + 0x20 + 0x30 + 0x40 + 0x50 + 0x60 + 0x01 + 0x02 + 0xE4 + 8 = 0x023F`
   - **Checksum (Byte 7)**: **`0x3F`**

2. **VAG MQB CRC-8**:
   - `DataID = 0x1234`
   - `Payload (Bytes 1..7)`: `01 02 03 04 05 06 07`
   - `Calculation Input`: `01 02 03 04 05 06 07 34 12`
   - **Checksum (Byte 0)**: **`0xA4`**

3. **Volvo Ones-Complement Checksum**:
   - `Payload (Bytes 0..6)`: `10 20 30 40 50 60 01`
   - `Sum = 0x10 + 0x20 + 0x30 + 0x40 + 0x50 + 0x60 + 0x01 = 0x0151 & 0xFF = 0x51`
   - `Checksum = ~0x51 & 0xFF = 0xAE`
   - **Checksum (Byte 7)**: **`0xAE`**

---

# 10. Edge Cases, Error Handling & Security Matrix

```
+----+----------------------------+-----------------------------------+---------------------------------------------------+
| #  | Edge Case Category         | Scenario / Trigger Condition      | Mandated Protocol & Safety Behavior               |
+----+----------------------------+-----------------------------------+---------------------------------------------------+
| E1 | J1939 Length Out of Bounds | BAM/RTS Total Bytes = 0 or > 1785 | Silently reject frame; do not allocate session    |
| E2 | J1939 Packet Count Mismatch| Declared packets != (bytes+6)//7  | Reject TP.CM frame; log warning                   |
| E3 | J1939 Out-of-Order Packet  | Sequence number != expected       | BAM: Silent eviction. CMDT: Send Conn_Abort (0x01)|
| E4 | J1939 T1 Inactivity Timeout| No packet received for > 750 ms   | BAM: Silent reap. CMDT: Send Conn_Abort (0x03)    |
| E5 | J1939 Session Collision    | RTS arrives for in-flight session | Send Conn_Abort (0x02) for old; start new session |
| E6 | J1939 Broadcast RTS DA=255 | RTS frame sent with DA == 255     | Reject RTS frame; RTS must be point-to-point      |
| E7 | J1939 Resource Exhaustion  | Flooding > 512 sessions / 4 per SA| Evict oldest idle session; enforce per-SA quota   |
| E8 | ISO-TP SF_DL == 0          | Classic CAN Single Frame SF_DL = 0| Reject with IsoTpInvalidPduError                  |
| E9 | ISO-TP CAN FD SF > 62 B    | CAN FD Single Frame SF_DL > 62    | Reject with IsoTpInvalidPduError                  |
| E10| ISO-TP Extended FF <= 4095 | 32-bit FF with length <= 4095 B   | Reject with IsoTpInvalidPduError                  |
| E11| ISO-TP WFTmax Exceeded     | Received > 16 consecutive FC_WAIT | Raise IsoTpTimeoutError; abort transmission       |
| E12| ISO-TP Buffer Overflow     | Requested length > max buffer     | Send FC_OVERFLOW; raise IsoTpBufferOverflowError  |
| E13| E2E CRC Mismatch           | Computed CRC != Received CRC Byte | Classify as CRC_ERROR; drop frame; increment count|
| E14| E2E Counter Sequence Jump  | Counter Delta > MaxDeltaCounter   | Classify as WRONG_SEQUENCE; alert health monitor  |
| E15| E2E Replay Attack          | Duplicate counter received (D = 0)| Classify as REPEATED; ignore duplicate payload    |
| E16| E2E Counter Wrap-Around    | Counter wraps from 15 to 0        | Recognized as valid Delta = 1 mod 16              |
+----+----------------------------+-----------------------------------+---------------------------------------------------+
```

---

# 11. Discovered Features & Interface Catalog

## 11.1 Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | R3 Transport | J1939 BAM Reassembly | Broadcast multi-packet reassembly (PGN 60416 / 60160) | CanFrame (29-bit) | CompletedMessage | Silent drop on timeout or sequence error | SAE J1939-21 §5.10 |
| 2 | R3 Transport | J1939 RTS/CTS CMDT | Point-to-point connection-mode transport with CTS/ACK | CanFrame (29-bit) | CompletedMessage + ACK CanFrame | Transmits Conn_Abort (reasons 1..5) | SAE J1939-21 §5.10 |
| 3 | R3 Transport | J1939 Segmentation | Outgoing segmentation for BAM and CMDT peer transfers | PGN, data bytes, SA/DA | List[CanFrame] | ValueError if length < 1 or > 1785 | SAE J1939-21 §5.10 |
| 4 | R3 Transport | ISO-TP SF Codec | Single Frame Classic CAN (1..7B) and CAN FD Extended SF (1..62B) | Raw data / CanFrame | CanFrame / bytes | Rejects SF_DL=0 or >62 | ISO 15765-2:2016 §9.4 |
| 5 | R3 Transport | ISO-TP Multi-Frame | Standard 12-bit (<=4095B) and Extended 32-bit (>4095B) FF + CF | Multi-byte payload | Segmented frames / bytes | IsoTpSequenceError, IsoTpBufferOverflowError | ISO 15765-2:2016 §9.5 |
| 6 | R3 Transport | ISO-TP Flow Control | FlowStatus CTS, WAIT (WFTmax=16), OVERFLOW, BS, STmin pacing | FC CanFrame | Pacing delays (ms/µs) | IsoTpTimeoutError if WFTmax exceeded | ISO 15765-2:2016 §9.6 |
| 7 | R3 Transport | Extended Addressing | 29-bit Normal Fixed (0x18DA/0x18DB), 8-bit N_TA, and N_AE | CAN ID / Header | Normalized payload | Rejects malformed headers | ISO 15765-2:2016 §9.2 |
| 8 | R3 Transport | DBC Reassembly Handover | Synthetic CanFrame synthesis and direct DbcSignalDecoder decode | CompletedMessage | DecodedMessage | Returns None if PGN not in DBC | Saha Risk Kataloğu R-08 |
| 9 | R4 Safety | AUTOSAR E2E Profile 1 | CRC-8 (0x1D) + 4-bit Counter (0..14/15) + 16-bit Data ID | CanFrame payload | Validation verdict / Protected frame | CRC_MISMATCH, WRONG_SEQUENCE | AUTOSAR CP R4.4 E2E |
| 10 | R4 Safety | AUTOSAR E2E Profile 2 | CRC-8 (0x2F) + 4-bit Counter (0..15) + 16 Data ID List | CanFrame payload | Validation verdict / Protected frame | CRC_MISMATCH, WRONG_SEQUENCE | AUTOSAR CP R4.4 E2E |
| 11 | R4 Safety | SAE J1850 CRC-8 | Standard SAE J1850 8-bit CRC calculation engine | Data bytes | 8-bit CRC remainder | Validated against test vector 0x4B | SAE J1850 Standard |
| 12 | R4 Safety | Toyota Safety Profile | Modulo-256 Additive Checksum + 4/8-bit Rolling Counter | CAN ID + Data | Checked frame / Packaged frame | Checksum error, counter jump | Toyota DBCs / TSS2 Spec |
| 13 | R4 Safety | VAG MQB Safety Profile | CRC-8 0x2F + 4-bit Counter + Message Data ID Key | 16-bit Key + Data | Checked frame / Packaged frame | CRC mismatch, counter drop | VAG MQB Architecture |
| 14 | R4 Safety | Volvo Safety Profile | 8-bit Ones-Complement Sum / CRC-8 + 3/4/8-bit Counter | Data payload | Checked frame / Packaged frame | Sum error, sequence jump | Volvo SPA/CMA Platform |
| 15 | R4 Safety | Rx Safety Validator | Stateful receiver health monitor & sequence tracking | Incoming frames | E2EStatus (OK, REPEATED, LOST, CRC_ERR) | Emits security telemetry | ISO 26262 ASIL D |
| 16 | R4 Safety | Tx Safety Packager | Auto-increment counter and auto-calculate CRC for TX | Unprotected payload | Ready-to-send CanFrame | Raises error on profile mismatch | Safety Gateway Stage 1 |

## 11.2 Edge Cases Summary

| # | Feature | Input | Observed Behavior |
|---|---------|-------|-------------------|
| 1 | J1939 BAM | 0-byte or 1786-byte payload | Rejected immediately without allocating session slot |
| 2 | J1939 BAM | Out-of-order DT packet | Session silently evicted; no abort frame emitted on bus |
| 3 | J1939 CMDT | Out-of-order DT packet | Session evicted; TP.Conn_Abort frame emitted with Reason 1 |
| 4 | J1939 CMDT | T1 timeout (> 750 ms) | Session evicted; TP.Conn_Abort frame emitted with Reason 3 |
| 5 | J1939 CMDT | RTS session collision | Old session aborted with Reason 2; new session initialized |
| 6 | ISO-TP Classic | Single Frame SF_DL = 0 | Raises IsoTpInvalidPduError; frame discarded |
| 7 | ISO-TP CAN FD | Extended SF_DL = 63 (> 62) | Raises IsoTpInvalidPduError; frame discarded |
| 8 | ISO-TP Multi-Frame | Extended 32-bit FF with len <= 4095 | Raises IsoTpInvalidPduError; frame discarded |
| 9 | ISO-TP Flow Control| 17 consecutive FC_WAIT frames | Exceeds WFTmax (16); raises IsoTpTimeoutError |
| 10| AUTOSAR E2E P1 | Received counter delta = 0 | Classified as REPEATED (duplicate frame) |
| 11| AUTOSAR E2E P2 | Counter wraps 15 -> 0 | Valid increment; delta = 1 mod 16; classified as OK |
| 12| Toyota Safety | Corrupted payload byte | Checksum sum mismatch; rejected with ChecksumError |
| 13| VAG MQB Safety | Incorrect 16-bit Data ID | CRC-8 remainder mismatch; rejected with CrcMismatchError |
| 14| Multi-Packet DBC | DM1 multi-packet with 0xFF padding | DTCs decoded; trailing 0xFF values filtered as NOT_AVAILABLE |
