"""SAE J1939 Commercial Vehicle OEM Proprietary Routing Registry & Canonical Types.

Complies with SAE J1939-21, SAE J1939-71, and SPEC-DIAG-J1939-V1.0 Section 5 & 6.
Handles Proprietary A (PGN 61184 / 0xEF00) and Proprietary B (PGN 65280-65535 / 0xFF00-0xFFFF).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any

from src.core.logging import get_logger
from src.core.models.can_frame import CanFrame
from src.engine.decoder.dbc_decoder import DecodedSignal

logger = get_logger("protocols.j1939.oem")


def parse_j1939_id(arbitration_id: int) -> tuple[int, int, int | None, int]:
    """Parse a 29-bit CAN arbitration identifier into J1939 components.

    Returns:
        (pgn, source_address, destination_address, priority)
        - pgn: 18-bit Parameter Group Number (0x00000..0x3FFFF)
        - source_address: 8-bit SA (0..255)
        - destination_address: 8-bit DA (0..255) if PDU1 (PF < 240), else None
        - priority: 3-bit priority (0..7)
    """
    priority = (arbitration_id >> 26) & 0x07
    edp = (arbitration_id >> 25) & 0x01
    dp = (arbitration_id >> 24) & 0x01
    pf = (arbitration_id >> 16) & 0xFF
    ps = (arbitration_id >> 8) & 0xFF
    sa = arbitration_id & 0xFF

    if pf < 240:
        # PDU1 Format: Destination Specific (Unicast)
        da: int | None = ps
        pgn = (edp << 17) | (dp << 16) | (pf << 8)
    else:
        # PDU2 Format: Global Broadcast (Group Extension)
        da = None
        pgn = (edp << 17) | (dp << 16) | (pf << 8) | ps

    return pgn, sa, da, priority


def build_j1939_id(
    pgn: int,
    sa: int,
    da: int | None = None,
    priority: int = 6,
) -> int:
    """Construct a 29-bit CAN arbitration identifier from J1939 components."""
    priority = priority & 0x07
    edp = (pgn >> 17) & 0x01
    dp = (pgn >> 16) & 0x01
    pf = (pgn >> 8) & 0xFF
    ps = pgn & 0xFF

    if pf < 240:
        # PDU1: PS is Destination Address
        target_da = (da if da is not None else 0xFF) & 0xFF
        can_id = (priority << 26) | (edp << 25) | (dp << 24) | (pf << 16) | (target_da << 8) | (sa & 0xFF)
    else:
        # PDU2: PS is Group Extension
        can_id = (priority << 26) | (edp << 25) | (dp << 24) | (pf << 16) | (ps << 8) | (sa & 0xFF)

    return can_id


@dataclass(slots=True)
class OemDecodedPayload:
    """Standardized physical signal payload decoded from OEM proprietary J1939 frames."""

    manufacturer: str
    pgn: int
    signals: dict[str, DecodedSignal]
    timestamp_ns: int
    arbitration_id: int = 0
    source_address: int = 0
    destination_address: int | None = None
    is_broadcast: bool = True
    service_id: int | None = None
    raw_data: bytes = b""
    confidence: str = "HIGH"

    def get_value(self, name: str, default: Any = None) -> Any:
        """Return the physical value of a decoded signal if present and valid."""
        sig = self.signals.get(name)
        if sig is not None and sig.is_valid:
            return sig.value
        return default

    def get_signal(self, name: str) -> DecodedSignal | None:
        """Return the DecodedSignal instance by name."""
        return self.signals.get(name)

    def is_valid(self, name: str) -> bool:
        """Check if a specific signal was decoded with valid status."""
        sig = self.signals.get(name)
        return sig is not None and sig.is_valid

    def __getitem__(self, name: str) -> DecodedSignal:
        """Dict-like access to signals."""
        return self.signals[name]

    def __contains__(self, name: str) -> bool:
        """Check if signal name is present in payload."""
        return name in self.signals

    def to_dict(self) -> dict[str, Any]:
        """Serialize payload to dictionary for telemetry pipelines and JSON logging."""
        return {
            "manufacturer": self.manufacturer,
            "pgn": self.pgn,
            "pgn_hex": f"0x{self.pgn:X}",
            "arbitration_id": f"0x{self.arbitration_id:08X}",
            "source_address": self.source_address,
            "destination_address": self.destination_address,
            "timestamp_ns": self.timestamp_ns,
            "confidence": self.confidence,
            "signals": {
                name: {
                    "value": sig.value,
                    "unit": sig.unit,
                    "raw_value": sig.raw_value,
                    "is_valid": sig.is_valid,
                    "status": sig.status.value if hasattr(sig.status, "value") else str(sig.status),
                }
                for name, sig in self.signals.items()
            },
        }


class BaseOemDecoder(abc.ABC):
    """Abstract Base Class for Heavy-Duty Commercial Vehicle OEM Decoders."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Return the manufacturer identifier string."""
        ...

    @property
    @abc.abstractmethod
    def supported_pgns(self) -> set[int]:
        """Return the set of J1939 PGNs supported by this decoder."""
        ...

    def supports_pgn(self, pgn: int) -> bool:
        """Check if this decoder supports the given PGN."""
        return pgn in self.supported_pgns

    @abc.abstractmethod
    def decode(
        self,
        frame: CanFrame,
        pgn: int,
        sa: int,
        da: int | None = None,
    ) -> OemDecodedPayload | None:
        """Decode a CAN frame into structured physical signals."""
        ...


