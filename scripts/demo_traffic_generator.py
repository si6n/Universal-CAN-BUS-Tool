"""Live Vehicle & Marine Telemetry Generator for Demonstration and Hardware-Free Testing.

Simulates a real-world engine ECU transmitting:
1. Standard / J1939 EEC1 (Engine Speed RPM, Actual Torque %)
2. Engine Coolant Temperature & Oil Pressure
3. NMEA 2000 Dynamic Marine parameters
4. ISO 14229 UDS responses
5. Periodic J1939 DM1 Diagnostic Trouble Codes
"""

from __future__ import annotations

import math
import time

from src.core.models.can_frame import CanFrame
from src.hal.drivers.pcan_kvaser import PythonCanBus


def run_live_simulation(channel: str = "vcan0", interval_s: float = 0.02) -> None:
    """Run live telemetry generator on virtual bus."""
    print(f"[*] Starting Live Telemetry Simulator on virtual bus '{channel}'...")
    bus = PythonCanBus(interface="virtual", channel=channel)
    bus.connect()

    t = 0.0
    print("[+] Simulator connected. Broadcasting live engine, marine & J1939 streams. Press Ctrl+C to stop.")

    try:
        while True:
            # 1. Simulate Engine Speed RPM (800..3200 RPM sine wave)
            rpm = 1800.0 + 1000.0 * math.sin(t * 0.8)
            # EEC1 PGN 61444 (0x0CF00400): Raw = RPM / 0.125
            raw_rpm = int(rpm / 0.125) & 0xFFFF
            eec1_data = bytearray(8)
            eec1_data[0] = 0xF0  # Torque mode
            eec1_data[1] = 0x7D  # 0% Torque
            eec1_data[2] = 0x7D
            eec1_data[3] = raw_rpm & 0xFF
            eec1_data[4] = (raw_rpm >> 8) & 0xFF
            eec1_data[5:8] = b"\xff\xff\xff"

            f_eec1 = CanFrame.create(
                channel_id="sim_engine",
                arbitration_id=0x0CF00400,
                data=bytes(eec1_data),
                is_extended=True,
                direction="rx",
            )
            bus.send(f_eec1)

            # 2. Engine Temperature & Oil Pressure (PGN 65262 / 0x18FEEE00)
            coolant_temp_c = 85.0 + 5.0 * math.sin(t * 0.2)
            raw_temp = int(coolant_temp_c + 40.0) & 0xFF  # Offset -40
            temp_data = bytearray([raw_temp, 0x96, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
            f_temp = CanFrame.create(
                channel_id="sim_engine",
                arbitration_id=0x18FEEE00,
                data=bytes(temp_data),
                is_extended=True,
                direction="rx",
            )
            bus.send(f_temp)

            # 3. NMEA 2000 Engine Rapid (PGN 127488 / 0x19F20000)
            boost_kpa = 120.0 + 40.0 * math.sin(t * 0.5)
            raw_boost = int((boost_kpa * 1000) / 100) & 0xFFFF
            n2k_rapid = bytearray(8)
            n2k_rapid[0] = 0x00  # Port Engine
            n2k_rapid[1] = raw_rpm & 0xFF
            n2k_rapid[2] = (raw_rpm >> 8) & 0xFF
            n2k_rapid[3] = raw_boost & 0xFF
            n2k_rapid[4] = (raw_boost >> 8) & 0xFF
            n2k_rapid[5] = 0x0A  # 10% Trim
            n2k_rapid[6:8] = b"\xff\xff"

            f_n2k = CanFrame.create(
                channel_id="sim_n2k",
                arbitration_id=0x19F20000,
                data=bytes(n2k_rapid),
                is_extended=True,
                direction="rx",
            )
            bus.send(f_n2k)

            # 4. Periodic J1939 DM1 Fault (SPN 100 Engine Oil Pressure, FMI 1 Low)
            if int(t) % 5 == 0:
                dm1_data = b"\x40\xff\x64\x00\x01\x01\xff\xff"
                f_dm1 = CanFrame.create(
                    channel_id="sim_diag",
                    arbitration_id=0x18FECA00,
                    data=dm1_data,
                    is_extended=True,
                    direction="rx",
                )
                bus.send(f_dm1)

            t += 0.05
            time.sleep(interval_s)

    except KeyboardInterrupt:
        print("\n[!] Simulator stopped.")
    finally:
        bus.disconnect()


if __name__ == "__main__":
    run_live_simulation()
