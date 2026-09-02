"""Volvo Penta EDC (MID 128 PID/SID) & EVC Marine Diagnostic Decoder.

Complies with Volvo Penta EDC1/4/7 and EVC-A..E specifications (MASTER_PLAN.md Section 8).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from src.core.logging import get_logger
from src.core.models.can_frame import CanFrame

logger = get_logger("protocols.volvo")

MID_ENGINE_ECU: int = 128

VOLVO_PIDS: dict[int, str] = {
    100: "Engine Oil Pressure",
    105: "Intake Manifold Temperature",
    110: "Engine Coolant Temperature",
    190: "Engine Speed",
}

VOLVO_SIDS: dict[int, str] = {
    1: "Injector Cylinder 1",
    2: "Injector Cylinder 2",
    3: "Injector Cylinder 3",
    4: "Injector Cylinder 4",
    5: "Injector Cylinder 5",
    6: "Injector Cylinder 6",
    21: "Engine Position Sensor (Crankshaft)",
    22: "Timing Sensor (Camshaft)",
    254: "Engine Control Module Microcontroller",
}

VOLVO_PSIDS: dict[int, str] = {
    96: "Fuel Rail Pressure High-Pressure System",
    98: "Boost Pressure Turbocharger Actuator (VGT)",
}


@dataclass(slots=True)
class VolvoDtc:
    """Volvo Penta EDC / EVC Diagnostic Trouble Code."""

    code_type: str  # "PID" | "SID" | "PPID" | "PSID"
    code_id: int
    fmi: int
    description: str
    is_active: bool = True


@dataclass(slots=True)
class VolvoEvcHelmState:
    """Volvo Penta EVC Control Lever and Powertrim Telemetry (PGN 65360 / 65361)."""

    lever_position_percent: float  # -100% (Full Reverse) .. +100% (Full Ahead)
    gear_state: str  # "NEUTRAL" | "AHEAD" | "ASTERN"
    trim_angle_deg: float  # -10.0 .. +15.0 deg
    rudder_angle_deg: float  # -45.0 .. +45.0 deg
    station_active: bool


class VolvoPentaDecoder:
    """Parser for Volvo Penta EDC J1587/J1939 fault payloads and EVC Marine CAN messages."""

    PGN_EVC_HELM: ClassVar[int] = 65360
    PGN_EVC_TRIM_RUDDER: ClassVar[int] = 65361

    @classmethod
    def parse_edc_fault_payload(cls, data: bytes) -> list[VolvoDtc]:
        """Parse Volvo Penta MID 128 PID/SID fault code payload."""
        dtcs: list[VolvoDtc] = []
        if len(data) < 3:
            return dtcs

        # Format: [Type (0=PID, 1=SID, 2=PPID, 3=PSID), Code_ID, FMI | (Active << 7)]
        idx = 0
        while idx + 3 <= len(data):
            code_type_code = data[idx]
            code_id = data[idx + 1]
            fmi_raw = data[idx + 2]

            fmi = fmi_raw & 0x1F
            is_active = bool((fmi_raw >> 7) & 0x01)

            if code_type_code == 0:
                type_str = "PID"
                desc = VOLVO_PIDS.get(code_id, f"PID {code_id}")
            elif code_type_code == 1:
                type_str = "SID"
                desc = VOLVO_SIDS.get(code_id, f"SID {code_id}")
            elif code_type_code == 3:
                type_str = "PSID"
                desc = VOLVO_PSIDS.get(code_id, f"PSID {code_id}")
            else:
                type_str = "PPID"
                desc = f"PPID {code_id}"

            dtcs.append(
                VolvoDtc(
                    code_type=type_str,
                    code_id=code_id,
                    fmi=fmi,
                    description=desc,
                    is_active=is_active,
                )
            )
            idx += 3

        return dtcs

    @classmethod
    def decode_evc_can_frame(cls, frame: CanFrame) -> VolvoEvcHelmState | None:
        """Decode Volvo Penta EVC proprietary CAN frames (PGN 65360 / 65361)."""
        if not frame.is_extended or len(frame.data) < 8:
            return None

        # Reject Extended Data Page frames: the EVC PGNs live in the standard
        # PGN space and an 18-bit mask would otherwise alias EDP=1 IDs onto
        # them (false-decode of unrelated traffic).
        if (frame.arbitration_id >> 25) & 0x01:
            return None

        pgn = (frame.arbitration_id >> 8) & 0x3FFFF

        if pgn == cls.PGN_EVC_HELM:
            # Byte 0: Lever position (-100% to +100%, 1% / bit, offset -125)
            raw_lever = frame.data[0]
            lever_pct = float(raw_lever - 125) if raw_lever <= 250 else 0.0

            # Byte 1: Gear (0=Neutral, 1=Ahead, 2=Astern)
            gear_code = frame.data[1] & 0x03
            gear = "NEUTRAL" if gear_code == 0 else ("AHEAD" if gear_code == 1 else "ASTERN")

            # Byte 2: Station flags
            station_active = bool(frame.data[2] & 0x01)

            # Byte 3..4: Powertrim angle (0.1 deg / bit, offset -50 deg)
            raw_trim = int.from_bytes(frame.data[3:5], byteorder="little")
            trim_deg = (raw_trim * 0.1) - 50.0 if raw_trim < 0xFFFF else 0.0

            # Byte 5..6: Rudder angle (0.1 deg / bit, offset -90 deg)
            raw_rudder = int.from_bytes(frame.data[5:7], byteorder="little")
            rudder_deg = (raw_rudder * 0.1) - 90.0 if raw_rudder < 0xFFFF else 0.0

            return VolvoEvcHelmState(
                lever_position_percent=lever_pct,
                gear_state=gear,
                trim_angle_deg=trim_deg,
                rudder_angle_deg=rudder_deg,
                station_active=station_active,
            )

        if pgn == cls.PGN_EVC_TRIM_RUDDER:
            # Byte 0..1: Powertrim angle (0.1 deg / bit, offset -50 deg)
            raw_trim = int.from_bytes(frame.data[0:2], byteorder="little")
            trim_deg = (raw_trim * 0.1) - 50.0 if raw_trim < 0xFFFF else 0.0

            # Byte 2..3: Rudder angle (0.1 deg / bit, offset -90 deg)
            raw_rudder = int.from_bytes(frame.data[2:4], byteorder="little")
            rudder_deg = (raw_rudder * 0.1) - 90.0 if raw_rudder < 0xFFFF else 0.0

            # Byte 4: Station flags
            station_active = bool(frame.data[4] & 0x01) if len(frame.data) > 4 else True

            return VolvoEvcHelmState(
                lever_position_percent=0.0,
                gear_state="NEUTRAL",
                trim_angle_deg=trim_deg,
                rudder_angle_deg=rudder_deg,
                station_active=station_active,
            )

        return None
