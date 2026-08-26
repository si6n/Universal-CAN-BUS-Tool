"""NMEA 2000 Standard Marine PGN Decoders (Engine Rapid, Dynamic, Transmission, Fluid)."""

from __future__ import annotations

from dataclasses import dataclass

from src.core.logging import get_logger

logger = get_logger("protocols.nmea2000.pgn")

PGN_ENGINE_RAPID: int = 127488
PGN_ENGINE_DYNAMIC: int = 127489
PGN_TRANSMISSION_DYNAMIC: int = 127493
PGN_FLUID_LEVEL: int = 127497


@dataclass(slots=True)
class EngineRapidParameters:
    """NMEA 2000 PGN 127488 (Engine Parameters, Rapid Update)."""

    engine_instance: int
    engine_speed_rpm: float | None
    boost_pressure_kpa: float | None
    tilt_trim_percent: int | None


@dataclass(slots=True)
class EngineDynamicParameters:
    """NMEA 2000 PGN 127489 (Engine Parameters, Dynamic - Fast Packet)."""

    engine_instance: int
    oil_pressure_kpa: float | None
    oil_temp_c: float | None
    coolant_temp_c: float | None
    alternator_voltage_v: float | None
    fuel_rate_lph: float | None
    total_engine_hours: float | None
    engine_load_percent: int | None


@dataclass(slots=True)
class TransmissionParameters:
    """NMEA 2000 PGN 127493 (Transmission Parameters, Dynamic - Fast Packet)."""

    transmission_instance: int
    gear: str  # "neutral" | "forward" | "reverse" | "unknown"
    oil_pressure_kpa: float | None
    oil_temp_c: float | None


@dataclass(slots=True)
class FluidLevelParameters:
    """NMEA 2000 PGN 127497 (Trip Parameters, Engine / Fluid Level)."""

    fluid_type: str  # "fuel" | "fresh_water" | "waste_water" | "oil" | "black_water"
    fluid_instance: int
    level_percent: float | None
    capacity_liters: float | None


FLUID_TYPES: dict[int, str] = {
    0: "fuel",
    1: "fresh_water",
    2: "waste_water",
    3: "live_well",
    4: "oil",
    5: "black_water",
}

GEAR_TYPES: dict[int, str] = {
    0: "neutral",
    1: "forward",
    2: "reverse",
}


