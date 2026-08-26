"""Vector ASCII (.asc) and Binary Log (.blf) Trace Parsers."""

from __future__ import annotations

import re
from pathlib import Path

from src.core.models.can_frame import CanFrame

# Standard Vector ASCII log line regex
# Example: "   0.001250 1  18FEEE00x       Rx   d 8 01 02 03 04 05 06 07 08"
CLASSIC_ASC_REGEX = re.compile(
    r"^\s*(?P<time>\d+\.\d+)\s+(?P<channel>\d+)\s+(?P<id>[0-9A-Fa-f]+)(?P<ext>x)?\s+(?P<dir>Rx|Tx)\s+d\s+(?P<dlc>\d+)\s+(?P<data>(?:[0-9A-Fa-f]{2}\s*)+)"
)

# CAN-FD Vector ASCII log line regex
# Example: "   0.002500 CANFD 1 Rx 123 1 0 12 12 01 02 03 04 05 06 07 08 09 0A 0B 0C"
FD_ASC_REGEX = re.compile(
    r"^\s*(?P<time>\d+\.\d+)\s+CANFD\s+(?P<channel>\d+)\s+(?P<dir>Rx|Tx)\s+(?P<id>[0-9A-Fa-f]+)(?P<ext>x)?\s+(?P<brs>[01])\s+(?P<esi>[01])\s+(?P<dlc>\d+)\s+(?P<len>\d+)\s+(?P<data>(?:[0-9A-Fa-f]{2}\s*)+)"
)


class VectorAscParser:
    """Parser for Vector CANoe/CANalyzer ASCII (.asc) trace log files."""

    @classmethod
    def parse_file(cls, file_path: str | Path, channel_prefix: str = "ch") -> list[CanFrame]:
        """Parse complete .asc file into chronological CanFrame list."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Trace file not found: {path}")

        frames: list[CanFrame] = []
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, 1):
                frame = cls.parse_line(line, line_no, channel_prefix)
                if frame:
                    frames.append(frame)

        return frames

    @classmethod
    def parse_line(cls, line: str, line_no: int = 1, channel_prefix: str = "ch") -> CanFrame | None:
        """Parse single ASCII line. Returns None for comments and header lines."""
        line = line.strip()
        if not line or line.startswith(("//", "date", "base")):
            return None

        # Check Classic CAN format
        match_classic = CLASSIC_ASC_REGEX.match(line)
        if match_classic:
            time_sec = float(match_classic.group("time"))
            channel_num = match_classic.group("channel")
            raw_id = match_classic.group("id")
            is_extended = match_classic.group("ext") == "x"
            direction = match_classic.group("dir").lower()
            dlc = int(match_classic.group("dlc"))
            data_hex = "".join(match_classic.group("data").split())
            data_bytes = bytes.fromhex(data_hex)

            arb_id = int(raw_id, 16)
            timestamp_ns = int(time_sec * 1_000_000_000)

            return CanFrame(
                channel_id=f"{channel_prefix}{channel_num}",
                arbitration_id=arb_id,
                dlc=dlc,
                data=data_bytes,
                is_extended=is_extended,
                is_fd=False,
                direction=direction,
                timestamp_ns=timestamp_ns,
                source="replay",
            )

        # Check CAN-FD format
        match_fd = FD_ASC_REGEX.match(line)
        if match_fd:
            time_sec = float(match_fd.group("time"))
            channel_num = match_fd.group("channel")
            raw_id = match_fd.group("id")
            is_extended = match_fd.group("ext") == "x"
            direction = match_fd.group("dir").lower()
            brs = match_fd.group("brs") == "1"
            esi = match_fd.group("esi") == "1"
            dlc = int(match_fd.group("dlc"))
            data_hex = "".join(match_fd.group("data").split())
            data_bytes = bytes.fromhex(data_hex)

            arb_id = int(raw_id, 16)
            timestamp_ns = int(time_sec * 1_000_000_000)

            return CanFrame(
                channel_id=f"{channel_prefix}{channel_num}",
                arbitration_id=arb_id,
                dlc=dlc,
                data=data_bytes,
                is_extended=is_extended,
                is_fd=True,
                brs=brs,
                esi=esi,
                direction=direction,
                timestamp_ns=timestamp_ns,
                source="replay",
            )

        return None
