"""DBC database generation from discovered signal and protocol hypotheses."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import cantools
from cantools.database.can.database import Database
from cantools.database.can.message import Message
from cantools.database.can.signal import Signal
from cantools.database.conversion import BaseConversion

from src.engine.discovery.hypotheses import IdReport


class DbcBuilder:
    """Constructs and serializes cantools CAN databases from discovery hypothesis reports."""

    @classmethod
    def build_database(
        cls,
        reports: Mapping[int, IdReport] | Sequence[IdReport],
        approved_only: bool = False,
    ) -> Database:
        """Create a cantools Database from ID reports."""
        db = Database()
        reports_list = reports.values() if isinstance(reports, Mapping) else reports

        for report in reports_list:
            if not report.hypotheses:
                continue

            signals: list[Signal] = []
            claimed_names: set[str] = set()
            occupied_bits: set[int] = set()

            # Sort hypotheses so higher confidence and wider signals are placed first
            sorted_hyps = sorted(
                report.hypotheses,
                key=lambda h: (1 if h.status == "approved" else 0, h.confidence, h.length),
                reverse=True,
            )

            for hyp in sorted_hyps:
                if approved_only and hyp.status != "approved":
                    continue

                # Ensure signal bits do not overlap with any previously placed signal
                hyp_bits = set(range(hyp.start_bit, hyp.start_bit + hyp.length))
                if hyp_bits & occupied_bits:
                    continue

                sig_name = hyp.name or f"SIG_{hyp.start_bit}_{hyp.length}"
                # Guarantee signal name uniqueness within message
                base_name = sig_name
                counter = 1
                while sig_name in claimed_names:
                    sig_name = f"{base_name}_{counter}"
                    counter += 1
                claimed_names.add(sig_name)
                occupied_bits.update(hyp_bits)

                # Format comments from evidence
                evidence_comments = [e.detail for e in hyp.evidence]
                comment_str = " | ".join(evidence_comments) if evidence_comments else f"Auto-discovered {hyp.htype}"

                conv = BaseConversion.factory(scale=hyp.factor, offset=hyp.offset)
                # In DBC Motorola format, start bit is MSB bit index
                start_bit = hyp.start_bit if hyp.is_little_endian else ((hyp.start_bit // 8) * 8 + 7)

                signal = Signal(
                    name=sig_name,
                    start=start_bit,
                    length=hyp.length,
                    byte_order="little_endian" if hyp.is_little_endian else "big_endian",
                    is_signed=hyp.is_signed,
                    conversion=conv,
                    minimum=hyp.min_value,
                    maximum=hyp.max_value,
                    unit=hyp.unit or None,
                    comment=comment_str,
                )
                signals.append(signal)

            if signals:
                is_extended = report.arbitration_id > 0x7FF
                msg_name = f"MSG_0x{report.arbitration_id:04X}"
                msg = Message(
                    frame_id=report.arbitration_id,
                    name=msg_name,
                    length=max(1, report.dlc),
                    signals=signals,
                    is_extended_frame=is_extended,
                    comment=f"Auto-generated for CAN ID 0x{report.arbitration_id:04X} ({report.frame_count} frames analyzed)",
                )
                db.messages.append(msg)

        return db

    @classmethod
    def export_dbc_file(cls, db: Database, file_path: str | Path) -> None:
        """Save database to a .dbc file."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        cantools.database.dump_file(db, str(path))
