import tempfile
from pathlib import Path

from src.core.models.can_frame import CanFrame
from src.engine.decoder.dbc_decoder import DbcSignalDecoder

# Standard Vector DBC format
SAMPLE_DBC = """VERSION ""

NS_ :

BS_:

BU_: Engine Tester

BO_ 2364539904 EEC1: 8 Engine
 SG_ EngineSpeed : 24|16@1+ (0.125,0) [0|8031.875] "rpm" Vector__XXX
 SG_ ActualEnginePercentTorque : 16|8@1+ (1,-125) [-125|125] "%" Vector__XXX

BO_ 256 StandardMsg: 8 Engine
 SG_ CoolantTemp : 0|8@1+ (1,-40) [-40|215] "degC" Vector__XXX
"""


def test_dbc_standard_and_j1939_decoding() -> None:
    decoder = DbcSignalDecoder.from_dbc_string(SAMPLE_DBC)

    # Test 1: Standard message (ID: 256 / 0x100)
    # Coolant temp raw 120 -> 120 - 40 = 80 degC
    frame_std = CanFrame.create(
        channel_id="ch0",
        arbitration_id=256,
        data=b"\x78\x00\x00\x00\x00\x00\x00\x00",
        is_extended=False,
    )
    decoded_std = decoder.decode_frame(frame_std)
    assert decoded_std is not None
    assert decoded_std.message_name == "StandardMsg"
    assert "CoolantTemp" in decoded_std.signals
    assert decoded_std.signals["CoolantTemp"].value == 80
    assert decoded_std.signals["CoolantTemp"].unit == "degC"

    # Test 2: J1939 EEC1 message (PGN 61444 / 0xF004, Priority 3, SA 0) -> CAN ID: 0x0CF00400 (217056256)
    # Engine speed starts at bit 24 (Byte 3: 0x00 LSB, Byte 4: 0x32 MSB -> 0x3200 = 12800 * 0.125 = 1600.0 RPM)
    frame_j1939 = CanFrame.create(
        channel_id="ch0",
        arbitration_id=0x0CF00400,
        data=b"\xff\xff\xff\x00\x32\xff\xff\xff",
        is_extended=True,
    )
    decoded_j1939 = decoder.decode_frame(frame_j1939)
    assert decoded_j1939 is not None
    assert decoded_j1939.message_name == "EEC1"
    assert "EngineSpeed" in decoded_j1939.signals
    assert decoded_j1939.signals["EngineSpeed"].value == 1600.0
    assert decoded_j1939.signals["EngineSpeed"].unit == "rpm"


def test_unknown_can_id_returns_none() -> None:
    decoder = DbcSignalDecoder.from_dbc_string(SAMPLE_DBC)
    frame_unknown = CanFrame.create(channel_id="ch0", arbitration_id=0x777, data=b"\x00")
    assert decoder.decode_frame(frame_unknown) is None


def test_truncated_frame_rejection() -> None:
    """Verify that frames with data length < DBC message length are rejected without zero-padding."""
    decoder = DbcSignalDecoder.from_dbc_string(SAMPLE_DBC)

    # StandardMsg requires 8 bytes; send only 4 bytes (truncated)
    frame_truncated = CanFrame.create(
        channel_id="ch0",
        arbitration_id=256,
        data=b"\x78\x00\x00\x00",
        is_extended=False,
    )
    assert decoder.decode_frame(frame_truncated) is None

    # EEC1 requires 8 bytes; send empty payload
    frame_empty = CanFrame.create(
        channel_id="ch0",
        arbitration_id=0x0CF00400,
        data=b"",
        is_extended=True,
    )
    assert decoder.decode_frame(frame_empty) is None


