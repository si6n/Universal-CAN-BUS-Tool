"""Example 02: SAE J1939 DM1 Active Diagnostic Trouble Code (DTC) Monitor.

Decodes SAE J1939 Active Faults (PGN 65226 / 0xFECA).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from src.protocols.j1939.diagnostics import J1939DiagnosticService, PGN_DM1
from src.core.models.can_frame import CanFrame

def main():
    print("=== SAE J1939 DM1 Diagnostic Trouble Code Parser ===")

    # Simulated DM1 Frame: Amber Lamp ON, SPN 651 (Cylinder #1 Injector), FMI 18, OC 14
    sample_dm1_payload = bytes([0x04, 0xFF, 0x8B, 0x02, 0x32, 0x0E, 0xFF, 0xFF])
    frame = CanFrame.create(
        channel_id="j1939_ch0",
        arbitration_id=0x18FECA00,
        data=sample_dm1_payload,
        is_extended=True,
    )

    result = J1939DiagnosticService.parse_dm1_or_dm2(
        data=frame.data,
        pgn=PGN_DM1,
        source_address=frame.arbitration_id & 0xFF,
        timestamp_ns=frame.timestamp_ns
    )
    
    if result:
        print(f"MIL Status: {result.malfunction_indicator_lamp.name} | Amber Lamp: {result.amber_warning_lamp.name}")
        for dtc in result.dtcs:
            print(f"  -> SPN: {dtc.spn} (FMI {dtc.fmi} - {dtc.fmi_description_tr}) - Oluşum Sayısı (OC): {dtc.occurrence_count}")

if __name__ == '__main__':
    main()
