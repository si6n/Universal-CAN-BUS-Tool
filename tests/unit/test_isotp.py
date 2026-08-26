import pytest

from src.core.models.can_frame import CanFrame
from src.protocols.uds.isotp import (
    PCI_CONSECUTIVE_FRAME,
    PCI_FIRST_FRAME,
    PCI_FLOW_CONTROL,
    PCI_SINGLE_FRAME,
    IsoTpTransport,
    decode_st_min,
)


def test_isotp_single_frame_roundtrip() -> None:
    transport = IsoTpTransport(tx_id=0x7E0, rx_id=0x7E8)

    # 4-byte payload (fits in Single Frame)
    payload = b"\x22\xf1\x90\x00"
    frames = transport.segment_message(payload)
    assert len(frames) == 1
    assert frames[0].arbitration_id == 0x7E0
    assert (frames[0].data[0] >> 4) == PCI_SINGLE_FRAME
    assert (frames[0].data[0] & 0x0F) == 4

    # Simulate ECU response: Single Frame with 0x62 F1 90 41 42
    resp_frame = CanFrame.create(
        channel_id="uds",
        arbitration_id=0x7E8,
        data=b"\x05\x62\xf1\x90\x41\x42\xcc\xcc",
        is_extended=False,
    )
    completed_data, flow_frame = transport.handle_rx_frame(resp_frame)
    assert flow_frame is None
    assert completed_data == b"\x62\xf1\x90\x41\x42"


def test_isotp_multi_frame_segmentation_and_reassembly() -> None:
    transport = IsoTpTransport(tx_id=0x7E0, rx_id=0x7E8)

    # 20-byte payload (Multi-Frame: FF + 2 CFs)
    long_payload = bytes(range(20))
    tx_frames = transport.segment_message(long_payload)
    assert len(tx_frames) == 3  # FF (6B) + CF1 (7B) + CF2 (7B)

    # 1. First Frame (FF)
    assert (tx_frames[0].data[0] >> 4) == PCI_FIRST_FRAME
    assert tx_frames[0].data[1] == 20  # Total length
    assert tx_frames[0].data[2:8] == long_payload[:6]

    # 2. Consecutive Frame 1 (CF 1)
    assert (tx_frames[1].data[0] >> 4) == PCI_CONSECUTIVE_FRAME
    assert (tx_frames[1].data[0] & 0x0F) == 1
    assert tx_frames[1].data[1:8] == long_payload[6:13]

    # 3. Consecutive Frame 2 (CF 2)
    assert (tx_frames[2].data[0] >> 4) == PCI_CONSECUTIVE_FRAME
    assert (tx_frames[2].data[0] & 0x0F) == 2

    # Now test reassembly of incoming response
    rx_transport = IsoTpTransport(tx_id=0x7E0, rx_id=0x7E8)

    # Feed FF
    ff_frame = CanFrame.create(
        channel_id="uds",
        arbitration_id=0x7E8,
        data=tx_frames[0].data,
        is_extended=False,
    )
    completed, fc_frame = rx_transport.handle_rx_frame(ff_frame)
    assert completed is None
    assert fc_frame is not None
    assert (fc_frame.data[0] >> 4) == PCI_FLOW_CONTROL

    # Feed CF 1
    cf1_frame = CanFrame.create(
        channel_id="uds",
        arbitration_id=0x7E8,
        data=tx_frames[1].data,
        is_extended=False,
    )
    completed, fc_frame = rx_transport.handle_rx_frame(cf1_frame)
    assert completed is None

    # Feed CF 2
    cf2_frame = CanFrame.create(
        channel_id="uds",
        arbitration_id=0x7E8,
        data=tx_frames[2].data,
        is_extended=False,
    )
    completed, fc_frame = rx_transport.handle_rx_frame(cf2_frame)
    assert completed is not None
    assert completed == long_payload


@pytest.mark.parametrize(
    ("raw_byte", "expected_ms"),
    [
        (0x00, 0.0),
        (0x05, 5.0),
        (0x7F, 127.0),
        (0xF1, 0.1),
        (0xF5, 0.5),
        (0xF9, 0.9),
        (0xFA, 127.0),
    ],
)
def test_isotp_decode_st_min_parametric(raw_byte: int, expected_ms: float) -> None:
    """Verify STmin decoding across standard millisecond and sub-millisecond ranges."""
    assert pytest.approx(decode_st_min(raw_byte), abs=1e-3) == expected_ms


def test_isotp_can_fd_segmentation() -> None:
    """Verify ISO-TP segmentation using CAN-FD 64-byte payload optimization."""
    transport = IsoTpTransport(tx_id=0x7E0, rx_id=0x7E8)

    # 40-byte payload in CAN-FD fits in single frame
    payload_40 = bytes(range(40))
    frames_fd_single = transport.segment_message(payload_40, is_fd=True)
    assert len(frames_fd_single) == 1
    assert frames_fd_single[0].is_fd is True
    assert frames_fd_single[0].data[0] == 0x00
    assert frames_fd_single[0].data[1] == 40
    assert frames_fd_single[0].data[2:42] == payload_40

    # 100-byte payload in CAN-FD uses FF (62B) + CF1 (38B)
    payload_100 = bytes(range(100))
    frames_fd_multi = transport.segment_message(payload_100, is_fd=True)
    assert len(frames_fd_multi) == 2
    assert (frames_fd_multi[0].data[0] >> 4) == PCI_FIRST_FRAME
    assert frames_fd_multi[0].is_fd is True
    assert (frames_fd_multi[1].data[0] >> 4) == PCI_CONSECUTIVE_FRAME
    assert frames_fd_multi[1].is_fd is True
