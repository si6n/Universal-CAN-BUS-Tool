# Universal CAN-Bus Diagnostic & Commercial Vehicle J1939 Specification
**Document ID:** SPEC-DIAG-J1939-V1.0  
**Status:** Authoritative Specification Mining Reference  
**Scope:** R1 (SAE J1979 OBD-II Mode 01 & ISO 14229 UDS Service 0x22 DIDs) and R2 (Commercial Vehicle OEM Proprietary J1939 Definitions & Curation)  
**Target Platform:** Universal CAN-Bus Diagnostic & Telemetry Tool  
**Date:** 2026-08-30  

---

## 1. Executive Summary & Standard References

This specification provides the comprehensive parameter knowledge base, byte layouts, scaling formulas, architectural state machines, and commercial vehicle proprietary parameter mappings for:
1. **SAE J1979 / ISO 15031-5 OBD-II Mode 01 Current Powertrain Diagnostic Data (PIDs 0x00 to 0xFF)**.
2. **ISO 14229-1:2020 Unified Diagnostic Services (UDS) Service 0x22 (ReadDataByIdentifier) Standard & Extended DIDs**.
3. **Active Diagnostic Poller Scheduler & Robust Request/Response State Machine**.
4. **Commercial Vehicle J1939 Proprietary A (PGN 61184 / 0xEF00) and Proprietary B (PGN 65280-65535 / 0xFF00-0xFFFF)**.
5. **OEM-Specific Parameter Maps and Physical Decoders for Cummins, Caterpillar, Scania, Volvo, Detroit Diesel, and Mercedes-Benz Actros**.

### Applicable Normative Standards
- **SAE J1979-DA / ISO 15031-5:** Diagnostic Test Modes & Parameter Identifiers (PID)
- **SAE J1979-2 (OBD-on-UDS):** Modernized Diagnostic Services on UDS
- **ISO 14229-1:2020 / ISO 14229-2:** Unified Diagnostic Services (UDS) & Session Timers
- **ISO 15765-2:2024:** Transport Protocol on CAN (ISO-TP)
- **SAE J1939-71:** Vehicle Application Layer (Standard SPNs and PGNs)
- **SAE J1939-73:** Application Layer - Diagnostics (DM1..DM32, FMI 0..31)
- **SAE J1939-21:** Data Link Layer (BAM & RTS/CTS Transport Protocols)
- **DIN 70070 / ISO 22241:** Diesel Exhaust Fluid (AdBlue / AUS32) 32.5% Concentration Standards

---

## 2. SAE J1979 Mode 01 Parameter Catalog (0x00 to 0xFF)

### 2.1 Protocol Framing & Addressing Rules
- **Functional Request Addressing:**
  - Standard 11-bit CAN ID: `0x7DF` (Broadcast to all powertrain ECUs)
  - Extended 29-bit CAN ID: `0x18DB33F1`
