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


def _fp_first_frame(total_bytes: int, pgn_id: int = 0x19F20100, seq: int = 0, payload: bytes = b"") -> CanFrame:
    """Fast Packet index-0 frame: header = seq<<5, total length in byte 1."""
    header = (seq << 5) & 0xFF
    data = bytes([header, total_bytes]) + payload[:6] + b"\xff" * max(0, 6 - len(payload[:6]))
    return CanFrame.create(
        channel_id="n2k",
        arbitration_id=pgn_id,
        data=data,
        is_extended=True,
    )


def _fp_next_frame(index: int, payload: bytes, pgn_id: int = 0x19F20100, seq: int = 0) -> CanFrame:
    header = ((seq << 5) | (index & 0x1F)) & 0xFF
    data = bytes([header]) + payload + b"\xff" * (7 - len(payload))
    return CanFrame.create(
        channel_id="n2k",
        arbitration_id=pgn_id,
        data=data[:8],
        is_extended=True,
    )


def test_n2k_boundary_223_bytes_accepted() -> None:
    """223 bytes = 6 + 7*31 is the maximum legal Fast Packet size and must complete."""
    decoder = Nmea2000FastPacketDecoder()
    payload = bytes((i % 256) for i in range(223))

    assert decoder.handle_rx_frame(_fp_first_frame(223, payload=payload)) is None
    res = None
    for idx in range(1, 32):
        res = decoder.handle_rx_frame(_fp_next_frame(idx, payload[6 + (idx - 1) * 7 : 6 + idx * 7]))
    assert res is not None
    assert res.data == payload


def test_n2k_boundary_224_bytes_rejected() -> None:
    """224 bytes exceeds the 6+7*31 limit — the session must never open."""
    decoder = Nmea2000FastPacketDecoder()
    assert decoder.handle_rx_frame(_fp_first_frame(224)) is None
    # A subsequent CF finds no session and is dropped silently
    assert decoder.handle_rx_frame(_fp_next_frame(1, b"\x01" * 7)) is None
    assert len(decoder._sessions) == 0


def test_n2k_min_boundary_8_bytes_rejected() -> None:
    """Below 9 bytes there is no need for Fast Packet at all — rejected."""
    decoder = Nmea2000FastPacketDecoder()
    assert decoder.handle_rx_frame(_fp_first_frame(8)) is None
    assert len(decoder._sessions) == 0


def test_n2k_sequence_mismatch_drops_session() -> None:
    """An out-of-order CF must evict the session — partial data never completes."""
    decoder = Nmea2000FastPacketDecoder()
    decoder.handle_rx_frame(_fp_first_frame(20))

    # Skip index 1, deliver index 2
    assert decoder.handle_rx_frame(_fp_next_frame(2, b"\x41" * 7)) is None
    # Session evicted: even the correct next index finds nothing
    assert decoder.handle_rx_frame(_fp_next_frame(1, b"\x42" * 7)) is None
    assert len(decoder._sessions) == 0


def test_n2k_index0_restart_drops_stale_session() -> None:
    """A mid-transfer restart (index 0) replaces stale state — new data wins."""
    decoder = Nmea2000FastPacketDecoder()
    decoder.handle_rx_frame(_fp_first_frame(20))
    decoder.handle_rx_frame(_fp_next_frame(1, b"\x41" * 7))  # in-flight, 13/20 bytes

    # Sender restarts with a fresh 16-byte message for the same key
    payload = bytes(range(16))
    restarted = decoder.handle_rx_frame(_fp_first_frame(16, payload=payload))
    assert restarted is None
    assert len(decoder._sessions) == 1  # stale dropped, one fresh session

    assert decoder.handle_rx_frame(_fp_next_frame(1, payload[6:13])) is None
    res = decoder.handle_rx_frame(_fp_next_frame(2, payload[13:16]))
    assert res is not None
    assert res.data == payload  # the RESTARTED payload, not stale bytes


def test_n2k_timeout_evicts_session() -> None:
    """500 ms of silence must evict an in-flight session."""
    import time as _time

    decoder = Nmea2000FastPacketDecoder()
    decoder.handle_rx_frame(_fp_first_frame(20))
    assert len(decoder._sessions) == 1

    _time.sleep(0.55)
    # Any subsequent frame triggers the expired-session sweep first
    decoder.handle_rx_frame(_fp_next_frame(1, b"\x41" * 7))
    assert len(decoder._sessions) == 0