def test_oversized_frame_truncation() -> None:
    """Verify that frames with data length > DBC message length are safely truncated."""
    decoder = DbcSignalDecoder.from_dbc_string(SAMPLE_DBC)

    # StandardMsg requires 8 bytes; send 12 bytes
    frame_oversized = CanFrame.create(
        channel_id="ch0",
        arbitration_id=256,
        data=b"\x78\x00\x00\x00\x00\x00\x00\x00\xaa\xbb\xcc\xdd",
        is_extended=False,
        is_fd=True,
        dlc=12,
    )
    decoded = decoder.decode_frame(frame_oversized)
    assert decoded is not None
    assert decoded.signals["CoolantTemp"].value == 80


def test_lru_cache_eviction_and_bounding() -> None:
    """Verify that _message_cache is strictly bounded by max_cache_size and evicts LRU entries."""
    decoder = DbcSignalDecoder.from_dbc_string(SAMPLE_DBC, max_cache_size=3)
    assert decoder.max_cache_size == 3

    # Query 3 IDs: 0x100 (in DBC), 0x200 (unknown), 0x300 (unknown)
    decoder._lookup_message(0x100, is_extended=False)
    decoder._lookup_message(0x200, is_extended=False)
    decoder._lookup_message(0x300, is_extended=False)

    assert len(decoder._message_cache) == 3
    assert list(decoder._message_cache.keys()) == [0x100, 0x200, 0x300]

    # Re-access 0x100 (moves 0x100 to most recently used end)
    decoder._lookup_message(0x100, is_extended=False)
    assert list(decoder._message_cache.keys()) == [0x200, 0x300, 0x100]

    # Query 4th ID: 0x400 -> oldest (0x200) should be evicted
    decoder._lookup_message(0x400, is_extended=False)
    assert len(decoder._message_cache) == 3
    assert 0x200 not in decoder._message_cache
    assert list(decoder._message_cache.keys()) == [0x300, 0x100, 0x400]


def test_from_dbc_file_with_custom_cache_size() -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".dbc", delete=False) as tmp:
        tmp.write(SAMPLE_DBC)
        tmp_path = Path(tmp.name)

    try:
        decoder = DbcSignalDecoder.from_dbc_file(tmp_path, max_cache_size=512)
        assert decoder.max_cache_size == 512
        assert len(decoder.db.messages) == 2
    finally:
        tmp_path.unlink(missing_ok=True)


def test_sentinel_msb_ranges_flagged_for_16bit_signals() -> None:
    """E4 regression: the whole J1939-71 MSB sentinel range is invalid, not just 0xFFFE/0xFFFF.

    EngineSpeed is a 16-bit little-endian signal in bytes 3 (LSB) and 4 (MSB)
    of EEC1. Any MSB of 0xFE means Error and any MSB of 0xFF means Not
    Available; previously only the exact values 0xFFFE and 0xFFFF were caught.
    """
    from src.engine.decoder.dbc_decoder import SignalStatus

    decoder = DbcSignalDecoder.from_dbc_string(SAMPLE_DBC)

    def decode_engine_speed(raw16: int):
        data = bytearray(8)
        data[3] = raw16 & 0xFF
        data[4] = (raw16 >> 8) & 0xFF
        frame = CanFrame.create(
            channel_id="ch0",
            arbitration_id=0x0CF00400,  # EEC1 on-wire ID (DBC id minus the 0x80000000 ext flag)
            data=bytes(data),
            is_extended=True,
        )
        decoded = decoder.decode_frame(frame)
        assert decoded is not None
        return decoded.signals["EngineSpeed"]

    # Mid-range Error encoding (0xFE57) — the regression case
    sig_err = decode_engine_speed(0xFE57)
    assert sig_err.is_valid is False
    assert sig_err.status == SignalStatus.ERROR

    # Mid-range Not Available encoding (0xFF00)
    sig_na = decode_engine_speed(0xFF00)
    assert sig_na.is_valid is False
    assert sig_na.status == SignalStatus.NOT_AVAILABLE

    # Normal value stays valid
    sig_ok = decode_engine_speed(0x1F40)  # 8000 -> 1000 rpm
    assert sig_ok.is_valid is True
    assert sig_ok.status == SignalStatus.VALID
