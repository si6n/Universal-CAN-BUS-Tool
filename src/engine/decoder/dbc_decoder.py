"""DBC Signal Decoder Engine for Live CAN & J1939 Telemetry with Signal Validity Verification.

Complies with Saha Risk Kataloğu v1.2 Sections 12, 13, 30, Risk R-08, R-30.
"""

from __future__ import annotations

import collections
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import cantools
from cantools.database.can.database import Database
from cantools.database.errors import Error as CantoolsError

from src.core.errors import ProtocolError
from src.core.logging import get_logger
from src.core.models.can_frame import CanFrame

logger = get_logger("engine.decoder")


class SignalStatus(str, Enum):
    """Semantic Signal Validity and Health Status."""

    VALID = "VALID"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    ERROR = "ERROR"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


@dataclass(slots=True)
class DecodedSignal:
    """Decoded physical CAN signal value with full provenance and validity state."""

    name: str
    value: float | int | str
    unit: str
    raw_value: int | float | None = None
    is_valid: bool = True
    status: SignalStatus = SignalStatus.VALID
    confidence: str = "HIGH"


@dataclass(slots=True)
class DecodedMessage:
    """Decoded CAN message containing physical signals."""

    message_name: str
    arbitration_id: int
    signals: dict[str, DecodedSignal]
    timestamp_ns: int
    channel_id: str


