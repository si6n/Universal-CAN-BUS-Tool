"""Signal Discovery & Evidence Engine Orchestrator.

Implements MASTER_PLAN.md Section 7, coordinating live and offline trace ingestion,
statistical bit profiling, invariant detection (Counter/CRC/Checksum), signal segmentation,
and automated DBC generation.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from cantools.database.can.database import Database

from src.core.logging import get_logger
from src.core.models.can_frame import CanFrame
from src.engine.discovery.bitstats import BitStats
from src.engine.discovery.dbc_builder import DbcBuilder
from src.engine.discovery.detectors.checksum import ChecksumDetector
from src.engine.discovery.detectors.counter import CounterDetector
from src.engine.discovery.hypotheses import IdReport
from src.engine.discovery.segmenter import SignalSegmenter
from src.hal.replay.parsers import VectorAscParser

logger = get_logger("engine.discovery")


class SignalDiscoveryEngine:
    """Orchestrates reverse-engineering workflows to discover signals from raw CAN traffic."""

    def __init__(self, min_frames: int = 10) -> None:
        self.min_frames = min_frames
        self._frames_by_id: dict[int, list[CanFrame]] = defaultdict(list)
        self._reports_cache: dict[int, IdReport] = {}

    def clear(self) -> None:
        """Clear all ingested frames and cached reports."""
        self._frames_by_id.clear()
        self._reports_cache.clear()

    def ingest_frame(self, frame: CanFrame) -> None:
        """Ingest a single CAN frame (e.g. from live stream or router)."""
        self._frames_by_id[frame.arbitration_id].append(frame)
        self._reports_cache.pop(frame.arbitration_id, None)

    def ingest_frames(self, frames: Sequence[CanFrame]) -> None:
        """Ingest a batch of CAN frames."""
        for f in frames:
            self._frames_by_id[f.arbitration_id].append(f)
            self._reports_cache.pop(f.arbitration_id, None)

    def ingest_asc_file(self, file_path: str | Path) -> int:
        """Load and ingest all frames from a Vector ASCII (.asc) trace file."""
        frames = VectorAscParser.parse_file(file_path)
        self.ingest_frames(frames)
        logger.info(
            "Ingested trace file into DiscoveryEngine",
            extra={"file": str(file_path), "frames": len(frames), "unique_ids": len(self._frames_by_id)},
        )
        return len(frames)

    @property
    def discovered_ids(self) -> list[int]:
        """List of all unique arbitration IDs present in the ingested dataset."""
        return sorted(self._frames_by_id.keys())

    def get_frame_count(self, arb_id: int) -> int:
        """Get the number of ingested frames for a specific CAN ID."""
        return len(self._frames_by_id.get(arb_id, []))

    def analyze_id(self, arb_id: int) -> IdReport:
        """Run full evidence-based reverse engineering on a specific CAN ID."""
        if arb_id in self._reports_cache:
            return self._reports_cache[arb_id]

        frames = self._frames_by_id.get(arb_id, [])
        if not frames:
            empty_report = IdReport(arbitration_id=arb_id, frame_count=0, rate_hz=0.0, dlc=0)
            self._reports_cache[arb_id] = empty_report
            return empty_report

        dlc = max(f.dlc for f in frames)
        payloads = [f.data for f in frames]
        frame_count = len(frames)

        # 1. Calculate Message Rate (Hz)
        rate_hz = 0.0
        if len(frames) >= 2:
            duration_s = (frames[-1].timestamp_ns - frames[0].timestamp_ns) / 1_000_000_000.0
            if duration_s > 0:
                rate_hz = round(len(frames) / duration_s, 2)

        # 2. Byte-Level Shannon Entropy
        entropy_by_byte: dict[int, float] = {}
        for byte_idx in range(dlc):
            byte_vals = [p[byte_idx] for p in payloads if len(p) > byte_idx]
            entropy_by_byte[byte_idx] = BitStats.compute_shannon_entropy(byte_vals)

        # 3. Detect Rolling Counters
        counter_hypotheses = CounterDetector.detect(payloads, dlc)

        # 4. Detect Checksums / CRCs
        checksum_hypotheses = ChecksumDetector.detect(payloads, dlc)

        # 5. Determine occupied bit spans from confirmed counter / checksum hypotheses
        occupied_spans: list[tuple[int, int]] = []
        for h in counter_hypotheses:
            if h.confidence >= 0.85:
                occupied_spans.append((h.start_bit, h.length))
        for h in checksum_hypotheses:
            if h.confidence >= 0.85:
                occupied_spans.append((h.start_bit, h.length))

        # 6. Segment Remaining Payload into Physical Signal Candidates
        signal_hypotheses = SignalSegmenter.segment(payloads, dlc, occupied_spans=occupied_spans)

        # Combine all hypotheses
        all_hypotheses = counter_hypotheses + checksum_hypotheses + signal_hypotheses

        report = IdReport(
            arbitration_id=arb_id,
            frame_count=frame_count,
            rate_hz=rate_hz,
            dlc=dlc,
            entropy=entropy_by_byte,
            hypotheses=all_hypotheses,
        )
        self._reports_cache[arb_id] = report
        return report

    def analyze_all(self) -> dict[int, IdReport]:
        """Run analysis on all CAN IDs with sufficient frame counts."""
        reports: dict[int, IdReport] = {}
        for arb_id in self.discovered_ids:
            if self.get_frame_count(arb_id) >= self.min_frames:
                reports[arb_id] = self.analyze_id(arb_id)
        return reports

    def approve_hypothesis(self, arb_id: int, start_bit: int, length: int) -> bool:
        """Approve a specific hypothesis for DBC export."""
        report = self.analyze_id(arb_id)
        for hyp in report.hypotheses:
            if hyp.start_bit == start_bit and hyp.length == length:
                hyp.status = "approved"
                return True
        return False

    def generate_evidence_markdown(self, arb_id: int) -> str:
        """Generate a human-readable Markdown evidence report for a CAN ID."""
        report = self.analyze_id(arb_id)
        lines = [
            f"# Signal Discovery Evidence Report: CAN ID 0x{arb_id:04X}",
            f"- **Frame Count:** {report.frame_count}",
            f"- **Estimated Rate:** {report.rate_hz} Hz",
            f"- **DLC:** {report.dlc} Bytes",
            "",
            "## Byte Entropy Profile",
            "| Byte Index | Shannon Entropy (bits) | Status |",
            "|:---:|:---:|:---|",
        ]
        for b_idx, ent in sorted(report.entropy.items()):
            status = "Const (0.0)" if ent == 0 else "Low Variance" if ent < 2.0 else "Dynamic" if ent < 6.0 else "High Entropy / Noise"
            lines.append(f"| {b_idx} | {ent:.4f} | {status} |")

        lines.extend([
            "",
            "## Discovered Hypotheses",
            "| Type | Bit Range | Length | Confidence | Status | Details |",
            "|:---:|:---:|:---:|:---:|:---:|:---|",
        ])

        if not report.hypotheses:
            lines.append("| - | - | - | - | - | *No strong hypotheses detected* |")
        else:
            for h in report.hypotheses:
                details = "; ".join(e.detail for e in h.evidence)
                lines.append(
                    f"| **{h.htype}** | {h.start_bit}..{h.start_bit + h.length - 1} | {h.length} | "
                    f"{h.confidence:.1%} | `{h.status}` | {details} |"
                )

        return "\n".join(lines)

    def build_dbc(self, approved_only: bool = False) -> Database:
        """Generate a cantools Database from discovered signal hypotheses."""
        reports = self.analyze_all()
        return DbcBuilder.build_database(reports, approved_only=approved_only)

    def export_dbc(self, file_path: str | Path, approved_only: bool = False) -> None:
        """Export discovered signals to a .dbc file."""
        db = self.build_dbc(approved_only=approved_only)
        DbcBuilder.export_dbc_file(db, file_path)
