"""Signal segmentation, multi-byte boundary detection, endianness and signedness analysis."""

from __future__ import annotations

from collections.abc import Sequence

from src.engine.discovery.hypotheses import Evidence, Hypothesis


class SignalSegmenter:
    """Groups unassigned active bits into physical signal candidates (1-byte, 2-byte, 4-byte)."""

    @classmethod
    def segment(
        cls,
        payloads: Sequence[bytes],
        dlc: int,
        occupied_spans: Sequence[tuple[int, int]] | None = None,
    ) -> list[Hypothesis]:
        """Segment remaining payload bytes into candidate physical signals."""
        if len(payloads) < 5 or dlc <= 0:
            return []

        occupied: set[int] = set()
        if occupied_spans:
            for start, length in occupied_spans:
                for b in range(start, start + length):
                    occupied.add(b)

        hypotheses: list[Hypothesis] = []
        byte_available = [True] * dlc
        for byte_idx in range(dlc):
            # Mark byte unavailable if any of its bits are occupied
            if any((byte_idx * 8 + bit) in occupied for bit in range(8)):
                byte_available[byte_idx] = False

        # Phase 1: Search for 2-byte (16-bit) candidate signals
        byte_idx = 0
        while byte_idx < dlc - 1:
            if byte_available[byte_idx] and byte_available[byte_idx + 1]:
                sig16 = cls._evaluate_16bit_signal(payloads, byte_idx)
                if sig16 is not None:
                    hypotheses.append(sig16)
                    byte_available[byte_idx] = False
                    byte_available[byte_idx + 1] = False
                    byte_idx += 2
                    continue
            byte_idx += 1

        # Phase 2: For any remaining available single bytes, emit 8-bit signal candidate
        for b_idx in range(dlc):
            if byte_available[b_idx]:
                sig8 = cls._evaluate_8bit_signal(payloads, b_idx)
                if sig8 is not None:
                    hypotheses.append(sig8)

        return hypotheses

    @classmethod
    def _evaluate_16bit_signal(cls, payloads: Sequence[bytes], byte_idx: int) -> Hypothesis | None:
        """Evaluate a 16-bit physical signal spanning byte_idx and byte_idx+1."""
        raw_b0 = [p[byte_idx] for p in payloads if len(p) > byte_idx + 1]
        raw_b1 = [p[byte_idx + 1] for p in payloads if len(p) > byte_idx + 1]

        if len(raw_b0) < 5:
            return None

        # Check activity: if both bytes are completely constant, it might be padding or constant
        b0_unique = len(set(raw_b0))
        b1_unique = len(set(raw_b1))
        if b0_unique == 1 and b1_unique == 1:
            # Constant 16-bit field
            return Hypothesis(
                htype="CONSTANT",
                start_bit=byte_idx * 8,
                length=16,
                is_little_endian=True,
                params={"constant_value": raw_b0[0] | (raw_b1[0] << 8)},
                confidence=0.95,
                evidence=[Evidence(kind="constancy", value=1.0, detail="Field has zero variance")],
                name=f"CONST_B{byte_idx}_16B",
            )

        # Endianness determination:
        # In Little Endian (Intel): byte_idx is LSB (higher unique count), byte_idx+1 is MSB (lower/smoother)
        is_le = b0_unique >= b1_unique

        values_le = [(p[byte_idx] | (p[byte_idx + 1] << 8)) for p in payloads if len(p) > byte_idx + 1]
        min_v = float(min(values_le))
        max_v = float(max(values_le))

        # Check for dynamic variability
        confidence = 0.85 if (max_v - min_v) > 0 else 0.50
        endian_str = "Little-Endian (Intel)" if is_le else "Big-Endian (Motorola)"

        return Hypothesis(
            htype="SIGNAL",
            start_bit=byte_idx * 8,
            length=16,
            is_little_endian=is_le,
            is_signed=False,
            min_value=min_v,
            max_value=max_v,
            confidence=confidence,
            evidence=[
                Evidence(
                    kind="entropy",
                    value=float(max(b0_unique, b1_unique)),
                    detail=f"16-bit candidate at bytes [{byte_idx}, {byte_idx+1}] in {endian_str}; range [{min_v:.0f}, {max_v:.0f}].",
                )
            ],
            name=f"SIG_B{byte_idx}_16B",
        )

    @classmethod
    def _evaluate_8bit_signal(cls, payloads: Sequence[bytes], byte_idx: int) -> Hypothesis | None:
        """Evaluate an 8-bit physical signal at byte_idx."""
        raw_bytes = [p[byte_idx] for p in payloads if len(p) > byte_idx]
        if not raw_bytes:
            return None

        unique_count = len(set(raw_bytes))
        min_v = float(min(raw_bytes))
        max_v = float(max(raw_bytes))

        if unique_count == 1:
            return Hypothesis(
                htype="CONSTANT",
                start_bit=byte_idx * 8,
                length=8,
                params={"constant_value": raw_bytes[0]},
                confidence=0.95,
                evidence=[Evidence(kind="constancy", value=1.0, detail=f"Byte {byte_idx} is constant 0x{raw_bytes[0]:02X}")],
                name=f"CONST_B{byte_idx}",
            )

        return Hypothesis(
            htype="SIGNAL",
            start_bit=byte_idx * 8,
            length=8,
            is_little_endian=True,
            is_signed=False,
            min_value=min_v,
            max_value=max_v,
            confidence=0.75,
            evidence=[
                Evidence(
                    kind="entropy",
                    value=float(unique_count),
                    detail=f"8-bit candidate at byte {byte_idx}; {unique_count} distinct values in range [{min_v:.0f}, {max_v:.0f}].",
                )
            ],
            name=f"SIG_B{byte_idx}_8B",
        )
