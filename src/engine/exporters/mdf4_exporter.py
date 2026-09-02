"""ASAM MDF4 (.mf4) Standard Binary Telemetry Exporter."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from asammdf import MDF, Signal

from src.core.logging import get_logger

logger = get_logger("engine.exporters.mdf4")


class Mdf4Exporter:
    """Exports time series telemetry channels into ASAM MDF4 (.mf4) files."""

    @classmethod
    def export_signals(
        cls,
        output_file: str | Path,
        signals_data: dict[str, tuple[list[float], list[float], str]],  # name -> (timestamps_s, values, unit)
    ) -> Path:
        """Export dictionary of signals into MDF4.

        Args:
            output_file: Target path ending in .mf4
            signals_data: Dict mapping signal_name -> (timestamps_s, values, unit)
        """
        path = Path(output_file)
        path.parent.mkdir(parents=True, exist_ok=True)

        mdf = MDF()
        signal_list: list[Signal] = []

        for sig_name, (timestamps, values, unit) in signals_data.items():
            if not timestamps or not values:
                continue

            t_arr = np.array(timestamps, dtype=np.float64)
            v_arr = np.array(values, dtype=np.float64)

            sig = Signal(
                samples=v_arr,
                timestamps=t_arr,
                name=sig_name,
                unit=unit,
            )
            signal_list.append(sig)

        if signal_list:
            mdf.append(signal_list)

        mdf.save(str(path), overwrite=True)
        logger.info("Saved ASAM MDF4 file", extra={"file": str(path), "signals": len(signal_list)})
        return path
