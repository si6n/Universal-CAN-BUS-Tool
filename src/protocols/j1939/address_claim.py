"""SAE J1939-81 Address Claiming State Machine and 64-Bit NAME Specification.

Complies with SAE J1939-81 and MASTER_PLAN.md Section 4.2.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from src.core.logging import get_logger
from src.core.models.can_frame import CanFrame

logger = get_logger("protocols.j1939.address_claim")

PGN_ADDRESS_CLAIM: int = 60928  # 0xEE00
NULL_ADDRESS: int = 254         # 0xFE
GLOBAL_ADDRESS: int = 255       # 0xFF


class AddressClaimState(Enum):
    """J1939-81 Address Claiming lifecycle states."""

    UNINITIALIZED = "UNINITIALIZED"
    CLAIMING = "CLAIMING"
    CLAIMED = "CLAIMED"
    CANNOT_CLAIM = "CANNOT_CLAIM"


@dataclass(slots=True, frozen=True)
class J1939Name:
    """SAE J1939-81 64-bit NAME composed of all 10 standard subfields."""

    arbitrary_address_capable: bool  # 1 bit (Bit 63)
    industry_group: int              # 3 bits (Bits 62..60)
    vehicle_system_instance: int     # 4 bits (Bits 59..56)
    vehicle_system: int              # 7 bits (Bits 55..49)
    reserved: int = 0                # 1 bit (Bit 48, default 0)
    function: int = 0                # 8 bits (Bits 47..40)
    function_instance: int = 0       # 5 bits (Bits 39..35)
    ecu_instance: int = 0            # 3 bits (Bits 34..32)
    manufacturer_code: int = 0       # 11 bits (Bits 31..21)
    identity_number: int = 0         # 21 bits (Bits 20..0)

    def to_int64(self) -> int:
        """Encode 10 subfields into a single 64-bit unsigned integer."""
        val = 0
        val |= (1 if self.arbitrary_address_capable else 0) << 63
        val |= (self.industry_group & 0x07) << 60
        val |= (self.vehicle_system_instance & 0x0F) << 56
        val |= (self.vehicle_system & 0x7F) << 49
        val |= (self.reserved & 0x01) << 48
        val |= (self.function & 0xFF) << 40
        val |= (self.function_instance & 0x1F) << 35
        val |= (self.ecu_instance & 0x07) << 32
        val |= (self.manufacturer_code & 0x07FF) << 21
        val |= self.identity_number & 0x1FFFFF
        return val

    def to_bytes(self) -> bytes:
        """Encode 64-bit NAME to 8-byte Little-Endian binary payload."""
        return self.to_int64().to_bytes(8, byteorder="little")

    @classmethod
    def from_int64(cls, val: int) -> J1939Name:
        """Decode 64-bit integer into 10-subfield J1939Name."""
        return cls(
            arbitrary_address_capable=bool((val >> 63) & 0x01),
            industry_group=(val >> 60) & 0x07,
            vehicle_system_instance=(val >> 56) & 0x0F,
            vehicle_system=(val >> 49) & 0x7F,
            reserved=(val >> 48) & 0x01,
            function=(val >> 40) & 0xFF,
            function_instance=(val >> 35) & 0x1F,
            ecu_instance=(val >> 32) & 0x07,
            manufacturer_code=(val >> 21) & 0x07FF,
            identity_number=val & 0x1FFFFF,
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> J1939Name:
        """Decode 8-byte binary payload into J1939Name."""
        if len(data) < 8:
            raise ValueError(f"J1939 NAME requires 8 bytes, got {len(data)}")
        val = int.from_bytes(data[:8], byteorder="little")
        return cls.from_int64(val)


class AddressClaimEngine:
    """J1939-81 Dynamic Address Claiming State Machine."""

    DEFAULT_PREFERRED_ADDRESS: ClassVar[int] = 0xF9  # 249 (Diagnostic tool #1)
    FALLBACK_ADDRESS_RANGE: ClassVar[tuple[int, ...]] = tuple(range(128, 248))

    def __init__(
        self,
        name: J1939Name,
        preferred_address: int = DEFAULT_PREFERRED_ADDRESS,
        channel_id: str = "j1939_ch0",
    ) -> None:
        self.name = name
        self.preferred_address = preferred_address
        self.current_address = preferred_address
        self.channel_id = channel_id
        self.state = AddressClaimState.UNINITIALIZED
        self._address_table: dict[int, J1939Name] = {}  # SA -> NAME

    @property
    def is_address_claimed(self) -> bool:
        """Return True if an address is successfully claimed and active for TX."""
        return self.state == AddressClaimState.CLAIMED and self.current_address != NULL_ADDRESS

    def start_claiming(self) -> CanFrame:
        """Initiate address claiming sequence and return the Address Claim frame to transmit."""
        self.current_address = self.preferred_address
        self.state = AddressClaimState.CLAIMING

        # Construct J1939 29-bit CAN ID: Priority 6, PGN 60928 (0xEE00), DA 255, SA
        # 0x18EEFF00 | SA
        can_id = 0x18EEFF00 | (self.current_address & 0xFF)
        claim_frame = CanFrame.create(
            channel_id=self.channel_id,
            arbitration_id=can_id,
            data=self.name.to_bytes(),
            is_extended=True,
            direction="tx",
        )

        logger.info(
            "Broadcasting Address Claim",
            extra={"address": self.current_address, "name_int": hex(self.name.to_int64())},
        )
        return claim_frame

    def handle_rx_frame(self, frame: CanFrame) -> CanFrame | None:
        """Process incoming frame. If Address Claim contention occurs, handles arbitration."""
        if not frame.is_extended or len(frame.data) < 8:
            return None

        # Extract PGN and Source Address from 29-bit CAN ID with PDU1/PDU2 distinction
        dp = (frame.arbitration_id >> 24) & 0x01
        pf = (frame.arbitration_id >> 16) & 0xFF
        ps = (frame.arbitration_id >> 8) & 0xFF
        source_address = frame.arbitration_id & 0xFF
        pgn = (dp << 16) | (pf << 8) if pf < 240 else (dp << 16) | (pf << 8) | ps

        # Check if frame is an Address Claim message (PGN 60928 / 0xEE00)
        if pgn != PGN_ADDRESS_CLAIM:
            return None

        other_name = J1939Name.from_bytes(frame.data)
        self._address_table[source_address] = other_name

        # If claim is from another SA, no collision with our current SA
        if source_address != self.current_address:
            return None

        # Contention detected on our address! Compare 64-bit NAMEs
        my_val = self.name.to_int64()
        other_val = other_name.to_int64()

        if my_val < other_val:
            # We have higher priority (lower numerical NAME). Re-assert our address!
            logger.info("Defending address claim against higher numerical NAME", extra={"sa": self.current_address})
            can_id = 0x18EEFF00 | (self.current_address & 0xFF)
            return CanFrame.create(
                channel_id=self.channel_id,
                arbitration_id=can_id,
                data=self.name.to_bytes(),
                is_extended=True,
                direction="tx",
            )
        else:
            # We lost contention.
            logger.warning("Lost address claim contention", extra={"sa": self.current_address})
            if self.name.arbitrary_address_capable:
                # Try next available address
                for candidate_sa in self.FALLBACK_ADDRESS_RANGE:
                    if candidate_sa not in self._address_table:
                        self.current_address = candidate_sa
                        can_id = 0x18EEFF00 | (self.current_address & 0xFF)
                        logger.info("Attempting next fallback address", extra={"new_sa": candidate_sa})
                        return CanFrame.create(
                            channel_id=self.channel_id,
                            arbitration_id=can_id,
                            data=self.name.to_bytes(),
                            is_extended=True,
                            direction="tx",
                        )

            # Cannot claim any address -> Send 'Cannot Claim' (SA = 254)
            self.current_address = NULL_ADDRESS
            self.state = AddressClaimState.CANNOT_CLAIM
            can_id = 0x18EEFF00 | NULL_ADDRESS
            logger.error("Transitioned to CANNOT_CLAIM (Null Address 0xFE)")
            return CanFrame.create(
                channel_id=self.channel_id,
                arbitration_id=can_id,
                data=self.name.to_bytes(),
                is_extended=True,
                direction="tx",
            )

    def confirm_claimed(self) -> None:
        """Call after claim contention timeout (250 ms) without collision to finalize claim."""
        if self.state == AddressClaimState.CLAIMING and self.current_address != NULL_ADDRESS:
            self.state = AddressClaimState.CLAIMED
            logger.info("Address Claim Confirmed", extra={"sa": self.current_address})
