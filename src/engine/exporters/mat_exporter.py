"""MATLAB (.mat) Telemetry Exporter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import savemat  # type: ignore[import-untyped]

from src.core.logging import get_logger

logger = get_logger("engine.exporters.mat")


class MatExporter:
    """Exports time series telemetry channels into MATLAB .mat files."""

    @classmethod
    def export_signals(
        cls,
        output_file: str | Path,
        signals_data: dict[str, tuple[list[float], list[float], str]],  # name -> (timestamps_s, values, unit)
    ) -> Path:
        """Export dictionary of signals into MATLAB .mat format."""
        path = Path(output_file)
        path.parent.mkdir(parents=True, exist_ok=True)

        mat_dict: dict[str, Any] = {}

        for sig_name, (timestamps, values, unit) in signals_data.items():
            clean_name = sig_name.replace(" ", "_").replace("-", "_")
            mat_dict[f"{clean_name}_time"] = np.array(timestamps, dtype=np.float64)
            mat_dict[f"{clean_name}_val"] = np.array(values, dtype=np.float64)
            mat_dict[f"{clean_name}_unit"] = unit

        savemat(str(path), mat_dict)
        logger.info("Saved MATLAB .mat file", extra={"file": str(path), "signals": len(signals_data)})
        return path