class OemJ1939Registry:
    """Master registry and routing engine for OEM Proprietary J1939 messages.

    Routes Proprietary A (PGN 61184 / 0xEF00) and Proprietary B (PGN 65280-65535 / 0xFF00-0xFFFF)
    frames to OEM decoders (Cummins, Caterpillar, Scania, Volvo, Detroit Diesel, Mercedes Actros).
    """

    PROPRIETARY_A_PGN: int = 61184  # 0xEF00
    PROPRIETARY_A2_PGN: int = 126720  # 0x1EF00
    PROPRIETARY_B_START: int = 65280  # 0xFF00
    PROPRIETARY_B_END: int = 65535  # 0xFFFF

    def __init__(self, decoders: list[BaseOemDecoder] | None = None) -> None:
        self._decoders: dict[str, BaseOemDecoder] = {}
        self._pgn_to_decoders: dict[int, list[BaseOemDecoder]] = {}

        if decoders is not None:
            for dec in decoders:
                self.register_decoder(dec)
        else:
            self._register_default_decoders()

    def _register_default_decoders(self) -> None:
        """Lazily import and register built-in OEM decoders."""
        from src.protocols.j1939.oem.actros import ActrosDecoder
        from src.protocols.j1939.oem.caterpillar import CaterpillarDecoder
        from src.protocols.j1939.oem.cummins import CumminsDecoder
        from src.protocols.j1939.oem.detroit import DetroitDecoder
        from src.protocols.j1939.oem.scania import ScaniaDecoder
        from src.protocols.j1939.oem.volvo import VolvoDecoder

        for decoder in [
            CumminsDecoder(),
            CaterpillarDecoder(),
            ScaniaDecoder(),
            VolvoDecoder(),
            DetroitDecoder(),
            ActrosDecoder(),
        ]:
            self.register_decoder(decoder)

    def register_decoder(self, decoder: BaseOemDecoder) -> None:
        """Register a new or custom OEM decoder."""
        key = decoder.name.lower()
        self._decoders[key] = decoder
        for pgn in decoder.supported_pgns:
            self._pgn_to_decoders.setdefault(pgn, [])
            if decoder not in self._pgn_to_decoders[pgn]:
                self._pgn_to_decoders[pgn].append(decoder)
        logger.debug("Registered OEM J1939 decoder", extra={"oem": decoder.name, "pgns": len(decoder.supported_pgns)})

    def unregister_decoder(self, name: str) -> None:
        """Remove a decoder by name."""
        key = name.lower()
        decoder = self._decoders.pop(key, None)
        if decoder:
            for pgn, dec_list in list(self._pgn_to_decoders.items()):
                if decoder in dec_list:
                    dec_list.remove(decoder)
                if not dec_list:
                    del self._pgn_to_decoders[pgn]

    def get_decoder(self, name: str) -> BaseOemDecoder | None:
        """Retrieve a registered decoder by name."""
        return self._decoders.get(name.lower())

    def list_decoders(self) -> list[str]:
        """List registered decoder names."""
        return [d.name for d in self._decoders.values()]

    def is_proprietary_pgn(self, pgn: int) -> bool:
        """Check if a PGN falls into J1939 Proprietary A or B ranges."""
        return (
            pgn == self.PROPRIETARY_A_PGN
            or pgn == self.PROPRIETARY_A2_PGN
            or (self.PROPRIETARY_B_START <= pgn <= self.PROPRIETARY_B_END)
        )

    def decode_frame(
        self,
        frame: CanFrame,
        manufacturer_hint: str | None = None,
    ) -> OemDecodedPayload | None:
        """Route and decode an incoming CAN frame into physical OEM signals.

        Args:
            frame: Raw 29-bit CAN frame
            manufacturer_hint: Optional OEM name filter ("Cummins", "Scania", etc.)

        Returns:
            OemDecodedPayload if decoded successfully, else None.
        """
        if not frame.is_extended:
            return None

        pgn, sa, da, _ = parse_j1939_id(frame.arbitration_id)

        # Fast path if manufacturer hint provided
        if manufacturer_hint:
            decoder = self.get_decoder(manufacturer_hint)
            if decoder and decoder.supports_pgn(pgn):
                return decoder.decode(frame, pgn, sa, da)

        # Match decoders registered for this PGN
        candidate_decoders = self._pgn_to_decoders.get(pgn, [])
        if not candidate_decoders:
            # Check if this is a general Proprietary A frame registered across all decoders
            if pgn == self.PROPRIETARY_A_PGN:
                candidate_decoders = list(self._decoders.values())
            else:
                return None

        for decoder in candidate_decoders:
            try:
                decoded = decoder.decode(frame, pgn, sa, da)
                if decoded is not None:
                    return decoded
            except Exception as exc:
                logger.debug(
                    "Decoder failed for frame",
                    extra={"decoder": decoder.name, "pgn": hex(pgn), "error": str(exc)},
                )

        return None

    def decode_payload(
        self,
        pgn: int,
        data: bytes,
        sa: int = 0,
        da: int | None = None,
        manufacturer_hint: str | None = None,
        timestamp_ns: int | None = None,
        channel_id: str = "oem_j1939",
    ) -> OemDecodedPayload | None:
        """Convenience method to decode directly from PGN and raw data bytes."""
        can_id = build_j1939_id(pgn=pgn, sa=sa, da=da)
        frame = CanFrame.create(
            channel_id=channel_id,
            arbitration_id=can_id,
            data=data,
            is_extended=True,
            timestamp_ns=timestamp_ns,
        )
        return self.decode_frame(frame, manufacturer_hint=manufacturer_hint)