class DbcSignalDecoder:
    """Real-time DBC signal decoding engine supporting Standard and J1939 message matching."""

    def __init__(self, db: Database | None = None, max_cache_size: int = 2048) -> None:
        self.db: Database = db if db is not None else cantools.database.can.Database()
        self.max_cache_size = max_cache_size
        self._message_cache: collections.OrderedDict[int, Any] = collections.OrderedDict()
        self._signal_units_cache: dict[int, dict[str, str]] = {}
        self._signal_defs_cache: dict[int, dict[str, Any]] = {}

    def _get_signal_metadata(self, msg_def: Any) -> tuple[dict[str, str], dict[str, Any]]:
        """Fetch pre-cached signal metadata for O(1) lookups."""
        fid = id(msg_def)
        if fid not in self._signal_units_cache:
            self._signal_units_cache[fid] = {s.name: (s.unit or "") for s in msg_def.signals}
            self._signal_defs_cache[fid] = {s.name: s for s in msg_def.signals}
        return self._signal_units_cache[fid], self._signal_defs_cache[fid]

    @classmethod
    def from_dbc_file(cls, dbc_path: str | Path, max_cache_size: int = 2048) -> DbcSignalDecoder:
        """Instantiate decoder from local DBC file."""
        path = Path(dbc_path)
        if not path.exists():
            raise FileNotFoundError(f"DBC file not found: {path}")

        try:
            loaded_db = cantools.database.load_file(path)
            if not isinstance(loaded_db, Database):
                raise TypeError(f"Expected CAN Database, got {type(loaded_db)}")
            logger.info("Loaded DBC file successfully", extra={"path": str(path), "messages": len(loaded_db.messages)})
            return cls(loaded_db, max_cache_size=max_cache_size)
        except Exception as exc:
            raise ProtocolError(
                f"Failed to parse DBC file '{path.name}': {exc}",
                code="DBC_PARSE_ERROR",
                details={"file": str(path)},
                cause=exc,
            ) from exc

    @classmethod
    def from_dbc_string(cls, dbc_text: str, max_cache_size: int = 2048) -> DbcSignalDecoder:
        """Instantiate decoder from in-memory DBC string."""
        loaded_db = cantools.database.load_string(dbc_text)
        if not isinstance(loaded_db, Database):
            raise TypeError(f"Expected CAN Database, got {type(loaded_db)}")
        return cls(loaded_db, max_cache_size=max_cache_size)

    def decode_frame(self, frame: CanFrame) -> DecodedMessage | None:
        """Decode raw frame payload into physical signals. Returns None if ID is not in DBC or truncated."""
        if not self.db.messages:
            return None

        # Look up message in DBC
        msg_def = self._lookup_message(frame.arbitration_id, frame.is_extended)
        if msg_def is None:
            return None

        try:
            # Reject truncated frames without creating phantom signals
            frame_len = len(frame.data)
            if frame_len < msg_def.length:
                return None

            payload = frame.data[: msg_def.length] if frame_len > msg_def.length else frame.data

            # Decode scaled physical values and raw integer values
            scaled_signals = msg_def.decode(
                payload,
                decode_choices=False,
                scaling=True,
            )
            raw_signals = msg_def.decode(
                payload,
                decode_choices=False,
                scaling=False,
            )

            units_map, sig_defs_map = self._get_signal_metadata(msg_def)
            decoded_signals: dict[str, DecodedSignal] = {}

            for sig_name, sig_val in scaled_signals.items():
                raw_val = raw_signals.get(sig_name)
                sig_def = sig_defs_map.get(sig_name)

                # Check for J1939 / standard Not Available and Parameter Error discrete values
                is_valid = True
                status = SignalStatus.VALID

                if sig_def is not None and isinstance(raw_val, (int, float)):
                    sig_len = sig_def.length
                    # Standard SAE J1939 indicator masks for unsigned fields
                    if not sig_def.is_signed and sig_len in {2, 4, 8, 16, 32}:
                        max_val = (1 << sig_len) - 1
                        error_val = max_val - 1

                        if raw_val == max_val:
                            is_valid = False
                            status = SignalStatus.NOT_AVAILABLE
                        elif raw_val == error_val:
                            is_valid = False
                            status = SignalStatus.ERROR

                decoded_signals[sig_name] = DecodedSignal(
                    name=sig_name,
                    value=sig_val,
                    unit=units_map.get(sig_name, ""),
                    raw_value=raw_val,
                    is_valid=is_valid,
                    status=status,
                    confidence="HIGH" if is_valid else "UNKNOWN",
                )

            return DecodedMessage(
                message_name=msg_def.name,
                arbitration_id=frame.arbitration_id,
                signals=decoded_signals,
                timestamp_ns=frame.timestamp_ns,
                channel_id=frame.channel_id,
            )
        except (KeyError, ValueError, CantoolsError) as exc:
            logger.debug(
                "Signal decode failed for frame",
                extra={"id": hex(frame.arbitration_id), "error": str(exc)},
            )
            return None

    def _lookup_message(self, arbitration_id: int, is_extended: bool) -> Any:
        """Find matching message definition with J1939 PGN mask support and LRU eviction."""
        if arbitration_id in self._message_cache:
            self._message_cache.move_to_end(arbitration_id)
            return self._message_cache[arbitration_id]

        msg: Any = None

        # Exact match attempt
        try:
            msg = self.db.get_message_by_frame_id(arbitration_id)
        except KeyError:
            pass

        # J1939 PGN lookup for 29-bit extended frames
        if msg is None and is_extended:
            # Extract PGN: bits 8..25
            pgn = (arbitration_id >> 8) & 0x3FFFF
            pdu_format = (pgn >> 8) & 0xFF
            masked_pgn = (pgn & 0x3FF00) if pdu_format < 240 else pgn

            for candidate in self.db.messages:
                # Candidate must be an extended frame definition (29-bit)
                is_candidate_ext = getattr(candidate, "is_extended_frame", False) or bool(
                    candidate.frame_id & 0x80000000
                )
                if not is_candidate_ext:
                    continue

                dbc_raw_id = candidate.frame_id & 0x1FFFFFFF
                dbc_pgn = (dbc_raw_id >> 8) & 0x3FFFF
                dbc_pf = (dbc_pgn >> 8) & 0xFF
                cand_masked_pgn = (dbc_pgn & 0x3FF00) if dbc_pf < 240 else dbc_pgn

                if cand_masked_pgn == masked_pgn:
                    msg = candidate
                    break

        self._message_cache[arbitration_id] = msg
        if len(self._message_cache) > self.max_cache_size:
            self._message_cache.popitem(last=False)

        return msg
