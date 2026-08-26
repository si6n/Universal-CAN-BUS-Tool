"""Unit tests for NMEA 2000 Fast Packet and PGN decoders."""

from src.core.models.can_frame import CanFrame
from src.protocols.nmea2000.fast_packet import Nmea2000FastPacketDecoder
from src.protocols.nmea2000.pgn_library import Nmea2000PgnDecoder


def test_n2k_fast_packet_reassembly() -> None:
    decoder = Nmea2000FastPacketDecoder()

    # Frame 0: Seq 0, Index 0 -> Header = 0x00, Total Bytes = 16
    f0_data = b"\x00\x10" + b"\x00\x01\x02\x03\x04\x05"
    f0 = CanFrame.create(
        channel_id="n2k",
        arbitration_id=0x19F20100,  # PGN 127489 (0x1F201)
        data=f0_data,
        is_extended=True,
    )
    res0 = decoder.handle_rx_frame(f0)
    assert res0 is None

    # Frame 1: Seq 0, Index 1 -> Header = 0x01, 7 bytes payload
    f1_data = b"\x01" + b"\x06\x07\x08\x09\x0a\x0b\x0c"
    f1 = CanFrame.create(
        channel_id="n2k",
        arbitration_id=0x19F20100,
        data=f1_data,
        is_extended=True,
    )
    res1 = decoder.handle_rx_frame(f1)
    assert res1 is None

    # Frame 2: Seq 0, Index 2 -> Header = 0x02, remaining 3 bytes payload
    f2_data = b"\x02" + b"\x0d\x0e\x0f\xff\xff\xff\xff"
    f2 = CanFrame.create(
        channel_id="n2k",
        arbitration_id=0x19F20100,
        data=f2_data,
        is_extended=True,
    )
    res2 = decoder.handle_rx_frame(f2)
    assert res2 is not None

    assert res2.pgn == 127489
    assert len(res2.data) == 16
    assert res2.data == bytes(range(16))


def test_decode_engine_rapid() -> None:
    # Instance 0, Speed 2000 RPM (2000 / 0.25 = 8000 = 0x1F40 -> 0x40, 0x1F)
    # Boost 150 kPa = 150000 Pa / 100 = 1500 = 0x05DC -> 0xDC, 0x05
    # Tilt 10%
    data = b"\x00\x40\x1f\xdc\x05\x0a\xff\xff"
    res = Nmea2000PgnDecoder.decode_engine_rapid(data)
    assert res is not None
    assert res.engine_instance == 0
    assert res.engine_speed_rpm == 2000.0
    assert res.boost_pressure_kpa == 150.0
    assert res.tilt_trim_percent == 10


def test_decode_fluid_level() -> None:
    # Fluid Type: Fuel (0), Instance: 1 -> Byte 0 = 0x10
    # Level: 75.0% -> 75.0 / 0.004 = 18750 = 0x493E -> 0x3E, 0x49
    # Capacity: 500 L -> 500 / 0.1 = 5000 = 0x1388 -> 0x88, 0x13, 0x00, 0x00
    data = b"\x10\x3e\x49\x88\x13\x00\x00\xff"
    res = Nmea2000PgnDecoder.decode_fluid_level(data)
    assert res is not None
    assert res.fluid_type == "fuel"
    assert res.fluid_instance == 1
    assert res.level_percent == 75.0
    assert res.capacity_liters == 500.0
