"""Unit tests for SAE J1939-21 Transport Protocol (BAM & CMDT RTS/CTS/Abort)."""

from src.core.models.can_frame import CanFrame
from src.protocols.j1939.transport import (
    TP_CTRL_ABORT,
    TP_CTRL_ACK,
    TP_CTRL_BAM,
    TP_CTRL_CTS,
    TP_CTRL_RTS,
    J1939TransportProtocol,
)


def test_j1939_bam_reassembly() -> None:
    tp = J1939TransportProtocol(my_address=0xF9)

    # 1. TP.CM_BAM frame: PGN 65226 (DM1), 14 bytes, 2 packets
    bam_data = bytearray(8)
    bam_data[0] = TP_CTRL_BAM
    bam_data[1:3] = (14).to_bytes(2, byteorder="little")
    bam_data[3] = 2  # 2 packets
    bam_data[4] = 0xFF
    bam_data[5:8] = (65226).to_bytes(3, byteorder="little")

    cm_frame = CanFrame.create(
        channel_id="ch0",
        arbitration_id=0x18ECFF00,  # DA = 255 (Global), SA = 0
        data=bytes(bam_data),
        is_extended=True,
    )
    completed_msg, resp_frame = tp.handle_rx_frame(cm_frame)
    assert completed_msg is None
    assert resp_frame is None

    # 2. TP.DT Packet 1 (7 bytes payload)
    dt1_data = b"\x01" + b"\x11\x22\x33\x44\x55\x66\x77"
    dt1_frame = CanFrame.create(
        channel_id="ch0",
        arbitration_id=0x18EBFF00,
        data=dt1_data,
        is_extended=True,
    )
    completed_msg, resp_frame = tp.handle_rx_frame(dt1_frame)
    assert completed_msg is None
    assert resp_frame is None

    # 3. TP.DT Packet 2 (7 bytes payload -> total 14 bytes)
    dt2_data = b"\x02" + b"\x88\x99\xaa\xbb\xcc\xdd\xee"
    dt2_frame = CanFrame.create(
        channel_id="ch0",
        arbitration_id=0x18EBFF00,
        data=dt2_data,
        is_extended=True,
    )
    completed_msg, resp_frame = tp.handle_rx_frame(dt2_frame)
    assert completed_msg is not None
    assert resp_frame is None  # BAM does not send ACK

    assert completed_msg.pgn == 65226
    assert completed_msg.source_address == 0
    assert len(completed_msg.data) == 14
    assert completed_msg.data == b"\x11\x22\x33\x44\x55\x66\x77\x88\x99\xaa\xbb\xcc\xdd\xee"


def test_j1939_cmdt_rts_cts_flow_and_ack() -> None:
    tp = J1939TransportProtocol(my_address=0xF9)

    # 1. Incoming TP.CM_RTS from ECU (SA=0) to our tool (DA=0xF9) for DM2 (PGN 65227), 8 bytes, 2 packets
    rts_data = bytearray(8)
    rts_data[0] = TP_CTRL_RTS
    rts_data[1:3] = (8).to_bytes(2, byteorder="little")
    rts_data[3] = 2
    rts_data[4] = 0xFF
    rts_data[5:8] = (65227).to_bytes(3, byteorder="little")

    rts_frame = CanFrame.create(
        channel_id="ch0",
        arbitration_id=0x18ECF900,  # DA = 0xF9, SA = 0
        data=bytes(rts_data),
        is_extended=True,
    )
    completed_msg, cts_frame = tp.handle_rx_frame(rts_frame)
    assert completed_msg is None
    assert cts_frame is not None

    # Verify CTS frame structure
    assert cts_frame.arbitration_id == 0x18EC00F9  # DA = 0, SA = 0xF9
    assert cts_frame.data[0] == TP_CTRL_CTS
    assert cts_frame.data[1] == 2  # Allowed packets
    assert cts_frame.data[2] == 1  # Next packet seq

    # 2. DT Packet 1
    dt1 = CanFrame.create(
        channel_id="ch0",
        arbitration_id=0x18EBF900,
        data=b"\x01" + b"\x01\x02\x03\x04\x05\x06\x07",
        is_extended=True,
    )
    tp.handle_rx_frame(dt1)

    # 3. DT Packet 2 (final 1 byte payload)
    dt2 = CanFrame.create(
        channel_id="ch0",
        arbitration_id=0x18EBF900,
        data=b"\x02" + b"\x08\xff\xff\xff\xff\xff\xff",
        is_extended=True,
    )
    completed_msg, ack_frame = tp.handle_rx_frame(dt2)

    assert completed_msg is not None
    assert len(completed_msg.data) == 8
    assert completed_msg.data == b"\x01\x02\x03\x04\x05\x06\x07\x08"

    # Verify EndOfMsgACK frame
    assert ack_frame is not None
    assert ack_frame.data[0] == TP_CTRL_ACK
    assert ack_frame.arbitration_id == 0x18EC00F9


def test_j1939_out_of_order_sequence_aborts() -> None:
    tp = J1939TransportProtocol(my_address=0xF9)

    # RTS
    rts_data = bytearray(8)
    rts_data[0] = TP_CTRL_RTS
    rts_data[1:3] = (14).to_bytes(2, byteorder="little")
    rts_data[3] = 2
    rts_data[4] = 0xFF
    rts_data[5:8] = (65226).to_bytes(3, byteorder="little")

    rts_frame = CanFrame.create(
        channel_id="ch0",
        arbitration_id=0x18ECF900,
        data=bytes(rts_data),
        is_extended=True,
    )
    tp.handle_rx_frame(rts_frame)

    # Send sequence 2 directly instead of 1 (Out of order)
    dt_bad = CanFrame.create(
        channel_id="ch0",
        arbitration_id=0x18EBF900,
        data=b"\x02\x01\x02\x03\x04\x05\x06\x07",
        is_extended=True,
    )
    completed_msg, abort_frame = tp.handle_rx_frame(dt_bad)

    assert completed_msg is None
    # Must emit standard TP.Conn_Abort (PGN 60416 / 0xEC00 with Control Byte 0xFF)
    assert abort_frame is not None
    assert abort_frame.data[0] == TP_CTRL_ABORT
    assert abort_frame.data[1] == 0x04  # Out of order reason


def test_j1939_session_reaping_and_dos_prevention() -> None:
    """Verify that stale J1939 sessions are reaped and capacity is bounded under flood attack."""
    tp = J1939TransportProtocol(my_address=0xF9)

    # 1. Flood with 2000 BAM frames from distinct simulated ECUs
    for sa in range(250):
        for pgn_offset in range(8):
            bam_data = bytearray(8)
            bam_data[0] = TP_CTRL_BAM
            bam_data[1:3] = (14).to_bytes(2, byteorder="little")
            bam_data[3] = 2
            bam_data[4] = 0xFF
            bam_data[5:8] = (60000 + pgn_offset).to_bytes(3, byteorder="little")

            cm_frame = CanFrame.create(
                channel_id="ch0",
                arbitration_id=0x18ECFF00 | sa,
                data=bytes(bam_data),
                is_extended=True,
            )
            tp.handle_rx_frame(cm_frame)

    # Active sessions must be strictly capped at MAX_CONCURRENT_SESSIONS
    assert len(tp._rx_sessions) <= tp.MAX_CONCURRENT_SESSIONS

    # 2. Simulate passage of time (> T1 timeout) and verify reaping
    import time

    tp._reap_stale_sessions(now=time.monotonic() + 10.0)
    assert len(tp._rx_sessions) == 0
