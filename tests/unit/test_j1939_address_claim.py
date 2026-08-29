"""Unit tests for SAE J1939-81 Address Claiming State Machine and 64-Bit NAME."""

from src.core.models.can_frame import CanFrame
from src.protocols.j1939.address_claim import (
    AddressClaimEngine,
    AddressClaimState,
    J1939Name,
)


def test_j1939_name_10_subfields_encoding() -> None:
    name = J1939Name(
        arbitrary_address_capable=True,  # 1 bit
        industry_group=1,  # On-Highway (3 bits)
        vehicle_system_instance=0,  # 4 bits
        vehicle_system=0,  # 7 bits
        reserved=0,  # 1 bit
        function=128,  # Diagnostic Tool (8 bits)
        function_instance=0,  # 5 bits
        ecu_instance=0,  # 3 bits
        manufacturer_code=500,  # 11 bits
        identity_number=12345,  # 21 bits
    )

    int64_val = name.to_int64()
    raw_bytes = name.to_bytes()
    assert len(raw_bytes) == 8

    decoded = J1939Name.from_bytes(raw_bytes)
    assert decoded.arbitrary_address_capable is True
    assert decoded.industry_group == 1
    assert decoded.vehicle_system_instance == 0
    assert decoded.vehicle_system == 0
    assert decoded.reserved == 0
    assert decoded.function == 128
    assert decoded.function_instance == 0
    assert decoded.ecu_instance == 0
    assert decoded.manufacturer_code == 500
    assert decoded.identity_number == 12345
    assert decoded.to_int64() == int64_val


def test_address_claim_win_contention() -> None:
    # My name has lower number (identity=100) -> Higher Priority
    my_name = J1939Name(
        arbitrary_address_capable=True,
        industry_group=1,
        vehicle_system_instance=0,
        vehicle_system=0,
        function=128,
        identity_number=100,
    )
    engine = AddressClaimEngine(name=my_name, preferred_address=0xF9)

    # Start claiming
    claim_frame = engine.start_claiming()
    assert engine.state.value == AddressClaimState.CLAIMING.value
    assert claim_frame.arbitration_id == 0x18EEFFF9

    # Another ECU sends claim for 0xF9 with higher number (identity=200) -> Lower Priority
    other_name = J1939Name(
        arbitrary_address_capable=True,
        industry_group=1,
        vehicle_system_instance=0,
        vehicle_system=0,
        function=128,
        identity_number=200,
    )
    other_frame = CanFrame.create(
        channel_id="j1939_ch0",
        arbitration_id=0x18EEFFF9,
        data=other_name.to_bytes(),
        is_extended=True,
    )

    # Engine should defend its address by re-broadcasting my claim
    defense_frame = engine.handle_rx_frame(other_frame)
    assert defense_frame is not None
    assert defense_frame.arbitration_id == 0x18EEFFF9
    assert defense_frame.data == my_name.to_bytes()

    engine.confirm_claimed()
    assert engine.is_address_claimed is True
    assert engine.state.value == AddressClaimState.CLAIMED.value


def test_address_claim_loss_and_fallback() -> None:
    # My name has higher number (identity=500) -> Lower Priority
    my_name = J1939Name(
        arbitrary_address_capable=True,
        industry_group=1,
        vehicle_system_instance=0,
        vehicle_system=0,
        function=128,
        identity_number=500,
    )
    engine = AddressClaimEngine(name=my_name, preferred_address=0xF9)
    engine.start_claiming()

    # Competing ECU has lower number (identity=50) -> Higher Priority
    competitor_name = J1939Name(
        arbitrary_address_capable=False,
        industry_group=1,
        vehicle_system_instance=0,
        vehicle_system=0,
        function=128,
        identity_number=50,
    )
    comp_frame = CanFrame.create(
        channel_id="j1939_ch0",
        arbitration_id=0x18EEFFF9,
        data=competitor_name.to_bytes(),
        is_extended=True,
    )

    # We lost 0xF9. Since arbitrary_address_capable is True, it tries fallback address 128 (0x80)
    fallback_frame = engine.handle_rx_frame(comp_frame)
    assert fallback_frame is not None
    assert engine.current_address == 128
    assert fallback_frame.arbitration_id == 0x18EEFF80