- **Physical Request/Response Addressing:**
  - Primary Powertrain Engine Control Unit (ECM/ECU #1): Request `0x7E0`, Response `0x7E8` (29-bit: `0x18DA00F1` / `0x18DAF100`)
  - Transmission Control Unit (TCU/ECU #2): Request `0x7E1`, Response `0x7E9` (29-bit: `0x18DA02F1` / `0x18DAF102`)
  - Hybrid/EV Gateway / Secondary ECM: Request `0x7E2`..`0x7E7`, Response `0x7EA`..`0x7EF`
- **ISO-TP Single Frame (SF) Request Structure:**
  - Byte 0: `0x02` (Payload Length: 2 bytes)
  - Byte 1: `0x01` (Service ID: Mode 01 - Request Current Powertrain Diagnostic Data)
  - Byte 2: `<PID>` (Target Parameter Identifier: `0x00`..`0xFF`)
  - Bytes 3..7: `0x55` or `0xAA` (ISO 15765-2 Padding)
- **ISO-TP Single Frame (SF) Response Structure:**
  - Byte 0: `[Length]` (e.g. `0x03` to `0x07`)
  - Byte 1: `0x41` (Positive Response: SID `0x01` + `0x40`)
  - Byte 2: `<PID>` (Echoed PID)
  - Bytes 3..N: Raw Data Bytes $A, B, C, D, \dots$

### 2.2 PID Support Bitmap Structure & Decoding Logic
Support discovery is queried in 32-PID ranges using bitmask anchor PIDs:
- `PID 0x00`: PIDs supported `[0x01 - 0x20]`
- `PID 0x20`: PIDs supported `[0x21 - 0x40]`
- `PID 0x40`: PIDs supported `[0x41 - 0x60]`
- `PID 0x60`: PIDs supported `[0x61 - 0x80]`
- `PID 0x80`: PIDs supported `[0x81 - 0xA0]`
- `PID 0xA0`: PIDs supported `[0xA1 - 0xC0]`
- `PID 0xC0`: PIDs supported `[0xC1 - 0xE0]`
- `PID 0xE0`: PIDs supported `[0xE1 - 0xFF]`

#### Bitmap Calculation Algorithm
A support response contains 4 data bytes $A, B, C, D$ (32 bits total):
$$\text{Bitmask} = (A \ll 24) \mid (B \ll 16) \mid (C \ll 8) \mid D$$
For a candidate PID $P$ in range $[P_{\text{base}} + 1, P_{\text{base}} + 32]$:
$$\text{Bit Position} = 32 - (P - P_{\text{base}})$$
$$\text{IsSupported}(P) = \left(\frac{\text{Bitmask} \gg \text{Bit Position}}{1}\right) \ \& \ 1 == 1$$
*Rule:* The least significant bit (bit 0 of byte $D$) indicates whether the next 32-PID block anchor is supported. If bit 0 of PID 0x00 is 1, PID 0x20 must be polled next.

---

### 2.3 Master Mode 01 PID Catalog (0x00 to 0xFF)

| PID (Hex) | PID (Dec) | Parameter Name | Bytes | Raw Bytes | Scaling Formula / Transfer Function | Unit | Valid Range | Physical Description & Bitfields |
|---|---|---|---|---|---|---|---|---|
| **0x00** | 0 | PIDs supported [01-20] | 4 | A, B, C, D | Bitmask (32 bits) | Bitmap | N/A | Bit 31: PID 0x01 ... Bit 0: PID 0x20 support |
| **0x01** | 1 | Monitor Status Since DTCs Cleared | 4 | A, B, C, D | Bitfield | Bitmap | N/A | Byte A: MIL status (bit 7: 0=Off, 1=On), DTC Count (bits 6..0). Bytes B..D: Continuous & Non-continuous readiness tests (Misfire, Fuel System, Catalyst, EGR, O2S, EVAP). |
| **0x02** | 2 | Freeze DTC | 2 | A, B | Raw 16-bit DTC | Code | N/A | DTC that caused freeze frame data capture. |
| **0x03** | 3 | Fuel System Status | 2 | A, B | Bitfield | Bitmap | N/A | Byte A: Fuel System 1, Byte B: Fuel System 2. Values: 0x01=Open loop (cold), 0x02=Closed loop (O2 feedback), 0x04=Open loop (driving conditions), 0x08=Open loop (fault), 0x10=Closed loop with fault. |
| **0x04** | 4 | Calculated Engine Load | 1 | A | $A \cdot \frac{100}{255}$ | % | 0.0 to 100.0 | Normalized engine load percentage. |
| **0x05** | 5 | Engine Coolant Temperature | 1 | A | $A - 40$ | °C | -40 to +215 | Engine coolant temperature sensor reading. |
| **0x06** | 6 | Short Term Fuel Trim — Bank 1 | 1 | A | $(A - 128) \cdot \frac{100}{128}$ | % | -100.0 to +99.2 | Rich/lean short term fuel correction bank 1. |
| **0x07** | 7 | Long Term Fuel Trim — Bank 1 | 1 | A | $(A - 128) \cdot \frac{100}{128}$ | % | -100.0 to +99.2 | Learned adaptive fuel correction bank 1. |
| **0x08** | 8 | Short Term Fuel Trim — Bank 2 | 1 | A | $(A - 128) \cdot \frac{100}{128}$ | % | -100.0 to +99.2 | Rich/lean short term fuel correction bank 2. |
| **0x09** | 9 | Long Term Fuel Trim — Bank 2 | 1 | A | $(A - 128) \cdot \frac{100}{128}$ | % | -100.0 to +99.2 | Learned adaptive fuel correction bank 2. |
| **0x0A** | 10 | Fuel Pressure (Gauge) | 1 | A | $A \cdot 3$ | kPa | 0 to 765 | Low pressure fuel rail supply pressure. |
| **0x0B** | 11 | Intake Manifold Absolute Pressure | 1 | A | $A$ | kPa | 0 to 255 | MAP sensor absolute intake pressure. |
| **0x0C** | 12 | Engine Speed (RPM) | 2 | A, B | $\frac{(A \cdot 256) + B}{4}$ | rpm | 0.0 to 16,383.75 | Crankshaft rotational speed. |
| **0x0D** | 13 | Vehicle Speed | 1 | A | $A$ | km/h | 0 to 255 | Vehicle road speed. |
| **0x0E** | 14 | Timing Advance | 1 | A | $\frac{A}{2} - 64$ | ° BTDC | -64.0 to +63.5 | Cylinder #1 ignition timing before TDC. |
| **0x0F** | 15 | Intake Air Temperature | 1 | A | $A - 40$ | °C | -40 to +215 | Air temperature in intake manifold / filter. |
| **0x10** | 16 | Mass Air Flow Sensor (MAF) | 2 | A, B | $\frac{(A \cdot 256) + B}{100}$ | g/s | 0.0 to 655.35 | Mass flow rate of air entering intake. |
| **0x11** | 17 | Throttle Position | 1 | A | $A \cdot \frac{100}{255}$ | % | 0.0 to 100.0 | Throttle valve position sensor #1. |
| **0x12** | 18 | Commanded Secondary Air Status | 1 | A | Bitfield | Bitmap | N/A | Bit 0: Upstream of catalytic converter, Bit 1: Downstream, Bit 2: Outside atmosphere, Bit 3: Diagnostic pump active. |
| **0x13** | 19 | Oxygen Sensors Present (2 Banks) | 1 | A | Bitfield | Bitmap | N/A | Bits 0..3: Bank 1 Sensors 1..4; Bits 4..7: Bank 2 Sensors 1..4. |
| **0x14** | 20 | O2 Sensor 1: Voltage & Short Term Trim | 2 | A, B | $V = \frac{A}{200}$, $\text{Trim} = (B - 128) \cdot \frac{100}{128}$ | V, % | 0.0-1.275 V, $\pm 100\%$ | Bank 1 Sensor 1 narrow-band voltage and trim. |
| **0x15** | 21 | O2 Sensor 2: Voltage & Short Term Trim | 2 | A, B | $V = \frac{A}{200}$, $\text{Trim} = (B - 128) \cdot \frac{100}{128}$ | V, % | 0.0-1.275 V, $\pm 100\%$ | Bank 1 Sensor 2 downstream voltage and trim. |
| **0x16** | 22 | O2 Sensor 3: Voltage & Short Term Trim | 2 | A, B | $V = \frac{A}{200}$, $\text{Trim} = (B - 128) \cdot \frac{100}{128}$ | V, % | 0.0-1.275 V, $\pm 100\%$ | Bank 1 Sensor 3. |
| **0x17** | 23 | O2 Sensor 4: Voltage & Short Term Trim | 2 | A, B | $V = \frac{A}{200}$, $\text{Trim} = (B - 128) \cdot \frac{100}{128}$ | V, % | 0.0-1.275 V, $\pm 100\%$ | Bank 1 Sensor 4. |
| **0x18** | 24 | O2 Sensor 5: Voltage & Short Term Trim | 2 | A, B | $V = \frac{A}{200}$, $\text{Trim} = (B - 128) \cdot \frac{100}{128}$ | V, % | 0.0-1.275 V, $\pm 100\%$ | Bank 2 Sensor 1. |
| **0x19** | 25 | O2 Sensor 6: Voltage & Short Term Trim | 2 | A, B | $V = \frac{A}{200}$, $\text{Trim} = (B - 128) \cdot \frac{100}{128}$ | V, % | 0.0-1.275 V, $\pm 100\%$ | Bank 2 Sensor 2. |
| **0x1A** | 26 | O2 Sensor 7: Voltage & Short Term Trim | 2 | A, B | $V = \frac{A}{200}$, $\text{Trim} = (B - 128) \cdot \frac{100}{128}$ | V, % | 0.0-1.275 V, $\pm 100\%$ | Bank 2 Sensor 3. |
| **0x1B** | 27 | O2 Sensor 8: Voltage & Short Term Trim | 2 | A, B | $V = \frac{A}{200}$, $\text{Trim} = (B - 128) \cdot \frac{100}{128}$ | V, % | 0.0-1.275 V, $\pm 100\%$ | Bank 2 Sensor 4. |
| **0x1C** | 28 | OBD Standards Conformance | 1 | A | Enumeration | Enum | 1 to 255 | 0x01=OBD-II (CARB), 0x02=OBD (EPA), 0x03=OBD & OBD-II, 0x04=OBD-I, 0x05=Not OBD, 0x06=EOBD, 0x07=EOBD & OBD-II, 0x08=EOBD & OBD, 0x0D=JOBD, 0x11=EMD, 0x12=HD-OBD-C, 0x13=HD-OBD, 0x14=WWH-OBD. |
| **0x1D** | 29 | Oxygen Sensors Present (4 Banks) | 1 | A | Bitfield | Bitmap | N/A | Location of oxygen sensors in 4-bank engines. |
| **0x1E** | 30 | Auxiliary Input Status | 1 | A | Bitfield | Bitmap | N/A | Bit 0: Power Take Off (PTO) active status (0=Off, 1=Active). |
| **0x1F** | 31 | Run Time Since Engine Start | 2 | A, B | $(A \cdot 256) + B$ | seconds | 0 to 65,535 | Total continuous engine operating seconds. |
| **0x20** | 32 | PIDs supported [21-40] | 4 | A, B, C, D | Bitmask (32 bits) | Bitmap | N/A | Support bitmap for PIDs 0x21 to 0x40. |
| **0x21** | 33 | Distance Traveled with MIL On | 2 | A, B | $(A \cdot 256) + B$ | km | 0 to 65,535 | Accumulated km with check engine lamp illuminated. |
| **0x22** | 34 | Fuel Rail Pressure (Manifold Relative) | 2 | A, B | $((A \cdot 256) + B) \cdot 0.079$ | kPa | 0.0 to 5,177.26 | Gasoline port injection fuel pressure relative to vacuum. |
| **0x23** | 35 | Fuel Rail Gauge Pressure (Diesel/GDI) | 2 | A, B | $((A \cdot 256) + B) \cdot 10$ | kPa | 0 to 655,350 | Common rail diesel / GDI direct injection pressure. |
| **0x24** | 36 | O2S1 (Wideband): Equivalence & Voltage | 4 | A, B, C, D | $\lambda = \frac{(A \cdot 256) + B}{32768}$, $V = \frac{(C \cdot 256) + D}{8192}$ | ratio, V | 0.0-2.0, 0-8 V | Bank 1 Sensor 1 wide-range lambda & voltage. |
| **0x25** | 37 | O2S2 (Wideband): Equivalence & Voltage | 4 | A, B, C, D | $\lambda = \frac{(A \cdot 256) + B}{32768}$, $V = \frac{(C \cdot 256) + D}{8192}$ | ratio, V | 0.0-2.0, 0-8 V | Bank 1 Sensor 2 wide-range lambda & voltage. |
| **0x26** | 38 | O2S3 (Wideband): Equivalence & Voltage | 4 | A, B, C, D | $\lambda = \frac{(A \cdot 256) + B}{32768}$, $V = \frac{(C \cdot 256) + D}{8192}$ | ratio, V | 0.0-2.0, 0-8 V | Bank 1 Sensor 3 wide-range lambda & voltage. |
| **0x27** | 39 | O2S4 (Wideband): Equivalence & Voltage | 4 | A, B, C, D | $\lambda = \frac{(A \cdot 256) + B}{32768}$, $V = \frac{(C \cdot 256) + D}{8192}$ | ratio, V | 0.0-2.0, 0-8 V | Bank 1 Sensor 4 wide-range lambda & voltage. |
| **0x28** | 40 | O2S5 (Wideband): Equivalence & Voltage | 4 | A, B, C, D | $\lambda = \frac{(A \cdot 256) + B}{32768}$, $V = \frac{(C \cdot 256) + D}{8192}$ | ratio, V | 0.0-2.0, 0-8 V | Bank 2 Sensor 1 wide-range lambda & voltage. |
| **0x29** | 41 | O2S6 (Wideband): Equivalence & Voltage | 4 | A, B, C, D | $\lambda = \frac{(A \cdot 256) + B}{32768}$, $V = \frac{(C \cdot 256) + D}{8192}$ | ratio, V | 0.0-2.0, 0-8 V | Bank 2 Sensor 2 wide-range lambda & voltage. |
| **0x2A** | 42 | O2S7 (Wideband): Equivalence & Voltage | 4 | A, B, C, D | $\lambda = \frac{(A \cdot 256) + B}{32768}$, $V = \frac{(C \cdot 256) + D}{8192}$ | ratio, V | 0.0-2.0, 0-8 V | Bank 2 Sensor 3 wide-range lambda & voltage. |
| **0x2B** | 43 | O2S8 (Wideband): Equivalence & Voltage | 4 | A, B, C, D | $\lambda = \frac{(A \cdot 256) + B}{32768}$, $V = \frac{(C \cdot 256) + D}{8192}$ | ratio, V | 0.0-2.0, 0-8 V | Bank 2 Sensor 4 wide-range lambda & voltage. |
| **0x2C** | 44 | Commanded EGR | 1 | A | $A \cdot \frac{100}{255}$ | % | 0.0 to 100.0 | Target EGR valve duty cycle/opening. |
| **0x2D** | 45 | EGR Error | 1 | A | $(A - 128) \cdot \frac{100}{128}$ | % | -100.0 to +99.2 | Divergence between commanded and actual EGR. |
| **0x2E** | 46 | Commanded Evaporative Purge | 1 | A | $A \cdot \frac{100}{255}$ | % | 0.0 to 100.0 | EVAP canister purge valve command. |
| **0x2F** | 47 | Fuel Tank Level Input | 1 | A | $A \cdot \frac{100}{255}$ | % | 0.0 to 100.0 | Fuel tank sender float position. |
| **0x30** | 48 | Warm-ups Since Codes Cleared | 1 | A | $A$ | counts | 0 to 255 | Number of engine OBD warm-up cycles. |
| **0x31** | 49 | Distance Traveled Since Codes Cleared | 2 | A, B | $(A \cdot 256) + B$ | km | 0 to 65,535 | Accumulated km since DTC memory clear. |
| **0x32** | 50 | Evap System Vapor Pressure | 2 | A, B | $\frac{\text{signed}(A, B)}{4}$ | Pa | -8,192 to +8,191.75 | EVAP canister tank pressure sensor. |
| **0x33** | 51 | Absolute Barometric Pressure | 1 | A | $A$ | kPa | 0 to 255 | Atmospheric ambient barometric pressure. |
| **0x34** | 52 | O2S1 (Wideband): Equivalence & Current | 4 | A, B, C, D | $\lambda = \frac{(A \cdot 256) + B}{32768}$, $I = \frac{(C \cdot 256) + D}{256} - 128$ | ratio, mA | 0.0-2.0, $\pm 128$ mA | Bank 1 Sensor 1 pumping current wideband O2. |
| **0x35** | 53 | O2S2 (Wideband): Equivalence & Current | 4 | A, B, C, D | $\lambda = \frac{(A \cdot 256) + B}{32768}$, $I = \frac{(C \cdot 256) + D}{256} - 128$ | ratio, mA | 0.0-2.0, $\pm 128$ mA | Bank 1 Sensor 2 pumping current. |
| **0x36** | 54 | O2S3 (Wideband): Equivalence & Current | 4 | A, B, C, D | $\lambda = \frac{(A \cdot 256) + B}{32768}$, $I = \frac{(C \cdot 256) + D}{256} - 128$ | ratio, mA | 0.0-2.0, $\pm 128$ mA | Bank 1 Sensor 3 pumping current. |
| **0x37** | 55 | O2S4 (Wideband): Equivalence & Current | 4 | A, B, C, D | $\lambda = \frac{(A \cdot 256) + B}{32768}$, $I = \frac{(C \cdot 256) + D}{256} - 128$ | ratio, mA | 0.0-2.0, $\pm 128$ mA | Bank 1 Sensor 4 pumping current. |
| **0x38** | 56 | O2S5 (Wideband): Equivalence & Current | 4 | A, B, C, D | $\lambda = \frac{(A \cdot 256) + B}{32768}$, $I = \frac{(C \cdot 256) + D}{256} - 128$ | ratio, mA | 0.0-2.0, $\pm 128$ mA | Bank 2 Sensor 1 pumping current. |
| **0x39** | 57 | O2S6 (Wideband): Equivalence & Current | 4 | A, B, C, D | $\lambda = \frac{(A \cdot 256) + B}{32768}$, $I = \frac{(C \cdot 256) + D}{256} - 128$ | ratio, mA | 0.0-2.0, $\pm 128$ mA | Bank 2 Sensor 2 pumping current. |
| **0x3A** | 58 | O2S7 (Wideband): Equivalence & Current | 4 | A, B, C, D | $\lambda = \frac{(A \cdot 256) + B}{32768}$, $I = \frac{(C \cdot 256) + D}{256} - 128$ | ratio, mA | 0.0-2.0, $\pm 128$ mA | Bank 2 Sensor 3 pumping current. |
| **0x3B** | 59 | O2S8 (Wideband): Equivalence & Current | 4 | A, B, C, D | $\lambda = \frac{(A \cdot 256) + B}{32768}$, $I = \frac{(C \cdot 256) + D}{256} - 128$ | ratio, mA | 0.0-2.0, $\pm 128$ mA | Bank 2 Sensor 4 pumping current. |
| **0x3C** | 60 | Catalyst Temp: Bank 1 Sensor 1 | 2 | A, B | $\frac{(A \cdot 256) + B}{10} - 40$ | °C | -40.0 to +6,513.5 | Catalytic converter substrate temp Bank 1 S1. |
| **0x3D** | 61 | Catalyst Temp: Bank 2 Sensor 1 | 2 | A, B | $\frac{(A \cdot 256) + B}{10} - 40$ | °C | -40.0 to +6,513.5 | Catalytic converter substrate temp Bank 2 S1. |
| **0x3E** | 62 | Catalyst Temp: Bank 1 Sensor 2 | 2 | A, B | $\frac{(A \cdot 256) + B}{10} - 40$ | °C | -40.0 to +6,513.5 | Catalytic converter substrate temp Bank 1 S2. |
| **0x3F** | 63 | Catalyst Temp: Bank 2 Sensor 2 | 2 | A, B | $\frac{(A \cdot 256) + B}{10} - 40$ | °C | -40.0 to +6,513.5 | Catalytic converter substrate temp Bank 2 S2. |
| **0x40** | 64 | PIDs supported [41-60] | 4 | A, B, C, D | Bitmask (32 bits) | Bitmap | N/A | Support bitmap for PIDs 0x41 to 0x60. |
| **0x41** | 65 | Monitor Status This Drive Cycle | 4 | A, B, C, D | Bitfield | Bitmap | N/A | Continuous & readiness test status for current drive cycle. |
| **0x42** | 66 | Control Module Voltage | 2 | A, B | $\frac{(A \cdot 256) + B}{1000}$ | V | 0.000 to 65.535 | ECU battery/ignition feed supply voltage. |
| **0x43** | 67 | Absolute Load Value | 2 | A, B | $\frac{((A \cdot 256) + B) \cdot 100}{255}$ | % | 0.0 to 25,700.0 | Normalized volumetric engine absolute load. |
| **0x44** | 68 | Commanded Fuel-Air Equivalence ($\lambda$) | 2 | A, B | $\frac{(A \cdot 256) + B}{32768}$ | ratio | 0.000 to 1.999 | Target equivalence ratio commanded by ECU. |
| **0x45** | 69 | Relative Throttle Position | 1 | A | $A \cdot \frac{100}{255}$ | % | 0.0 to 100.0 | Relative throttle opening angle above idle stop. |
| **0x46** | 70 | Ambient Air Temperature | 1 | A | $A - 40$ | °C | -40 to +215 | Outside ambient atmospheric temperature. |
| **0x47** | 71 | Absolute Throttle Position B | 1 | A | $A \cdot \frac{100}{255}$ | % | 0.0 to 100.0 | Redundant throttle angle sensor track B. |
| **0x48** | 72 | Absolute Throttle Position C | 1 | A | $A \cdot \frac{100}{255}$ | % | 0.0 to 100.0 | Redundant throttle angle sensor track C. |
| **0x49** | 73 | Accelerator Pedal Position D | 1 | A | $A \cdot \frac{100}{255}$ | % | 0.0 to 100.0 | Accelerator pedal position sensor track D. |
| **0x4A** | 74 | Accelerator Pedal Position E | 1 | A | $A \cdot \frac{100}{255}$ | % | 0.0 to 100.0 | Accelerator pedal position sensor track E. |
| **0x4B** | 75 | Accelerator Pedal Position F | 1 | A | $A \cdot \frac{100}{255}$ | % | 0.0 to 100.0 | Accelerator pedal position sensor track F. |
| **0x4C** | 76 | Commanded Throttle Actuator | 1 | A | $A \cdot \frac{100}{255}$ | % | 0.0 to 100.0 | Electronic throttle motor commanded position. |
| **0x4D** | 77 | Time Run with MIL On | 2 | A, B | $(A \cdot 256) + B$ | minutes | 0 to 65,535 | Accumulated engine running minutes with MIL. |
| **0x4E** | 78 | Time Since Trouble Codes Cleared | 2 | A, B | $(A \cdot 256) + B$ | minutes | 0 to 65,535 | Engine run minutes elapsed since clearing DTCs. |
| **0x4F** | 79 | Maximum Values for Equiv, V, I, P | 4 | A, B, C, D | Equiv=$A$, V=$B$, I=$C$, P=$D \cdot 10$ | mult | Various | Sensor limits for lambda, voltage, current, pressure. |
| **0x50** | 80 | Maximum MAF Air Flow Rate | 4 | A, B, C, D | $A \cdot 10$ | g/s | 0 to 2,550 | Sensor ceiling for mass air flow rate. |
| **0x51** | 81 | Fuel Type | 1 | A | Enumeration | Enum | 1 to 255 | 0x01=Gasoline, 0x02=Methanol, 0x03=Ethanol, 0x04=Diesel, 0x05=LPG, 0x06=CNG, 0x07=Propane, 0x08=Battery/EV, 0x09=Bifuel Gasoline, 0x0A=Bifuel Methanol, 0x0B=Bifuel Ethanol, 0x0C=Bifuel LPG, 0x0D=Bifuel CNG, 0x0E=Bifuel Propane, 0x0F=Bifuel Battery, 0x10=Bifuel Electric, 0x11=Hybrid Gasoline, 0x12=Hybrid Ethanol, 0x13=Hybrid Diesel, 0x14=Hybrid Electric, 0x15=Hybrid Mixed. |
| **0x52** | 82 | Ethanol Fuel % | 1 | A | $A \cdot \frac{100}{255}$ | % | 0.0 to 100.0 | Flex fuel ethanol blend percentage. |
| **0x53** | 83 | Absolute Evap System Vapor Pressure | 2 | A, B | $\frac{(A \cdot 256) + B}{200}$ | kPa | 0.0 to 327.675 | Evaporative fuel tank absolute pressure. |
| **0x54** | 84 | Evap System Vapor Pressure (Pa) | 2 | A, B | $\text{signed}(A, B) - 32767$ | Pa | -32,767 to +32,768 | Fine resolution tank vapor pressure. |
| **0x55** | 85 | Short Term Secondary O2 Trim: Bank 1/3 | 2 | A, B | $(A - 128) \cdot \frac{100}{128}$, $(B - 128) \cdot \frac{100}{128}$ | % | $\pm 100\%$ | Downstream O2 sensor fuel trim correction. |
| **0x56** | 86 | Long Term Secondary O2 Trim: Bank 1/3 | 2 | A, B | $(A - 128) \cdot \frac{100}{128}$, $(B - 128) \cdot \frac{100}{128}$ | % | $\pm 100\%$ | Downstream O2 sensor learned trim correction. |
| **0x57** | 87 | Short Term Secondary O2 Trim: Bank 2/4 | 2 | A, B | $(A - 128) \cdot \frac{100}{128}$, $(B - 128) \cdot \frac{100}{128}$ | % | $\pm 100\%$ | Bank 2/4 secondary trim correction. |
| **0x58** | 88 | Long Term Secondary O2 Trim: Bank 2/4 | 2 | A, B | $(A - 128) \cdot \frac{100}{128}$, $(B - 128) \cdot \frac{100}{128}$ | % | $\pm 100\%$ | Bank 2/4 learned secondary trim correction. |
| **0x59** | 89 | Fuel Rail Absolute Pressure | 2 | A, B | $((A \cdot 256) + B) \cdot 10$ | kPa | 0 to 655,350 | Absolute common rail direct fuel pressure. |
| **0x5A** | 90 | Relative Accelerator Pedal Position | 1 | A | $A \cdot \frac{100}{255}$ | % | 0.0 to 100.0 | Relative accelerator pedal deflection. |
| **0x5B** | 91 | Hybrid Battery Pack Remaining Life | 1 | A | $A \cdot \frac{100}{255}$ | % | 0.0 to 100.0 | High-voltage traction battery state of health / charge. |
| **0x5C** | 92 | Engine Oil Temperature | 1 | A | $A - 40$ | °C | -40 to +215 | Sump lubricating oil temperature sensor. |
| **0x5D** | 93 | Fuel Injection Timing | 2 | A, B | $\frac{((A \cdot 256) + B) - 26880}{128}$ | ° | -210.0 to +302.0 | Main pilot/injection start angle relative to TDC. |
| **0x5E** | 94 | Engine Fuel Rate | 2 | A, B | $((A \cdot 256) + B) \cdot 0.05$ | L/h | 0.0 to 3,276.75 | Instantaneous volumetric fuel consumption. |
| **0x5F** | 95 | Emission Requirements Conformance | 1 | A | Bitfield | Bitmap | N/A | EPA, Euro, CARB emissions stage compliance flags. |
| **0x60** | 96 | PIDs supported [61-80] | 4 | A, B, C, D | Bitmask (32 bits) | Bitmap | N/A | Support bitmap for PIDs 0x61 to 0x80. |
| **0x61** | 97 | Driver's Demand Engine Percent Torque | 1 | A | $A - 125$ | % | -125 to +130 | Torque requested via accelerator pedal. |
| **0x62** | 98 | Actual Engine Percent Torque | 1 | A | $A - 125$ | % | -125 to +130 | Net delivered flywheel indicated torque. |
| **0x63** | 99 | Engine Reference Torque | 2 | A, B | $(A \cdot 256) + B$ | Nm | 0 to 65,535 | 100% baseline reference engine torque rating. |
| **0x64** | 100 | Engine Percent Torque at Idle / Points | 5 | A, B, C, D, E | $A-125, B-125, \dots$ | % | -125 to +130 | Torque map curve points (idle, speed 1..4). |
| **0x65** | 101 | Auxiliary Input / Output Supported | 2 | A, B | Bitfield | Bitmap | N/A | Support flags for auxiliary inputs and PTO. |
| **0x66** | 102 | Mass Air Flow Sensor (Bank 1 & 2) | 5 | A, B, C, D, E | Dual MAF formulas | g/s | 0 to 2,048 | Dual intake bank airflow rates. |
| **0x67** | 103 | Engine Coolant Temp Sensors 1 & 2 | 3 | A, B, C | $A - 40$, $B - 40$ | °C | -40 to +215 | Radiator inlet vs engine block coolant temp. |
| **0x68** | 104 | Intake Air Temp Sensors (Bank 1/2) | 7 | A..G | $A - 40$, $B - 40, \dots$ | °C | -40 to +215 | Intercooler inlet/outlet & bank air temperatures. |
| **0x69** | 105 | Commanded EGR and EGR Error (Dual) | 7 | A..G | Dual EGR scaling | % | 0-100%, $\pm 100\%$ | High-pressure & low-pressure EGR positions & errors. |
| **0x6A** | 106 | Commanded Diesel Intake Air Flow Control | 5 | A..E | Dual throttle | % | 0 to 100.0 | Diesel throttle flap actuator position and error. |
| **0x6B** | 107 | Exhaust Gas Recirculation Temp (Dual) | 5 | A..E | $A - 40$, $B - 40$ | °C | -40 to +215 | Pre/post EGR cooler gas temperatures. |
| **0x6C** | 108 | Commanded Throttle Actuator & Position | 5 | A..E | Multi-throttle | % | 0 to 100.0 | Dual electronic throttle body commands. |
| **0x6D** | 109 | Fuel Pressure Control System | 11 | A..K | Rail & supply | kPa | 0 to 655,350 | Multi-stage common rail closed-loop fuel pressures. |
| **0x6E** | 110 | Injection Pressure Control System | 9 | A..I | Injection commands | kPa | 0 to 655,350 | Diesel HEUI / common rail injection pressures. |
| **0x6F** | 111 | Turbocharger Compressor Inlet Pressure | 3 | A, B, C | $A$ | kPa | 0 to 255 | Air filter restriction / compressor inlet absolute. |
| **0x70** | 112 | Boost Pressure Control | 10 | A..J | Commanded & Actual | kPa | 0 to 655.35 | Commanded vs actual turbo boost absolute pressures. |
| **0x71** | 113 | Variable Geometry Turbo (VGT) Control | 6 | A..F | VGT position | % | 0.0 to 100.0 | Commanded & actual VGT vane nozzle positions. |
| **0x72** | 114 | Wastegate Control | 5 | A..E | Wastegate position | % | 0.0 to 100.0 | Electronic wastegate actuator position & duty. |
| **0x73** | 115 | Exhaust Pressure | 5 | A..E | Absolute & Gauge | kPa | 0 to 655.35 | Exhaust manifold pre-turbine backpressure. |
| **0x74** | 116 | Turbocharger RPM | 5 | A..E | $(A \cdot 256) + B$ | rpm | 0 to 655,350 | Turbocharger shaft rotational speed sensor. |
| **0x75** | 117 | Turbocharger Temp 1 (Compressor/Turbine) | 7 | A..G | Temp conversions | °C | -40 to +1,200 | Turbo compressor inlet/outlet & turbine inlet temps. |
| **0x76** | 118 | Turbocharger Temp 2 (Bearing/Coolant) | 7 | A..G | Temp conversions | °C | -40 to +1,200 | Turbo center housing & bearing cooling temps. |
| **0x77** | 119 | Charge Air Cooler (CAC) Temp | 5 | A..E | $A - 40$, $B - 40$ | °C | -40 to +215 | Intercooler inlet and outlet air temperatures. |
| **0x78** | 120 | Exhaust Gas Temp (EGT) Bank 1 | 9 | A..I | 4 sensors: $\frac{(A \cdot 256) + B}{10} - 40$ | °C | -40.0 to +6,513.5 | EGT Sensors 1..4 (Pre-DOC, Pre-DPF, Post-DPF, Post-SCR). |
| **0x79** | 121 | Exhaust Gas Temp (EGT) Bank 2 | 9 | A..I | 4 sensors: $\frac{(A \cdot 256) + B}{10} - 40$ | °C | -40.0 to +6,513.5 | Bank 2 EGT Sensors 1..4. |
| **0x7A** | 122 | DPF Differential Pressure | 7 | A..G | $\frac{(A \cdot 256) + B}{100} - 327.68$ | kPa | -327.68 to +327.67 | Diesel Particulate Filter delta pressure across core. |
| **0x7B** | 123 | DPF Status & Inlet/Outlet Temps | 7 | A..G | Temps & Flags | °C, bitmask | -40 to +1,200 | DPF core inlet/outlet temps & active regen flag. |
| **0x7C** | 124 | DPF Temperature Bank 1 & 2 | 9 | A..I | Temperature array | °C | -40 to +1,200 | DPF substrate internal core temperatures. |
| **0x7D** | 125 | NOx NTE Control Area Status | 1 | A | Bitfield | Bitmap | N/A | Heavy duty NOx Not-To-Exceed compliance zone. |
| **0x7E** | 126 | PM NTE Control Area Status | 1 | A | Bitfield | Bitmap | N/A | Heavy duty Particulate Matter NTE zone active bit. |
| **0x7F** | 127 | Engine Run Time (Total / Idle / PTO) | 13 | A..M | Cumulative hours | hours | 0 to 4,294,967 | Total operating hours, idle hours, and PTO hours. |
| **0x80** | 128 | PIDs supported [81-A0] | 4 | A, B, C, D | Bitmask (32 bits) | Bitmap | N/A | Support bitmap for PIDs 0x81 to 0xA0. |
| **0x81** | 129 | Engine Run Time for AECD 1..5 | 21 | A..U | AECD timer array | minutes | 0 to 4,294,967 | Auxiliary Emission Control Device active timers. |
| **0x82** | 130 | Engine Run Time for AECD 6..10 | 21 | A..U | AECD timer array | minutes | 0 to 4,294,967 | AECD active timers 6 to 10. |
| **0x83** | 131 | NOx Sensor Concentration Bank 1 | 5 | A..E | $(A \cdot 256) + B$ | ppm | 0 to 65,535 | Pre-SCR & Post-SCR upstream NOx concentration. |
| **0x84** | 132 | NOx Sensor Concentration Bank 2 | 5 | A..E | $(A \cdot 256) + B$ | ppm | 0 to 65,535 | Bank 2 NOx sensor readings. |
| **0x85** | 133 | NOx Sensor Corrected (Bank 1) | 5 | A..E | $(A \cdot 256) + B$ | ppm | 0 to 65,535 | Humidity & O2 corrected NOx concentration. |
| **0x86** | 134 | NOx Sensor Corrected (Bank 2) | 5 | A..E | $(A \cdot 256) + B$ | ppm | 0 to 65,535 | Bank 2 corrected NOx concentration. |
| **0x87** | 135 | Diesel Particulate Filter (DPF) Soot Mass | 5 | A..E | $((A \cdot 256) + B) \cdot 0.1$ | g | 0.0 to 6,553.5 | Calculated soot mass load in DPF filter core. |
| **0x88** | 136 | Alternative Fuel Cylinder Pressure | 4 | A..D | $((A \cdot 256) + B) \cdot 10$ | kPa | 0 to 655,350 | CNG / Hydrogen tank regulator pressure. |
| **0x89** | 137 | Evap System Vapor Pressure (Wide) | 4 | A..D | Signed pressure | Pa | -32,768 to +32,767 | Wide-range fuel tank pressure transmitter. |
| **0x8A** | 138 | Commanded Fuel Injection Pressure | 5 | A..E | $((A \cdot 256) + B) \cdot 10$ | kPa | 0 to 655,350 | ECU commanded rail target pressure. |
| **0x8B** | 139 | Commanded Fuel Rail Pressure B | 5 | A..E | $((A \cdot 256) + B) \cdot 10$ | kPa | 0 to 655,350 | Target pressure for secondary rail / bank. |
| **0x8D** | 141 | Throttle Position G | 1 | A | $A \cdot \frac{100}{255}$ | % | 0.0 to 100.0 | Throttle sensor track G. |
| **0x8E** | 142 | Engine Friction - Percent Torque | 1 | A | $A - 125$ | % | -125 to +130 | Internal parasitic & mechanical friction torque. |
| **0x8F** | 143 | PM Sensor (Particulate Matter) Bank 1/2 | 5 | A..E | PM mass / current | mg/m³ | 0.0 to 1,000.0 | Tailpipe soot sensor soot accumulation rate. |
| **0x90** | 144 | WWH-OBD Vehicle OBD System Info | 3 | A, B, C | Bitfield | Bitmap | N/A | World-Wide Harmonized OBD system class. |
| **0x91** | 145 | WWH-OBD ECU OBD System Info | 5 | A..E | Bitfield | Bitmap | N/A | WWH-OBD ECU compliance & protocol class. |
| **0x92** | 146 | Fuel System Control | 2 | A, B | Bitfield | Bitmap | N/A | Closed loop fuel control enabled flags. |
| **0x93** | 147 | WWH-OBD Counters Support | 3 | A, B, C | Bitfield | Bitmap | N/A | Heavy duty B1, B2, C malfunction counters. |
| **0x94** | 148 | NOx Warning and Inducement System | 12 | A..L | Inducement status | Hours, status | 0-10,000 hrs | SCR tamper / DEF empty speed de-rate countdown. |
| **0x98** | 152 | Exhaust Gas Temp Sensor (Bank 1 & 2) | 9 | A..I | Temperature array | °C | -40 to +1,200 | Wide-temperature EGT array. |
| **0x99** | 153 | Hybrid / EV High Voltage Telemetry | 9 | A..I | Current, Voltage, SOC | A, V, % | $\pm 1000$ A, 0-1000V | High voltage traction battery current, voltage, SOC. |
| **0x9A** | 154 | Diesel Exhaust Fluid (DEF) Sensor Data | 4 | A, B, C, D | Level: $A \cdot \frac{100}{255}$, Conc: $B \cdot 0.05$ | %, % Urea | 0-100%, 0-12.75% | AdBlue tank level and urea concentration percentage. |
| **0x9B** | 155 | O2 Sensor Wide Range (Dual) | 4 | A, B, C, D | Lambda & current | ratio, mA | 0-2.0, $\pm 128$ mA | Dual wideband sensors. |
| **0x9C** | 156 | Engine Fuel Rate (Comprehensive) | 17 | A..Q | Instantaneous / Avg | L/h, g/s | 0 to 5,000 | Multi-point engine fuel consumption rates. |
| **0x9D** | 157 | Engine Exhaust Flow Rate | 4 | A, B, C, D | $\frac{(A \cdot 256) + B}{5}$ | kg/h | 0.0 to 13,107.0 | Mass flow rate of exhaust gas through tailpipe. |
| **0x9E** | 158 | Fuel System Secondary Status | 2 | A, B | Bitfield | Bitmap | N/A | Multi-tank transfer and auxiliary pump status. |
| **0xA0** | 160 | PIDs supported [A1-C0] | 4 | A, B, C, D | Bitmask (32 bits) | Bitmap | N/A | Support bitmap for PIDs 0xA1 to 0xC0. |
| **0xA1** | 161 | NOx Sensor Bank 1 & 2 Sensor 2 | 9 | A..I | $(A \cdot 256) + B$ | ppm | 0 to 65,535 | Downstream SCR outlet tailpipe NOx sensor. |
| **0xA2** | 162 | Cylinder Fuel Rate | 5 | A..E | Fuel quantity | mg/stroke | 0.0 to 500.0 | Fuel injection quantity per cylinder event. |
| **0xA3** | 163 | Evap System Purge Flow | 9 | A..I | Purge flow rate | g/s | 0.0 to 100.0 | Measured purge flow mass and pressure. |
| **0xA4** | 164 | Transmission Actual Gear / Ratio | 4 | A, B, C, D | Gear: $A - 125$, Ratio: $\frac{(B \cdot 256) + C}{1000}$ | gear, ratio | -5 to +18, 0-65.535 | Engaged transmission gear (negative=reverse) & ratio. |
| **0xA5** | 165 | Commanded DEF Dosing | 4 | A, B, C, D | $\frac{(A \cdot 256) + B}{10}$ | g/h | 0.0 to 6,553.5 | Commanded urea dosing rate to SCR injector. |
| **0xA6** | 166 | Odometer | 4 | A, B, C, D | $(A \ll 24 \mid B \ll 16 \mid C \ll 8 \mid D) \cdot 0.1$ | km | 0.0 to 429,496,729.5 | High precision total vehicle distance traveled. |
| **0xC0** | 192 | PIDs supported [C1-E0] | 4 | A, B, C, D | Bitmask (32 bits) | Bitmap | N/A | Support bitmap for PIDs 0xC1 to 0xE0. |
| **0xE0** | 224 | PIDs supported [E1-FF] | 4 | A, B, C, D | Bitmask (32 bits) | Bitmap | N/A | Support bitmap for PIDs 0xE1 to 0xFF. |

---

## 3. ISO 14229 UDS Service 0x22 (ReadDataByIdentifier) DID Knowledge Base

### 3.1 Standard Diagnostic Data Identifiers (0xF180 - 0xF1AF)
Under ISO 14229-1, ISO 27145, and SAE J1979-2, standard 16-bit DIDs (`0xF180` to `0xF1AF`) provide structured identification, software versioning, calibration hashes, and security state metadata:

| DID (Hex) | DID (Dec) | Data Identifier Name | Length | Encoding Format | Example / Format Representation | Description |
|---|---|---|---|---|---|---|
| **0xF180** | 61824 | Boot Software Identification | Variable | ASCII / Hex | `"BOOT_v04.12.00"` | Identifier of bootloader software image. |
| **0xF181** | 61825 | Application Software Identification | Variable | ASCII / Hex | `"SW_APPL_482910"` | Main ECU operational firmware identifier. |
| **0xF182** | 61826 | Application Data Identification | Variable | ASCII / Hex | `"CAL_DATA_ENG_01"` | Calibration maps & parameter dataset ID. |
| **0xF183** | 61827 | Boot Software Fingerprint | 9-16 B | Timestamp + Tester ID | `[YYYYMMDD][Tester ID]` | Flashing stamp of bootloader code. |
| **0xF184** | 61828 | Application Software Fingerprint | 9-16 B | Timestamp + Tester ID | `[YYYYMMDD][Tester ID]` | Flashing stamp of application firmware. |
| **0xF185** | 61829 | Application Data Fingerprint | 9-16 B | Timestamp + Tester ID | `[YYYYMMDD][Tester ID]` | Flashing stamp of calibration parameters. |
| **0xF186** | 61830 | Active Diagnostic Session | 1 Byte | `uint8` IntEnum | `0x01`=Default, `0x02`=Programming, `0x03`=Extended, `0x04`=SafetySystem | Currently active ISO 14229 diagnostic session. |
| **0xF187** | 61831 | Vehicle Manufacturer Spare Part Number | 10-16 B | ASCII String | `"21854930P02"` / `"A0009004802"` | OEM official replacement part number. |
| **0xF188** | 61832 | Vehicle Manufacturer ECU Software Number | 10-16 B | ASCII String | `"SW22948201AB"` | OEM software part number release. |
| **0xF189** | 61833 | Vehicle Manufacturer ECU Software Version | 4-8 B | ASCII / BCD | `"v03.14.02"` | Software build and release version number. |
| **0xF18A** | 61834 | System Supplier Identifier | 4-8 B | ASCII String | `"BOSCH_EDC17"` / `"CONTINENTAL"` | Tier-1 ECU hardware/software supplier ID. |
| **0xF18B** | 61835 | ECU Manufacturing Date | 4 Bytes | BCD (YYYYMMDD) | `0x20 0x24 0x05 0x18` = 2024-05-18 | Physical production line manufacture date. |
| **0xF18C** | 61836 | ECU Serial Number | 16 Bytes | ASCII String | `"SN93847291048200"` | Hardware board unique serial number. |
| **0xF190** | 61840 | Vehicle Identification Number (VIN) | 17 Bytes | ASCII (ISO 3779) | `"1M8GDM9A_KP042788"` | 17-character vehicle chassis identifier. |
| **0xF191** | 61841 | Vehicle Manufacturer ECU Hardware Number | 10-16 B | ASCII String | `"HW21482019AA"` | OEM physical ECU assembly hardware number. |
| **0xF192** | 61842 | System Supplier ECU Hardware Number | 10-16 B | ASCII String | `"0281020349"` (Bosch HW PN) | Tier-1 supplier hardware part number. |
| **0xF193** | 61843 | System Supplier ECU Hardware Version | 4 Bytes | ASCII / BCD | `"HW_v02.00"` | Tier-1 supplier circuit board revision. |
| **0xF194** | 61844 | System Supplier ECU Software Number | 10-16 B | ASCII String | `"1037528190"` (Bosch SW ID) | Tier-1 supplier core software build number. |
| **0xF195** | 61845 | System Supplier ECU Software Version | 4 Bytes | ASCII / BCD | `"SW_v12.45.00"` | Tier-1 supplier low-level software revision. |
| **0xF196** | 61846 | Exhaust Regulation / Type Approval Number | Variable | ASCII String | `"e1*2007/46*0412*02"` | UNECE / EPA exhaust emission approval code. |
| **0xF197** | 61847 | System Name / Engine Type | Variable | ASCII String | `"OM471LA_EURO6"` / `"ISX15_CM2350"` | Powertrain engine family and designation. |
| **0xF198** | 61848 | Repair Shop Code / Tester Serial Number | Variable | ASCII String | `"DEALER_TRUCK_042"` | Last diagnostic tool programming station ID. |
| **0xF199** | 61849 | Programming Date | 4 Bytes | BCD (YYYYMMDD) | `0x20 0x25 0x11 0x04` = 2025-11-04 | Date of last ECU flash reprogramming. |
| **0xF19A** | 61850 | Calibration Repair Shop Code | Variable | ASCII String | `"CAL_STATION_89"` | Diagnostic tool ID used for last calibration. |
| **0xF19D** | 61853 | ECU Installation Date | 4 Bytes | BCD (YYYYMMDD) | `0x20 0x24 0x06 0x01` = 2024-06-01 | Vehicle assembly plant installation date. |
| **0xF1A0** | 61856 | Calibration Verification Number (CVN) #1 | 4 Bytes | Raw 32-bit Hex CRC | `0x9A 0x4F 0x11 0xBC` | Cryptographic checksum of engine calibration. |
| **0xF1A1** | 61857 | Calibration Verification Number (CVN) #2 | 4 Bytes | Raw 32-bit Hex CRC | `0x44 0x12 0x7E 0x09` | Checksum of emissions control calibration. |
| **0xF1A2** | 61858 | Flash Counter (Programming Attempts) | 2 Bytes | `uint16` Big Endian | `0x00 0x03` = 3 flashes | Cumulative successful flash counter. |
| **0xF1A3** | 61859 | Flash Attempt Counter (Max Reprogram) | 2 Bytes | `uint16` Big Endian | `0x00 0x03` = 3 attempts | Reprogramming attempts (detects flash aborts). |
| **0xF1A4** | 61860 | Seed-Key Failure Penalty Counter | 1 Byte | `uint8` | `0x00` (0 failures) | Number of incorrect security access attempts. |
| **0xF1A5** | 61861 | Security Access State Lock Flag | 1 Byte | Bitfield | `0x00`=Locked, `0x01`=Unlocked L1, `0x03`=L3 | Current active security level access mask. |

---

### 3.2 Extended Powertrain & Telemetry DIDs (0x0100 - 0x03FF)

| DID (Hex) | DID (Dec) | Parameter Name | Bytes | Scaling Formula | Unit | Range | Description |
|---|---|---|---|---|---|---|---|
| **0xF010** / **0x0100** | 61456 / 256 | Battery Terminal 30 Voltage | 2 | $\frac{(A \cdot 256) + B}{100}$ | V | 0.00 to 655.35 V | High precision unswitched battery voltage. |
| **0x0101** | 257 | Ignition Switch / Terminal 15 Status | 1 | Enum | Enum | 0 to 3 | 0=Key Off, 1=Accessory, 2=Ignition On, 3=Crank Start. |
| **0x0102** | 258 | Engine Coolant Temperature | 2 | $\frac{(A \cdot 256) + B}{10} - 40.0$ | °C | -40.0 to +215.0 | Dual-byte engine block coolant temp. |
| **0x0103** | 259 | Engine Crankshaft Speed | 2 | $\frac{(A \cdot 256) + B}{4}$ | rpm | 0.0 to 16,383.75 | High resolution engine rotational speed. |
| **0x0104** | 260 | Accelerator Pedal Position | 2 | $\frac{(A \cdot 256) + B}{100}$ | % | 0.00 to 100.00 | Electronic throttle pedal angle. |
| **0x0105** | 261 | Brake Master Cylinder Pressure | 2 | $\frac{(A \cdot 256) + B}{10}$ | bar | 0.0 to 6,553.5 | Hydraulic brake line pressure. |
| **0x0106** | 262 | Steering Wheel Angle | 2 | $\text{signed}(A, B) \cdot 0.1$ | deg | -3,276.8 to +3,276.7 | Steering column sensor angle. |
| **0x0107** | 263 | Vehicle Road Speed | 2 | $\frac{(A \cdot 256) + B}{100}$ | km/h | 0.00 to 655.35 | Calibrated wheel speed sensor average. |
| **0x0110** | 272 | Security Access State | 1 | Bitfield | Enum | 0 to 255 | 0x00=Locked, 0x01=Level 1, 0x03=Level 3, 0x05=Eng. |
| **0x0200** | 512 | DPF Soot Mass Accumulation | 2 | $\frac{(A \cdot 256) + B}{10}$ | g | 0.0 to 6,553.5 | Total particulate filter soot load. |
| **0x0201** | 513 | DPF Regeneration Status Mode | 1 | Enum | Enum | 0 to 5 | 0=Idle, 1=Passive, 2=Active Low, 3=Active High, 4=Parked, 5=Inhibited. |
| **0x0202** | 514 | DPF Differential Pressure | 2 | $\frac{(A \cdot 256) + B}{100}$ | kPa | 0.00 to 655.35 | Delta P across particulate filter substrate. |
| **0x0210** | 528 | AdBlue / DEF Dosing Rate | 2 | $\frac{(A \cdot 256) + B}{100}$ | g/s | 0.00 to 655.35 | Instantaneous SCR urea injection rate. |
| **0x0211** | 529 | AdBlue / DEF Tank Level | 1 | $A \cdot \frac{100}{255}$ | % | 0.0 to 100.0 | Ultrasonic / float tank level percentage. |
| **0x0212** | 530 | AdBlue / DEF Urea Concentration | 2 | $\frac{(A \cdot 256) + B}{100}$ | % | 0.00 to 100.00 | Refractometer quality (Target: 32.5% ISO 22241). |
| **0x0300** | 768 | Injector 1 Balancing Trim Offset | 2 | $\frac{\text{signed}(A, B)}{100}$ | mg/stroke | -327.68 to +327.67 | Cylinder #1 smooth running fuel trim. |
| **0x0301** | 769 | Injector 2 Balancing Trim Offset | 2 | $\frac{\text{signed}(A, B)}{100}$ | mg/stroke | -327.68 to +327.67 | Cylinder #2 smooth running fuel trim. |
| **0x0302** | 770 | Injector 3 Balancing Trim Offset | 2 | $\frac{\text{signed}(A, B)}{100}$ | mg/stroke | -327.68 to +327.67 | Cylinder #3 smooth running fuel trim. |
| **0x0303** | 771 | Injector 4 Balancing Trim Offset | 2 | $\frac{\text{signed}(A, B)}{100}$ | mg/stroke | -327.68 to +327.67 | Cylinder #4 smooth running fuel trim. |
| **0x0304** | 772 | Injector 5 Balancing Trim Offset | 2 | $\frac{\text{signed}(A, B)}{100}$ | mg/stroke | -327.68 to +327.67 | Cylinder #5 smooth running fuel trim. |
| **0x0305** | 773 | Injector 6 Balancing Trim Offset | 2 | $\frac{\text{signed}(A, B)}{100}$ | mg/stroke | -327.68 to +327.67 | Cylinder #6 smooth running fuel trim. |

---

## 4. Active Diagnostic Poller Scheduler & Robust Request/Response State Machine

### 4.1 Multi-Rate Priority Polling Architecture
Active diagnostics on CAN requires deterministic scheduling to prevent bus overload and avoid violating ISO 14229 ECU server timing windows ($P2_{\text{server\_max}} = 50\text{ ms}$, $P2^*_{\text{server\_max}} = 5000\text{ ms}$).

```
                  +---------------------------------------+
                  |      DIAGNOSTIC POLLER SCHEDULER      |
                  +---------------------------------------+
                                      |
         +----------------------------+----------------------------+
         |                            |                            |
         v                            v                            v
  +--------------+             +--------------+             +--------------+
  |  FAST LOOP   |             | MEDIUM LOOP  |             |  SLOW LOOP   |
  |  (10-20 ms)  |             | (100-250 ms) |             | (1000-5000ms)|
  +--------------+             +--------------+             +--------------+
  | • Engine RPM |             | • MAP / MAF  |             | • VIN (F190) |
  | • Veh Speed  |             | • Rail Press |             | • SW/HW IDs  |
  | • Pedal/Thr  |             | • Boost Pres |             | • CVN / ODO  |
  | • Brake Pres |             | • Coolant T. |             | • Ambient T. |
  +--------------+             +--------------+             +--------------+
         |                            |                            |
         +----------------------------+----------------------------+
                                      |
                                      v
                      +-------------------------------+
                      |    TOKEN BUCKET RATE LIMITER  |
                      |   Max Bandwidth: 40 msgs/sec  |
                      +-------------------------------+
                                      |
                                      v
                      +-------------------------------+
                      |  ISO-TP / UDS CLIENT ENGINE   |
                      +-------------------------------+
```

#### Scheduler Timing Bands
1. **Fast Telemetry Loop (10 - 20 ms / 50 Hz - 100 Hz):**
   - High-dynamic control parameters: Engine Speed (PID 0x0C), Vehicle Speed (PID 0x0D), Accelerator Pedal (PID 0x11 / DID 0x0104), Brake Pressure (DID 0x0105).
2. **Medium Telemetry Loop (100 - 250 ms / 4 Hz - 10 Hz):**
   - Thermodynamic & closed loop parameters: Intake MAP (PID 0x0B), MAF (PID 0x10), Fuel Rail Pressure (PID 0x23 / DID 0x0100), Coolant Temp (PID 0x05), Boost Pressure (PID 0x70).
3. **Slow / Identification Loop (1000 - 5000 ms / 0.2 Hz - 1.0 Hz):**
   - Static/quasi-static parameters: VIN (DID 0xF190), System Name (DID 0xF197), Part Numbers (DID 0xF187/F188), Ambient Temp (PID 0x46), Odometer (PID 0xA6), Fuel Level (PID 0x2F).

---

### 4.2 Diagnostic Request/Response State Machine
Every diagnostic transaction is executed via a deterministic finite state machine (FSM):

```
       [IDLE]
         |
         | (Enqueue Request)
         v
    [ENQUEUED]
         |
         | (Rate Limiter Token Available)
         v
  [ISO_TP_TRANSMIT] ---> (Tx Error) ------------+
         |                                       |
         | (Tx Complete, Start P2 Timer)         |
         v                                       |
[WAITING_FOR_RESPONSE] <-----------------+       |
    |          |                         |       |
    | (NRC 0x78)                         |       |
    |          v                         |       |
    |   [WAITING_P2_STAR]                |       |
    |   (Reset Deadline = now + 5.0s)    |       |
    |          |                         |       |
    |          +-------------------------+       |
    |                                            |
    | (Positive Response: SID+0x40)              |
    v                                            |
[PROCESSING_PAYLOAD]                             |
    |                                            |
    | (Decode Physical Signals)                  |
    v                                            |
[COMPLETED]                                      |
                                                 |
    +---- (Timeout / NRC 0x21 / Bus Failure) ----+
    |
    v
[RETRY_BACKOFF]
    |
    +---> (Attempt < MaxRetries: 3) ---> [ENQUEUED]
    |
    +---> (Attempt >= MaxRetries) ---> [FAILED]
```

#### State Definitions & Transition Guard Conditions
1. **`IDLE`:** Poller queue is empty. Awaiting timer triggers or on-demand user diagnostic requests.
2. **`ENQUEUED`:** Request formatted with target SID/PID/DID, CAN IDs, timeout parameters, and priority.
3. **`ISO_TP_TRANSMIT`:** Payload segmented via `IsoTpTransport` into Single Frame (SF) or First Frame (FF) + Consecutive Frames (CF). Routed through `TxSafetyGateway` with speed interlock and confirmation verification.
4. **`WAITING_FOR_RESPONSE`:** Poller waits for response from ECU within standard $P2_{\text{client}}$ window (default 2.0s, minimum ECU specification 50 ms).
5. **`WAITING_P2_STAR`:** Triggered upon reception of Negative Response Code `NRC 0x78 (RequestCorrectlyReceived-ResponsePending)`. Extended timer $P2^* = 5.0\text{ s}$ is armed. Consecutive NRC 0x78 frames refresh the 5.0s window.
6. **`PROCESSING_PAYLOAD`:** Full response reassembled by ISO-TP. SID verified (e.g. `0x62` for `0x22`, `0x41` for `0x01`). Parameter physical values extracted and scaled.
7. **`RETRY_BACKOFF`:** Invoked on communication timeout, CAN bus error, or `NRC 0x21 (BusyRepeatRequest)`. Implements exponential backoff: $t_{\text{wait}} = 50\text{ ms} \times 2^{\text{attempt}}$.
8. **`COMPLETED`:** Telemetry point emitted to signal bus and UI oscilloscope.
9. **`FAILED`:** Final state if retries exhausted. Emits structured `ProtocolError` with error provenance.

---

## 5. Commercial Vehicle OEM Proprietary J1939 Architecture (R2)

### 5.1 SAE J1939 Identifier Breakdown & Proprietary Message Formats
The 29-bit CAN arbitration identifier in SAE J1939 is structured as follows:

```
+----------+---------+--------+------------------+------------------+------------------+
| Priority | Ext DP  | Data P | PDU Format (PF)  | PDU Specific(PS) | Source Addr (SA) |
| (3 bits) | (1 bit) |(1 bit) |     (8 bits)     |     (8 bits)     |     (8 bits)     |
+----------+---------+--------+------------------+------------------+------------------+
| 28 .. 26 |   25    |   24   |    23 .. 16      |     15 .. 8      |      7 .. 0      |
+----------+---------+--------+------------------+------------------+------------------+
```

#### Proprietary PGN Classification
1. **Proprietary A (PDU1 Format - Destination Specific Unicast):**
   - **PGN 61184 (`0xEF00`):** $\text{PF} = 0xEF$ ($239 < 240$). The PDU Specific (PS) field defines the **Destination Address (DA)** of the recipient ECU.
   - **Full CAN ID:** `(Priority << 26) | (0xEF << 16) | (DA << 8) | SA`
   - *Example:* Engine ECU (`SA=0x00`) sending Proprietary A command to Aftertreatment ACM (`DA=0x27`) with Priority 6: `0x18EF2700`.
   - *Usage:* Critical closed OEM commands, calibration overrides, forced DPF manual regeneration trigger, cylinder cut-out commands.
2. **Proprietary A2 (PDU1 Format - Destination Specific Extended):**
   - **PGN 126720 (`0x1EF00`):** Extended Data Page $= 1$, $\text{PF} = 0xEF$.
3. **Proprietary B (PDU2 Format - Global Broadcast Telemetry):**
   - **PGNs 65280 to 65535 (`0xFF00` to `0xFFFF`):** $\text{PF} = 0xFF$ ($255 \ge 240$). The PDU Specific (PS) field serves as the **Group Extension (GE)** defining the proprietary message ID ($0x00$ to $0xFF$).
   - **Full CAN ID:** `(Priority << 26) | (0xFF << 16) | (GE << 8) | SA`
   - *Example:* Scania EMS (`SA=0x00`) broadcasting Proprietary B PGN 65400 (`0xFF78`, $\text{GE}=0x78$): `0x18FF7800`.
   - *Usage:* High-speed OEM telemetry, continuous DPF soot mass, AdBlue dosing rates, retarder torque requests, and cylinder injection balancing offsets.

---

## 6. Commercial Vehicle OEM Proprietary Parameter Databases & Decoders

### 6.1 Cummins Engine Architecture
**Target Engines:** ISX15, X15, ISB6.7, QSL9, L9  
**Target Controllers:** CM2350, CM2450, CM871, CM2250 ECM & Aftertreatment Controller

#### 1. Cummins Aftertreatment Status & DPF Control
- **PGN:** `65300 (0xFF14)` — Proprietary B (GE=`0x14`, SA=`0x00` Engine / `0x27` ACM)
- **CAN ID:** `0x18FF1400` / `0x18FF1427`
- **Cycle Rate:** 100 ms

| Byte Index | Bit Range | Parameter Name | Raw Type | Scaling | Offset | Unit | Range | Description |
|---|---|---|---|---|---|---|---|---|
| **0..1** | 0..15 | Cummins DPF Soot Mass Load | `uint16` LE | $0.1$ | $0.0$ | g | 0.0 to 6,553.5 | Real-time soot accumulation calculated by CM2350. |
| **2** | 0..1 | DPF Active Regeneration Status | `uint2` | Enum | 0 | Enum | 0 to 3 | 00b=Disabled/Off, 01b=Active Stationary (Parked), 10b=Active Mobile (Highway), 11b=Inhibited. |
| **2** | 2..3 | DPF Regeneration Inhibit Switch | `uint2` | Enum | 0 | Enum | 0 to 3 | 00b=Inhibit Off, 01b=Inhibit Switch Active, 10b=Error, 11b=N/A. |
| **2** | 4..7 | Cummins DPF Warning Lamp State | `uint4` | Enum | 0 | Enum | 0 to 15 | 0=Off, 1=Solid (Level 1), 2=Flashing (Level 2), 3=Flashing with Stop Lamp (Level 3 Critical). |
| **3** | 0..7 | Cummins DPF Ash Mass Load Index | `uint8` | $1.0$ | $0.0$ | g | 0 to 250 | Unburnable mineral ash accumulation in DPF core. |
| **4..5** | 0..15 | DPF Differential Pressure (High Res) | `uint16` LE | $0.01$ | $0.0$ | kPa | 0.00 to 655.35 | High-resolution differential pressure transducer. |
| **6..7** | 0..15 | DEF Actual Dosing Rate | `uint16` LE | $0.01$ | $0.0$ | g/s | 0.00 to 655.35 | Cummins UL2/UL3 DEF doser nozzle mass injection rate. |

#### 2. Cummins Cylinder Balancing & Injector Trimming
- **PGN:** `65303 (0xFF17)` — Proprietary B (GE=`0x17`, SA=`0x00`)
- **CAN ID:** `0x18FF1700`
- **Cycle Rate:** 200 ms

| Byte Index | Bit Range | Parameter Name | Raw Type | Scaling | Offset | Unit | Range | Description |
|---|---|---|---|---|---|---|---|---|
| **0** | 0..7 | Cylinder 1 Fuel Trim Offset | `uint8` | $0.1$ | $-12.8$ | mg/stroke | -12.8 to +12.7 | Closed-loop rotational speed balance trim Cyl 1. |
| **1** | 0..7 | Cylinder 2 Fuel Trim Offset | `uint8` | $0.1$ | $-12.8$ | mg/stroke | -12.8 to +12.7 | Rotational speed balance trim Cyl 2. |
| **2** | 0..7 | Cylinder 3 Fuel Trim Offset | `uint8` | $0.1$ | $-12.8$ | mg/stroke | -12.8 to +12.7 | Rotational speed balance trim Cyl 3. |
| **3** | 0..7 | Cylinder 4 Fuel Trim Offset | `uint8` | $0.1$ | $-12.8$ | mg/stroke | -12.8 to +12.7 | Rotational speed balance trim Cyl 4. |
| **4** | 0..7 | Cylinder 5 Fuel Trim Offset | `uint8` | $0.1$ | $-12.8$ | mg/stroke | -12.8 to +12.7 | Rotational speed balance trim Cyl 5. |
| **5** | 0..7 | Cylinder 6 Fuel Trim Offset | `uint8` | $0.1$ | $-12.8$ | mg/stroke | -12.8 to +12.7 | Rotational speed balance trim Cyl 6. |
| **6** | 0..7 | Cummins Engine Balancing Quality Score | `uint8` | $0.4$ | $0.0$ | % | 0.0 to 100.0 | Overall cylinder smooth running index. |
| **7** | 0..7 | Reserved / Checksum | `uint8` | Raw | 0 | N/A | N/A | Proprietary parity check byte. |

#### 3. Cummins Proprietary Service Routine Request
- **PGN:** `61184 (0xEF00)` — Proprietary A (DA=`0x00` Engine)
- **CAN ID:** `0x18EF00F9` (from Diagnostic Tool `0xF9`)
- **Payload Format (8 Bytes):**
  - Byte 0: Service Command ID (`0x3A` = Forced Parked DPF Regeneration Start, `0x3B` = DPF Regen Abort, `0x41` = Cylinder Cut-out Test)
  - Byte 1: Sub-command / Cylinder Target (`0x01`..`0x06` for Cut-out, `0xFF` for All)
  - Bytes 2..3: Security Authentication Token / Seed-Key Signature
  - Bytes 4..7: Execution parameters (`0x00 0x00 0x00 0x00`)

---

### 6.2 Caterpillar Engine Architecture
**Target Engines:** C7, C9, C12, C13, C15, C18 ACERT  
**Target Controllers:** ADEM IV, ADEM V Engine & Clean Emission Module (CEM)

#### 1. CAT Aftertreatment & Regeneration Engine Control
- **PGN:** `65320 (0xFF28)` — Proprietary B (GE=`0x28`, SA=`0x00`)
- **CAN ID:** `0x18FF2800`
- **Cycle Rate:** 100 ms

| Byte Index | Bit Range | Parameter Name | Raw Type | Scaling | Offset | Unit | Range | Description |
|---|---|---|---|---|---|---|---|---|
| **0** | 0..7 | CAT ARD Combustion Air Pressure | `uint8` | $0.5$ | $0.0$ | kPa | 0.0 to 127.5 | Aftertreatment Regeneration Device air supply. |
| **1** | 0..7 | CAT ARD Fuel Pressure | `uint8` | $2.0$ | $0.0$ | kPa | 0 to 510 | Fuel pressure fed to ARD regeneration burner. |
| **2** | 0..7 | CAT ARD Flame Temperature | `uint8` | $5.0$ | $-40.0$ | °C | -40 to +1,235 | Burner combustion flame sensor temperature. |
| **3** | 0..3 | CAT DPF Regeneration Mode | `uint4` | Enum | 0 | Enum | 0 to 15 | 0=Off, 1=Low Temp Self-clean, 2=High Temp Active, 3=Parked Service Regen, 4=Cooldown. |
| **3** | 4..7 | CAT Regeneration Inhibit Status | `uint4` | Enum | 0 | Enum | 0 to 15 | 0=Enabled, 1=Inhibited by Cab Switch, 2=Inhibited by Interlock (Brake/PTO). |
| **4..5** | 0..15 | CAT DPF Soot Loading Index | `uint16` LE | $0.01$ | $0.0$ | % | 0.00 to 655.35 | Particulate filter soot percentage load. |
| **6** | 0..7 | CAT DEF Quality (Urea Concentration)| `uint8` | $0.25$ | $0.0$ | % | 0.0 to 63.75 | DEF concentration (Target 32.5%). |
| **7** | 0..7 | CAT Compression Brake / Retarder Request| `uint8` | $0.5$ | $0.0$ | % | 0.0 to 100.0 | Cat Compression Brake braking level request. |

#### 2. CAT Cylinder Injection Balancing Trim
- **PGN:** `65325 (0xFF2D)` — Proprietary B (GE=`0x2D`, SA=`0x00`)
- **CAN ID:** `0x18FF2D00`
- **Cycle Rate:** 200 ms

| Byte Index | Bit Range | Parameter Name | Raw Type | Scaling | Offset | Unit | Range | Description |
|---|---|---|---|---|---|---|---|---|
| **0** | 0..7 | CAT Cyl 1 MEUI/HEUI Trim Offset | `uint8` | $0.1$ | $-12.8$ | mm³/stroke | -12.8 to +12.7 | Injection volume trim calibration Cyl 1. |
| **1** | 0..7 | CAT Cyl 2 MEUI/HEUI Trim Offset | `uint8` | $0.1$ | $-12.8$ | mm³/stroke | -12.8 to +12.7 | Injection volume trim calibration Cyl 2. |
| **2** | 0..7 | CAT Cyl 3 MEUI/HEUI Trim Offset | `uint8` | $0.1$ | $-12.8$ | mm³/stroke | -12.8 to +12.7 | Injection volume trim calibration Cyl 3. |
| **3** | 0..7 | CAT Cyl 4 MEUI/HEUI Trim Offset | `uint8` | $0.1$ | $-12.8$ | mm³/stroke | -12.8 to +12.7 | Injection volume trim calibration Cyl 4. |
| **4** | 0..7 | CAT Cyl 5 MEUI/HEUI Trim Offset | `uint8` | $0.1$ | $-12.8$ | mm³/stroke | -12.8 to +12.7 | Injection volume trim calibration Cyl 5. |
| **5** | 0..7 | CAT Cyl 6 MEUI/HEUI Trim Offset | `uint8` | $0.1$ | $-12.8$ | mm³/stroke | -12.8 to +12.7 | Injection volume trim calibration Cyl 6. |
| **6..7** | 0..15 | CAT Rail / Actuation High Pressure | `uint16` LE | $0.1$ | $0.0$ | MPa | 0.0 to 6,553.5 | HEUI hydraulic oil pump injection pressure. |

---

### 6.3 Scania Truck & Bus Architecture
**Target Engines:** DC09 (5-Cyl), DC13 (6-Cyl In-line), DC16 (V8 500-770 hp)  
**Target Controllers:** EMS S6, EMS S7, EMS S8, EEC3 / SCR Aftertreatment, RET Retarder (R3500/R4100)

#### 1. Scania EMS Aftertreatment & DPF Control
- **PGN:** `65400 (0xFF78)` — Proprietary B (GE=`0x78`, SA=`0x00` EMS / `0x27` EEC3)
- **CAN ID:** `0x18FF7800` / `0x18FF7827`
- **Cycle Rate:** 100 ms

| Byte Index | Bit Range | Parameter Name | Raw Type | Scaling | Offset | Unit | Range | Description |
|---|---|---|---|---|---|---|---|---|
| **0..1** | 0..15 | Scania DPF Calculated Soot Mass | `uint16` LE | $0.05$ | $0.0$ | g | 0.00 to 3,276.75 | Calculated soot load in Scania Euro 6 DPF. |
| **2** | 0..7 | Scania DPF Regeneration State | `uint8` | Enum | 0 | Enum | 0 to 255 | 0x00=Not Required, 0x01=Automatic Highway Running, 0x02=Parked Regeneration Required, 0x03=Parked Regeneration Running, 0x04=Inhibited by Driver Switch, 0x05=Aborted High Temp, 0x06=System Fault. |
| **3** | 0..7 | Scania AdBlue Dosing Command | `uint8` | $0.1$ | $0.0$ | g/min | 0.0 to 25.5 | Commanded urea dosing rate by EEC3 unit. |
| **4** | 0..7 | Scania AdBlue Tank Level (High Res) | `uint8` | $0.4$ | $0.0$ | % | 0.0 to 100.0 | High-precision DEF tank level sensor. |
| **5** | 0..7 | Scania AdBlue Refractometer Quality | `uint8` | $0.1$ | $0.0$ | % | 0.0 to 25.5 | Measured urea concentration (Target: 32.5%). |
| **6..7** | 0..15 | Scania SCR Catalyst Bed Temperature | `uint16` LE | $0.1$ | $-40.0$ | °C | -40.0 to +6,513.5 | Dual SCR ceramic substrate temperature. |

#### 2. Scania Retarder Control & Telemetry (R3500 / R4100)
- **PGN:** `65410 (0xFF82)` — Proprietary B (GE=`0x82`, SA=`0x10` Retarder)
- **CAN ID:** `0x18FF8210`
- **Cycle Rate:** 50 ms

| Byte Index | Bit Range | Parameter Name | Raw Type | Scaling | Offset | Unit | Range | Description |
|---|---|---|---|---|---|---|---|---|
| **0** | 0..7 | Scania Retarder Lever Stage Request | `uint8` | Enum | 0 | Enum | 0 to 6 | 0=Off, 1=Stage 1 (20%), 2=Stage 2 (40%), 3=Stage 3 (60%), 4=Stage 4 (80%), 5=Stage 5 (100%), 6=Aquatarder Auto Brake Mode. |
| **1** | 0..7 | Scania Retarder Braking Torque Demand| `uint8` | $0.4$ | $0.0$ | % | 0.0 to 100.0 | Requested hydrodynamic braking torque. |
| **2..3** | 0..15 | Scania Retarder Oil Temperature | `uint16` LE | $0.03125$ | $-273.0$ | °C | -273.0 to +1,775.0 | Retarder hydraulic cooling fluid temp. |
| **4** | 0..7 | Scania Retarder Actuator Air Pressure | `uint8` | $0.05$ | $0.0$ | bar | 0.0 to 12.75 | Pneumatic proportional valve control pressure. |
| **5..7** | 0..23 | Reserved / Safety Status | `bytes3` | Raw | 0 | N/A | N/A | Scania safety interlocking flags. |

#### 3. Scania Smooth Running / Cylinder Balancing (DC09, DC13, DC16 V8)
- **PGN:** `65420 (0xFF8C)` — Proprietary B (GE=`0x8C`, SA=`0x00`)
- **CAN ID:** `0x18FF8C00`
- **Cycle Rate:** 100 ms

| Byte Index | Bit Range | Parameter Name | Raw Type | Scaling | Offset | Unit | Range | Description |
|---|---|---|---|---|---|---|---|---|
| **0** | 0..7 | Cyl 1 Smooth Running Correction | `uint8` | $0.25$ | $-32.0$ | mm³/stroke | -32.0 to +31.75 | Individual injector quantity balance Cyl 1. |
| **1** | 0..7 | Cyl 2 Smooth Running Correction | `uint8` | $0.25$ | $-32.0$ | mm³/stroke | -32.0 to +31.75 | Individual injector quantity balance Cyl 2. |
| **2** | 0..7 | Cyl 3 Smooth Running Correction | `uint8` | $0.25$ | $-32.0$ | mm³/stroke | -32.0 to +31.75 | Individual injector quantity balance Cyl 3. |
| **3** | 0..7 | Cyl 4 Smooth Running Correction | `uint8` | $0.25$ | $-32.0$ | mm³/stroke | -32.0 to +31.75 | Individual injector quantity balance Cyl 4. |
| **4** | 0..7 | Cyl 5 Smooth Running Correction | `uint8` | $0.25$ | $-32.0$ | mm³/stroke | -32.0 to +31.75 | Individual injector quantity balance Cyl 5. |
| **5** | 0..7 | Cyl 6 Smooth Running Correction | `uint8` | $0.25$ | $-32.0$ | mm³/stroke | -32.0 to +31.75 | Individual injector quantity balance Cyl 6. |
| **6** | 0..7 | Cyl 7 Smooth Running (DC16 V8 only) | `uint8` | $0.25$ | $-32.0$ | mm³/stroke | -32.0 to +31.75 | V8 Cylinder 7 quantity correction. |
| **7** | 0..7 | Cyl 8 Smooth Running (DC16 V8 only) | `uint8` | $0.25$ | $-32.0$ | mm³/stroke | -32.0 to +31.75 | V8 Cylinder 8 quantity correction. |

---

### 6.4 Volvo Trucks & Renault Architecture
**Target Engines:** D11, D13 (D13K Euro 6), D16, Volvo Penta Marine  
**Target Controllers:** EMS 2.2, EMS 2.3, EMS 2.4, ACM 2.1, ACM 2.2, EVC-A..E

#### 1. Volvo Aftertreatment ACM Telemetry & DPF Status
- **PGN:** `65350 (0xFF46)` — Proprietary B (GE=`0x46`, SA=`0x27` ACM)
- **CAN ID:** `0x18FF4627`
- **Cycle Rate:** 100 ms

| Byte Index | Bit Range | Parameter Name | Raw Type | Scaling | Offset | Unit | Range | Description |
|---|---|---|---|---|---|---|---|---|
| **0..1** | 0..15 | Volvo DPF Soot Accumulation Level | `uint16` LE | $0.1$ | $0.0$ | g | 0.0 to 6,553.5 | Calculated DPF soot mass in grams. |
| **2** | 0..1 | DPF Regeneration Active State | `uint2` | Enum | 0 | Enum | 0 to 3 | 0=Inactive, 1=Service Regeneration, 2=Active In-drive, 3=Inhibited. |
| **2** | 2..3 | DPF Regeneration Inhibit Switch State | `uint2` | Enum | 0 | Enum | 0 to 3 | 0=Normal, 1=Inhibit Demanded by Driver, 2=Error. |
| **2** | 4..7 | High Exhaust Temperature Warning Flag | `uint4` | Enum | 0 | Enum | 0 to 15 | ACM thermal safety flag. |
| **3..4** | 0..15 | Volvo AdBlue Dosing Mass Flow Rate | `uint16` LE | $0.05$ | $0.0$ | g/s | 0.00 to 3,276.75 | Urea mass flow rate to 7th injector. |
| **5** | 0..7 | Volvo AdBlue Tank Level | `uint8` | $0.4$ | $0.0$ | % | 0.0 to 100.0 | Ultrasonic AdBlue level sensor. |
| **6** | 0..7 | Volvo AdBlue Concentration Quality | `uint8` | $0.2$ | $0.0$ | % | 0.0 to 51.0 | DEF quality sensor reading (Target 32.5%). |
| **7** | 0..7 | Volvo ACM Subsystem Health Status | `uint8` | Bitfield | 0 | Bitmap | N/A | SCR pump, pressure line heater, nozzle health. |

#### 2. Volvo VEB+ Engine Brake & Retarder Control
- **PGN:** `65352 (0xFF48)` — Proprietary B (GE=`0x48`, SA=`0x00` EMS / `0x10` Retarder)
- **CAN ID:** `0x18FF4800`
- **Cycle Rate:** 50 ms

| Byte Index | Bit Range | Parameter Name | Raw Type | Scaling | Offset | Unit | Range | Description |
|---|---|---|---|---|---|---|---|---|
| **0** | 0..7 | Volvo VEB+ Engine Brake Stage | `uint8` | Enum | 0 | Enum | 0 to 4 | 0=Off, 1=Low (40% Compression), 2=Med (70%), 3=High (100% VEB+ Compression Brake), 4=Brake Blending Active. |
| **1** | 0..7 | Volvo Retarder Torque Demand | `uint8` | $0.4$ | $0.0$ | % | 0.0 to 100.0 | Driver stalk / EBS auxiliary brake request. |
| **2..3** | 0..15 | Volvo Retarder Delivered Braking Torque| `uint16` LE | $0.5$ | $-1000.0$ | Nm | -1,000 to +31,767.5 | Physical counter-torque delivered at propshaft. |
| **4..7** | 0..31 | Reserved / Retarder Interlocks | `bytes4` | Raw | 0 | N/A | N/A | ABS active inhibit and temp safety flags. |

#### 3. Volvo Cylinder Balancing / Adaptive Trimming
- **PGN:** `65355 (0xFF4B)` — Proprietary B (GE=`0x4B`, SA=`0x00` EMS)
- **CAN ID:** `0x18FF4B00`
- **Cycle Rate:** 200 ms

| Byte Index | Bit Range | Parameter Name | Raw Type | Scaling | Offset | Unit | Range | Description |
|---|---|---|---|---|---|---|---|---|
| **0** | 0..7 | Volvo Cyl 1 Adaptive Trim Offset | `uint8` | $0.1$ | $-12.8$ | mg/stroke | -12.8 to +12.7 | Closed-loop rotational acceleration trim Cyl 1. |
| **1** | 0..7 | Volvo Cyl 2 Adaptive Trim Offset | `uint8` | $0.1$ | $-12.8$ | mg/stroke | -12.8 to +12.7 | Acceleration trim Cyl 2. |
| **2** | 0..7 | Volvo Cyl 3 Adaptive Trim Offset | `uint8` | $0.1$ | $-12.8$ | mg/stroke | -12.8 to +12.7 | Acceleration trim Cyl 3. |
| **3** | 0..7 | Volvo Cyl 4 Adaptive Trim Offset | `uint8` | $0.1$ | $-12.8$ | mg/stroke | -12.8 to +12.7 | Acceleration trim Cyl 4. |
| **4** | 0..7 | Volvo Cyl 5 Adaptive Trim Offset | `uint8` | $0.1$ | $-12.8$ | mg/stroke | -12.8 to +12.7 | Acceleration trim Cyl 5. |
| **5** | 0..7 | Volvo Cyl 6 Adaptive Trim Offset | `uint8` | $0.1$ | $-12.8$ | mg/stroke | -12.8 to +12.7 | Acceleration trim Cyl 6. |
| **6..7** | 0..15 | Volvo Common Rail System Pressure (Actual)| `uint16` LE | $0.1$ | $0.0$ | MPa | 0.0 to 6,553.5 | High pressure common rail actual pressure. |

---

### 6.5 Detroit Diesel Architecture
**Target Engines:** DD13, DD15, DD16 Heavy Duty  
**Target Controllers:** MCM21T (Motor Control Module), ACM21T (Aftertreatment Control Module), CPC4 (Common Powertrain Controller)

#### 1. Detroit Diesel ACM Aftertreatment & DPF Status
- **PGN:** `65370 (0xFF5A)` — Proprietary B (GE=`0x5A`, SA=`0x27` ACM21T)
- **CAN ID:** `0x18FF5A27`
- **Cycle Rate:** 100 ms

| Byte Index | Bit Range | Parameter Name | Raw Type | Scaling | Offset | Unit | Range | Description |
|---|---|---|---|---|---|---|---|---|
| **0..1** | 0..15 | Detroit DPF Soot Mass Accumulation | `uint16` LE | $0.1$ | $0.0$ | g | 0.0 to 6,553.5 | Calculated 1-BOX DPF soot mass. |
| **2..3** | 0..15 | Detroit DPF Ash Mass Accumulation | `uint16` LE | $1.0$ | $0.0$ | g | 0 to 65,535 | Service ash loading index in grams. |
| **4** | 0..3 | Detroit DPF Regeneration Mode | `uint4` | Enum | 0 | Enum | 0 to 15 | 0=Passive, 1=Active Low, 2=Active High, 3=Parked Service Regen, 4=Inhibited. |
| **4** | 4..7 | Detroit DPF Regeneration Inhibit Reason| `uint4` | Enum | 0 | Enum | 0 to 15 | 0=None, 1=Inhibit Switch, 2=Vehicle Speed, 3=Clutch/PTO. |
| **5..6** | 0..15 | Detroit DEF Dosing Rate (Instantaneous)| `uint16` LE | $0.1$ | $0.0$ | g/min | 0.0 to 6,553.5 | Urea dosing injection mass flow. |
| **7** | 0..7 | Detroit DEF Quality Status | `uint8` | Enum | 0 | Enum | 0 to 255 | 0x00=Nominal (32.5% Urea), 0x01=Degraded (28-30%), 0x02=Poor Quality (<28%), 0x03=Tamper/Water Detected. |

#### 2. Detroit Diesel Jake Brake & Secondary Retarder
- **PGN:** `65375 (0xFF5F)` — Proprietary B (GE=`0x5F`, SA=`0x00` MCM / `0x10` Retarder)
- **CAN ID:** `0x18FF5F00`
- **Cycle Rate:** 50 ms

| Byte Index | Bit Range | Parameter Name | Raw Type | Scaling | Offset | Unit | Range | Description |
|---|---|---|---|---|---|---|---|---|
| **0** | 0..7 | Detroit Jake Brake Stage | `uint8` | Enum | 0 | Enum | 0 to 3 | 0=Off, 1=Low (2-Cylinder Compression), 2=Medium (4-Cylinder), 3=High (6-Cylinder). |
| **1** | 0..7 | Detroit Voith Secondary Water Retarder | `uint8` | $0.4$ | $0.0$ | % | 0.0 to 100.0 | Retarder braking torque percentage. |
| **2..3** | 0..15 | Detroit Engine Retardation Power | `uint16` LE | $0.1$ | $0.0$ | kW | 0.0 to 6,553.5 | Calculated braking power absorbed. |
| **4..7** | 0..31 | Reserved | `bytes4` | Raw | 0 | N/A | N/A | Detroit safety status word. |

#### 3. Detroit MCM Injector Quantity Balancing
- **PGN:** `65380 (0xFF64)` — Proprietary B (GE=`0x64`, SA=`0x00` MCM21T)
- **CAN ID:** `0x18FF6400`
- **Cycle Rate:** 200 ms

| Byte Index | Bit Range | Parameter Name | Raw Type | Scaling | Offset | Unit | Range | Description |
|---|---|---|---|---|---|---|---|---|
| **0** | 0..7 | Detroit Cyl 1 Fuel Offset Trim | `uint8` | $0.05$ | $-6.4$ | mg/stroke | -6.4 to +6.35 | Smooth running correction Cyl 1. |
| **1** | 0..7 | Detroit Cyl 2 Fuel Offset Trim | `uint8` | $0.05$ | $-6.4$ | mg/stroke | -6.4 to +6.35 | Smooth running correction Cyl 2. |
| **2** | 0..7 | Detroit Cyl 3 Fuel Offset Trim | `uint8` | $0.05$ | $-6.4$ | mg/stroke | -6.4 to +6.35 | Smooth running correction Cyl 3. |
| **3** | 0..7 | Detroit Cyl 4 Fuel Offset Trim | `uint8` | $0.05$ | $-6.4$ | mg/stroke | -6.4 to +6.35 | Smooth running correction Cyl 4. |
| **4** | 0..7 | Detroit Cyl 5 Fuel Offset Trim | `uint8` | $0.05$ | $-6.4$ | mg/stroke | -6.4 to +6.35 | Smooth running correction Cyl 5. |
| **5** | 0..7 | Detroit Cyl 6 Fuel Offset Trim | `uint8` | $0.05$ | $-6.4$ | mg/stroke | -6.4 to +6.35 | Smooth running correction Cyl 6. |
| **6..7** | 0..15 | Detroit Amplified Rail Pressure (APCRS)| `uint16` LE | $0.1$ | $0.0$ | MPa | 0.0 to 6,553.5 | Amplified common rail peak injection pressure. |

---

### 6.6 Mercedes-Benz Actros Architecture
**Target Engines:** OM470, OM471, OM473 In-line 6 (Euro 6 BlueTec 6)  
**Target Controllers:** MCM (Motor Control Module), ACM (Aftertreatment Control Module), CPC (Common Powertrain Controller)

#### 1. Mercedes BlueTec 6 Aftertreatment & DPF Control
- **PGN:** `65450 (0xFFAA)` — Proprietary B (GE=`0xAA`, SA=`0x27` ACM)
- **CAN ID:** `0x18FFAA27`
- **Cycle Rate:** 100 ms

| Byte Index | Bit Range | Parameter Name | Raw Type | Scaling | Offset | Unit | Range | Description |
|---|---|---|---|---|---|---|---|---|
| **0..1** | 0..15 | Mercedes DPF Soot Load Index | `uint16` LE | $0.1$ | $0.0$ | % | 0.0 to 6,553.5 | Particulate filter soot loading percentage. |
| **2** | 0..7 | Mercedes BlueTec Regeneration Mode | `uint8` | Enum | 0 | Enum | 0 to 255 | 0x00=Inaktiv (Passive), 0x01=Regeneration Fahren (Highway), 0x02=Regeneration Stand (Parked), 0x03=Gesperrt (Inhibit Switch Active), 0x04=Stoerung (Fault). |
| **3..4** | 0..15 | Mercedes AdBlue Dosierrate Istwert | `uint16` LE | $0.01$ | $0.0$ | g/s | 0.00 to 655.35 | Actual urea injection mass rate. |
| **5** | 0..7 | Mercedes AdBlue Fuellstand Kombi | `uint8` | $0.4$ | $0.0$ | % | 0.0 to 100.0 | AdBlue tank level reported to instrument cluster. |
| **6** | 0..7 | Mercedes AdBlue Qualitaet / Konzentration| `uint8` | $0.1$ | $0.0$ | % | 0.0 to 25.5 | DEF concentration measurement (Soll: 32.5%). |
| **7** | 0..7 | Mercedes SCR Katalysator Wirkungsgrad | `uint8` | $0.4$ | $0.0$ | % | 0.0 to 100.0 | DeNOx catalytic conversion efficiency percentage. |

#### 2. Mercedes High Performance Engine Brake (HPEB) & Retarder
- **PGN:** `65455 (0xFFAF)` — Proprietary B (GE=`0xAF`, SA=`0x00` MCM / `0x10` Retarder)
- **CAN ID:** `0x18FFAF00`
- **Cycle Rate:** 50 ms

| Byte Index | Bit Range | Parameter Name | Raw Type | Scaling | Offset | Unit | Range | Description |
|---|---|---|---|---|---|---|---|---|
| **0** | 0..7 | Mercedes HPEB Motorbremse Stufe | `uint8` | Enum | 0 | Enum | 0 to 3 | 0=Aus, 1=Stufe 1 (Dekompression 30%), 2=Stufe 2 (HPEB 60%), 3=Stufe 3 (Volllast Dauerbremse 100%). |
| **1** | 0..7 | Mercedes Retarder Bremsmomentanforderung| `uint8` | $0.4$ | $0.0$ | % | 0.0 to 100.0 | Retarder braking torque setpoint. |
| **2..3** | 0..15 | Mercedes Retarder Kuehlmitteltemperatur | `uint16` LE | $0.03125$ | $-273.0$ | °C | -273.0 to +1,775.0 | Retarder heat exchanger coolant temp. |
| **4..7** | 0..31 | Mercedes Dauerbremse Statuswort | `bytes4` | Raw | 0 | N/A | N/A | Continuous braking safety and ABS intervention status. |

#### 3. Mercedes Laufruheregelung / Zylinder-Ausgleich (MCM)
- **PGN:** `65460 (0xFFB4)` — Proprietary B (GE=`0xB4`, SA=`0x00` MCM)
- **CAN ID:** `0x18FFB400`
- **Cycle Rate:** 100 ms

| Byte Index | Bit Range | Parameter Name | Raw Type | Scaling | Offset | Unit | Range | Description |
|---|---|---|---|---|---|---|---|---|
| **0** | 0..7 | Zylinder 1 Mengenkorrektur | `uint8` | $0.1$ | $-12.8$ | mm³/Hub | -12.8 to +12.7 | Injection volume correction Cyl 1. |
| **1** | 0..7 | Zylinder 2 Mengenkorrektur | `uint8` | $0.1$ | $-12.8$ | mm³/Hub | -12.8 to +12.7 | Injection volume correction Cyl 2. |
| **2** | 0..7 | Zylinder 3 Mengenkorrektur | `uint8` | $0.1$ | $-12.8$ | mm³/Hub | -12.8 to +12.7 | Injection volume correction Cyl 3. |
| **3** | 0..7 | Zylinder 4 Mengenkorrektur | `uint8` | $0.1$ | $-12.8$ | mm³/Hub | -12.8 to +12.7 | Injection volume correction Cyl 4. |
| **4** | 0..7 | Zylinder 5 Mengenkorrektur | `uint8` | $0.1$ | $-12.8$ | mm³/Hub | -12.8 to +12.7 | Injection volume correction Cyl 5. |
| **5** | 0..7 | Zylinder 6 Mengenkorrektur | `uint8` | $0.1$ | $-12.8$ | mm³/Hub | -12.8 to +12.7 | Injection volume correction Cyl 6. |
| **6..7** | 0..15 | Common-Rail Raildruck Istwert | `uint16` LE | $0.1$ | $0.0$ | bar | 0.0 to 6,553.5 | High pressure common rail measured pressure. |

---

## 7. Features Discovered Table

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|---|---|---|---|---|---|---|
| 1 | OBD-II Standard | Mode 01 PID Bitmask Hierarchy | Recursive discovery of supported PIDs in 32-bit blocks (0x00, 0x20, 0x40, 0x60, 0x80, 0xA0, 0xC0, 0xE0). | Single Frame `02 01 <AnchorPID>` | 4-byte bitmask payload representing support for subsequent 32 PIDs. | If bit 0 of anchor PID is 0, terminates query chain. If ECU returns NRC, flags block as unsupported. | SAE J1979-DA / ISO 15031-5 Specification |
| 2 | OBD-II Standard | High-Speed Powertrain Telemetry | Physical transformations for Engine RPM (`(256A+B)/4`), Speed (`A`), Coolant Temp (`A-40`), Throttle (`A*100/255`), Fuel Pressure (`A*3`), MAF (`(256A+B)/100`). | Raw CAN response bytes $A, B, \dots$ | Calibrated floating-point physical telemetry values. | Out of range bytes (e.g. `0xFF` indicator) flagged as `NOT_AVAILABLE`. | SAE J1979 Mode 01 Specification |
| 3 | OBD-II Standard | Advanced Emissions & DPF/DEF PIDs | Extended standard PIDs (0x78-0x7C EGT/DPF, 0x87 DPF Soot Mass, 0x9A DEF level & concentration, 0xA5 DEF Dosing, 0xA6 Odometer). | Raw response bytes | Physical DPF soot grams, DEF dosing g/h, exhaust gas temperatures °C. | Negative pressures and temperatures clamped to signed domain limits. | SAE J1979-DA (2020 Revision) |
| 4 | ISO 14229 UDS | Standard Identification DIDs | Standard DIDs (0xF190 VIN, 0xF188 SW ID, 0xF191 HW ID, 0xF187 Part No, 0xF197 System Name, 0xF1A0..0xF1AF CVN & Flash Counters). | ISO-TP request `0x22 <DID_High> <DID_Low>` | Reassembled multi-frame ASCII strings, BCD dates, and raw CVN checksums. | NRC 0x31 (RequestOutOfRange) or NRC 0x22 (ConditionsNotCorrect) handled gracefully. | ISO 14229-1:2020 / ISO 27145 |
| 5 | ISO 14229 UDS | Live Diagnostic Sensor DIDs | Powertrain DIDs (0xF010/0x0100 Battery Voltage, 0x0101 Ignition, 0x0102 Coolant, 0x0103 RPM, 0x0104 Pedal, 0x0105 Brake Pressure, 0x0106 Steering Angle). | ISO-TP request `0x22 <DID>` | Scaled high-precision floating point telemetry. | Returns `SignalStatus.ERROR` on sensor hardware malfunction flags. | ISO 14229 UDS Diagnostic Catalog |
| 6 | Architecture | Multi-Rate Poller Scheduler | Token-bucket rate-limiting active scheduler separating Fast (10-20ms), Medium (100-250ms), and Slow (1000-5000ms) loops. | Configured poll list with target update frequencies | Time-multiplexed CAN frames maintaining bus load $\le 40\%$. | If CAN TX buffer full, defers frame to next clock tick without starvation. | Architecture Analysis |
| 7 | Architecture | Robust Request/Response FSM | State machine handling ISO-TP segmentation, $P2_{\text{max}}$ (50ms/2.0s), and $P2^*$ (5.0s on NRC 0x78) timing extensions. | CAN RX frames, timer tick events | Emits completed telemetry or transitions to retry backoff. | NRC 0x78 extends deadline by 5.0s; NRC 0x21 triggers exponential backoff. | ISO 14229-2 / ISO 15765-2 Specification |
| 8 | J1939 Proprietary | Proprietary A (PGN 61184) Routing | Unicast PDU1 destination-specific messaging for OEM service overrides and manual tests. | 29-bit CAN frame with $\text{PF}=0xEF$, $\text{PS}=\text{DA}$ | Directed command payload delivered exclusively to target controller address. | Rejects frame if DA does not match expected destination ECU. | SAE J1939-21 Specification |
| 9 | J1939 Proprietary | Proprietary B (PGNs 65280-65535) Broadcast | Global broadcast PDU2 telemetry decoding for OEM custom parameters. | 29-bit CAN frame with $\text{PF}=0xFF$, $\text{PS}=\text{GE}$ | Signal-level telemetry points routed to telemetry buffer and UI. | Unrecognized GE values dropped safely or logged to raw sniffer. | SAE J1939-71 Specification |
| 10 | OEM J1939 | Cummins CM2350/CM2450 Decoder | Proprietary PGN 65300 (DPF soot mass, active regen status, inhibit switch, DEF dosing rate) and PGN 65303 (Cyl 1..6 balancing trim). | PGN 65300 / 65303 CAN frames | Physical soot mass in grams, dosing rate in g/s, trim in mg/stroke. | Bitmask values `0b10` / `0b11` decoded as Error / Not Available. | Cummins OEM Diagnostic Database |
| 11 | OEM J1939 | Caterpillar ADEM IV/V Decoder | Proprietary PGN 65320 (ARD air/fuel pressure, flame temp, DPF soot index, DEF quality) and PGN 65325 (HEUI injection balance trim). | PGN 65320 / 65325 CAN frames | Flame temp °C, soot load %, fuel trim mm³/stroke. | ARD flame temp raw `0xFF` decoded as Sensor Open/Fault. | Caterpillar Commercial Engine Specification |
| 12 | OEM J1939 | Scania EMS S6/S7/S8 & Retarder Decoder | Proprietary PGN 65400 (DPF soot, AdBlue dosing, refractometer quality), PGN 65410 (Retarder stages 0-5, oil temp), PGN 65420 (Cyl 1..8 balancing). | PGN 65400 / 65410 / 65420 CAN frames | Soot grams, AdBlue %, retarder torque %, oil temp °C, smooth running mm³/stroke. | Retarder oil temp `0xFFFF` decoded as Sensor Uninstalled/Fault. | Scania Truck & Bus Diagnostic Manual |
| 13 | OEM J1939 | Volvo Trucks D13K & VEB+ Decoder | Proprietary PGN 65350 (DPF soot level, regen state, DEF concentration), PGN 65352 (VEB+ stages 0-3, retarder torque), PGN 65355 (Cyl 1..6 trim). | PGN 65350 / 65352 / 65355 CAN frames | DPF grams, VEB+ state, braking torque Nm, trim mg/stroke. | High exhaust temp warning triggers UI visual alert. | Volvo Trucks Heavy Duty Diagnostic Manual |
| 14 | OEM J1939 | Detroit Diesel MCM/ACM Decoder | Proprietary PGN 65370 (DPF soot/ash mass, DEF quality), PGN 65375 (Jake Brake stages 0-3), PGN 65380 (Cyl 1..6 fuel trim). | PGN 65370 / 65375 / 65380 CAN frames | Soot grams, ash grams, DEF quality enum, Jake stage, APCRS rail pressure MPa. | DEF quality status `0x03` (Water/Tamper) triggers critical alert. | Detroit Diesel Electronic Manuals |
| 15 | OEM J1939 | Mercedes-Benz Actros OM471 Decoder | Proprietary PGN 65450 (BlueTec 6 soot index, AdBlue dosing, DeNOx efficiency), PGN 65455 (HPEB stages 0-3), PGN 65460 (Laufruheregelung Cyl 1..6). | PGN 65450 / 65455 / 65460 CAN frames | Soot load %, AdBlue g/s, DeNOx %, HPEB stage, Mengenkorrektur mm³/Hub. | Regeneration mode `0x03` (Gesperrt) indicates driver inhibit. | Mercedes-Benz Star Diagnosis Documentation |

---

## 8. Edge Cases & Error Behaviors

| # | Feature | Input / Condition | Observed / Documented Behavior | Error Handling & Safety Mitigation |
|---|---|---|---|---|
| 1 | Mode 01 Support Bitmap | ECU returns all zeroes for PID 0x00 (`00 00 00 00`). | No standard PIDs supported (e.g. non-OBD gateway or auxiliary controller). | Poller marks Mode 01 scanning complete for that ECU address; logs warning and switches to UDS DID queries. |
| 2 | Mode 01 Support Bitmap | Bit 0 of PID 0x00 is `0` (PID 0x20 unsupported), but tool attempts query of PID 0x21. | ECU responds with Negative Response (`0x7F 0x01 0x12` SubFunctionNotSupported or `0x7F 0x01 0x31` RequestOutOfRange). | Poller catches NRC, drops PID 0x21 from active schedule, and prevents further transmission attempts. |
| 3 | UDS DID Multi-Frame | VIN DID 0xF190 queried on slow ECU requiring ISO-TP Consecutive Frames. | First Frame `10 14 62 F1 90 ...` sent by ECU. Poller receives FF, transmits Flow Control `30 00 00 00 00 00 00 00` via TxSafetyGateway. | Reassembles 17 ASCII bytes. If consecutive frames missing after 1000ms, triggers `IsoTpReassemblyTimeout` and retries. |
| 4 | ISO 14229 P2* Extension | Long-running routine or DID read triggers `0x7F 0x22 0x78` (Response Pending). | Poller detects NRC 0x78, pauses timeout deadline, and grants $P2^* = 5000\text{ ms}$ window. | Does not raise timeout error while ECU is actively processing; waits for final positive/negative response. |
| 5 | Speed Interlock Gate | Diagnostic service attempting critical write (DID 0x2E / Routine 0x31 / DPF Forced Regen PGN 61184) while vehicle speed is 45 km/h. | `TxSafetyGateway` checks current vehicle speed (> 0.5 km/h) and blocks transmission immediately. | Raises `SpeedInterlockError (SPEED_INTERLOCK_ACTIVE)`. Prevents dangerous actuator manipulation in motion. |
| 6 | J1939 Multi-Packet BAM | DM1 active DTC list (PGN 65226) exceeds 8 bytes (e.g. 5 active DTCs = 22 bytes payload). | Broadcast Announce Message (BAM) PGN 60416 (`0xEC00`) received with total size 22 bytes, followed by PGN 60160 (`0xEB00`) sequence packets. | `J1939Transport` reassembles all packets into 22-byte payload and forwards to `J1939DiagnosticService` for multi-DTC parsing. |
| 7 | DEF Sensor Out-of-Range | DEF level input reports raw byte `0xFE` (Error indicator) or `0xFF` (Not available). | Formula $A \cdot \frac{100}{255}$ would evaluate to 99.6% / 100.0% erroneously. | Decoder checks for `0xFE`/`0xFF` guard bytes and returns `SignalStatus.NOT_AVAILABLE` or `SignalStatus.ERROR` instead of false valid reading. |
| 8 | Cylinder Balancing Trim Clamp | Common rail injector trim raw byte reports `0x00` ($-12.8\text{ mg/stroke}$) or `0xFF` ($+12.7\text{ mg/stroke}$) on faulty cylinder. | Decoder computes physical delta and checks against engine mechanical warning limits ($\pm 5.0\text{ mg/stroke}$). | Flags severe cylinder unbalance warning on UI, assisting technician in diagnosing failing injector solenoid/needle. |
| 9 | Duplicate Diagnostic CAN IDs | Multiple ECUs (Engine `0x7E8`, Transmission `0x7E9`, Retarder `0x7EA`) respond to functional broadcast `0x7DF`. | Individual responses arrive interleaved on CAN bus within 20 ms. | Poller matches each response to its respective source CAN ID, demultiplexing per-controller telemetry streams without cross-contamination. |
| 10 | Retarder Oil Temperature Underflow | Retarder oil temperature sensor disconnected, reporting raw `0xFFFF` on Scania PGN 65410. | Scaling formula $(0.03125 \cdot 65535) - 273 = 1775.0^\circ\text{C}$ would show physically impossible temperature. | Decoder intercepts `0xFFFF` sentinel value, classifying signal status as `SignalStatus.NOT_AVAILABLE` with 0.0 value. |