class Nmea2000PgnDecoder:
    """Parser for common Marine NMEA 2000 PGNs."""

    @classmethod
    def decode_engine_rapid(cls, data: bytes) -> EngineRapidParameters | None:
        """Decode PGN 127488 (8 bytes)."""
        if len(data) < 6:
            return None

        instance = data[0]

        # Engine Speed (Bytes 1..2): 0.25 rpm / bit
        raw_speed = int.from_bytes(data[1:3], byteorder="little")
        speed_rpm = raw_speed * 0.25 if raw_speed < 0xFFFF else None

        # Boost Pressure (Bytes 3..4): 100 Pa / bit -> / 1000 = 0.1 kPa
        raw_boost = int.from_bytes(data[3:5], byteorder="little")
        boost_kpa = (raw_boost * 100) / 1000.0 if raw_boost < 0xFFFF else None

        # Tilt / Trim (Byte 5): 1% / bit (signed int8: -100% .. +100%)
        raw_tilt = int.from_bytes(data[5:6], byteorder="little", signed=True)
        tilt_percent = raw_tilt if (-100 <= raw_tilt <= 100) else None

        return EngineRapidParameters(
            engine_instance=instance,
            engine_speed_rpm=speed_rpm,
            boost_pressure_kpa=boost_kpa,
            tilt_trim_percent=tilt_percent,
        )

    @classmethod
    def decode_engine_dynamic(cls, data: bytes) -> EngineDynamicParameters | None:
        """Decode PGN 127489 (Fast Packet ~26 bytes)."""
        if len(data) < 23:
            return None

        instance = data[0]

        # Oil Pressure (Bytes 1..2): 100 Pa / bit -> kPa
        raw_oil_p = int.from_bytes(data[1:3], byteorder="little")
        oil_p_kpa = (raw_oil_p * 100) / 1000.0 if raw_oil_p < 0xFFFF else None

        # Oil Temp (Bytes 3..4): 0.1 K / bit -> °C
        raw_oil_t = int.from_bytes(data[3:5], byteorder="little")
        oil_t_c = (raw_oil_t * 0.1) - 273.15 if raw_oil_t < 0xFFFF else None

        # Coolant Temp (Bytes 5..6): 0.01 K / bit -> °C
        raw_cool_t = int.from_bytes(data[5:7], byteorder="little")
        cool_t_c = (raw_cool_t * 0.01) - 273.15 if raw_cool_t < 0xFFFF else None

        # Alternator Potential / Voltage (Bytes 7..8): 0.01 V / bit
        raw_volt = int.from_bytes(data[7:9], byteorder="little")
        volt_v = raw_volt * 0.01 if raw_volt < 0xFFFF else None

        # Fuel Rate (Bytes 9..10): 0.1 L/h / bit
        raw_fuel_r = int.from_bytes(data[9:11], byteorder="little")
        fuel_lph = raw_fuel_r * 0.1 if raw_fuel_r < 0xFFFF else None

        # Total Engine Hours (Bytes 11..14): 1 s / bit -> hours
        raw_hours = int.from_bytes(data[11:15], byteorder="little")
        hours = raw_hours / 3600.0 if raw_hours < 0xFFFFFFFF else None

        # Engine Load % (Byte 21)
        raw_load = data[21]
        load_pct = raw_load if raw_load <= 100 else None

        return EngineDynamicParameters(
            engine_instance=instance,
            oil_pressure_kpa=oil_p_kpa,
            oil_temp_c=oil_t_c,
            coolant_temp_c=cool_t_c,
            alternator_voltage_v=volt_v,
            fuel_rate_lph=fuel_lph,
            total_engine_hours=hours,
            engine_load_percent=load_pct,
        )

    @classmethod
    def decode_transmission(cls, data: bytes) -> TransmissionParameters | None:
        """Decode PGN 127493 (Fast Packet ~12 bytes)."""
        if len(data) < 6:
            return None

        instance = data[0]
        gear_code = data[1] & 0x03
        gear_str = GEAR_TYPES.get(gear_code, "unknown")

        raw_oil_p = int.from_bytes(data[2:4], byteorder="little")
        oil_p_kpa = (raw_oil_p * 100) / 1000.0 if raw_oil_p < 0xFFFF else None

        raw_oil_t = int.from_bytes(data[4:6], byteorder="little")
        oil_t_c = (raw_oil_t * 0.1) - 273.15 if raw_oil_t < 0xFFFF else None

        return TransmissionParameters(
            transmission_instance=instance,
            gear=gear_str,
            oil_pressure_kpa=oil_p_kpa,
            oil_temp_c=oil_t_c,
        )

    @classmethod
    def decode_fluid_level(cls, data: bytes) -> FluidLevelParameters | None:
        """Decode PGN 127497 (8 bytes)."""
        if len(data) < 8:
            return None

        fluid_type_code = data[0] & 0x0F
        fluid_type_str = FLUID_TYPES.get(fluid_type_code, "other")
        fluid_instance = (data[0] >> 4) & 0x0F

        # Level % (Bytes 1..2): 0.004 % / bit
        raw_level = int.from_bytes(data[1:3], byteorder="little")
        level_pct = raw_level * 0.004 if raw_level < 0xFFFF else None

        # Capacity (Bytes 3..6): 0.1 L / bit
        raw_cap = int.from_bytes(data[3:7], byteorder="little")
        cap_l = raw_cap * 0.1 if raw_cap < 0xFFFFFFFF else None

        return FluidLevelParameters(
            fluid_type=fluid_type_str,
            fluid_instance=fluid_instance,
            level_percent=level_pct,
            capacity_liters=cap_l,
        )
