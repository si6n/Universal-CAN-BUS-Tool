"""Unit tests for DBC signal validity filter, Not Available (0xFF) detection, and status metadata."""

from __future__ import annotations

from src.core.models.can_frame import CanFrame
from src.engine.decoder.dbc_decoder import DbcSignalDecoder, SignalStatus

TEST_VALIDITY_DBC = """VERSION ""
NS_ :
BS_:
BU_: Engine Tester

BO_ 2364539904 EEC1: 8 Engine
 SG_ EngineSpeed : 24|16@1+ (0.125,0) [0|8031.875] "rpm" Vector__XXX
 SG_ ActualEnginePercentTorque : 16|8@1+ (1,-125) [-125|125] "%" Vector__XXX
 SG_ EngineStarterMode : 8|4@1+ (1,0) [0|15] "" Vector__XXX

BO_ 256 StandardMsg: 8 Engine
 SG_ CoolantTemp : 0|8@1+ (1,-40) [-40|215] "degC" Vector__XXX
"""


def test_dbc_signal_validity_valid_signals() -> None:
    decoder = DbcSignalDecoder.from_dbc_string(TEST_VALIDITY_DBC)

    # Valid Engine Speed 1600 RPM (0x3200 = 12800 * 0.125) and Torque 50% (raw 175 -> 175 - 125 = 50)
    frame = CanFrame.create(
        channel_id="ch0",
        arbitration_id=0x0CF00400,
        data=b"\x00\x01\xAF\x00\x32\x00\x00\x00",
        is_extended=True,
    )
    decoded = decoder.decode_frame(frame)
    assert decoded is not None
    sig_speed = decoded.signals["EngineSpeed"]
    assert sig_speed.value == 1600.0
    assert sig_speed.is_valid is True
    assert sig_speed.status == SignalStatus.VALID
    assert sig_speed.confidence == "HIGH"

    sig_torque = decoded.signals["ActualEnginePercentTorque"]
    assert sig_torque.value == 50
    assert sig_torque.is_valid is True
    assert sig_torque.status == SignalStatus.VALID


def test_dbc_signal_not_available_discrete_values_detected() -> None:
    decoder = DbcSignalDecoder.from_dbc_string(TEST_VALIDITY_DBC)

    # 1. 8-bit signal with raw 0xFF (255) -> Not Available
    # 2. 16-bit signal with raw 0xFFFF (65535) -> Not Available
    # 3. 4-bit signal with raw 0x0F (15) -> Not Available
    frame_na = CanFrame.create(
        channel_id="ch0",
        arbitration_id=0x0CF00400,
        data=b"\x00\x0F\xFF\xFF\xFF\x00\x00\x00",
        is_extended=True,
    )
    decoded = decoder.decode_frame(frame_na)
    assert decoded is not None

    sig_speed = decoded.signals["EngineSpeed"]
    assert sig_speed.raw_value == 65535
    assert sig_speed.is_valid is False
    assert sig_speed.status == SignalStatus.NOT_AVAILABLE
    assert sig_speed.confidence == "UNKNOWN"

    sig_torque = decoded.signals["ActualEnginePercentTorque"]
    assert sig_torque.raw_value == 255
    assert sig_torque.is_valid is False
    assert sig_torque.status == SignalStatus.NOT_AVAILABLE

    sig_mode = decoded.signals["EngineStarterMode"]
    assert sig_mode.raw_value == 15
    assert sig_mode.is_valid is False
    assert sig_mode.status == SignalStatus.NOT_AVAILABLE


def test_dbc_signal_parameter_error_discrete_values_detected() -> None:
    decoder = DbcSignalDecoder.from_dbc_string(TEST_VALIDITY_DBC)

    # 8-bit signal with raw 0xFE (254) -> Parameter Error
    # 16-bit signal with raw 0xFFFE (65534) -> Parameter Error
    frame_err = CanFrame.create(
        channel_id="ch0",
        arbitration_id=0x0CF00400,
        data=b"\x00\x0E\xFE\xFE\xFF\x00\x00\x00",
        is_extended=True,
    )
    decoded = decoder.decode_frame(frame_err)
    assert decoded is not None

    sig_speed = decoded.signals["EngineSpeed"]
    assert sig_speed.raw_value == 65534
    assert sig_speed.is_valid is False
    assert sig_speed.status == SignalStatus.ERROR
    assert sig_speed.confidence == "UNKNOWN"

    sig_torque = decoded.signals["ActualEnginePercentTorque"]
    assert sig_torque.raw_value == 254
    assert sig_torque.is_valid is False
    assert sig_torque.status == SignalStatus.ERROR
