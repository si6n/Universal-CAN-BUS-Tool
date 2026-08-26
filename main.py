"""Universal CAN-Bus Diagnostic & Telemetry Platform - Root Launcher.

Allows launching directly from project root or IDE Solution Explorer.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path
_project_root = str(Path(__file__).resolve().parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.main import main

if __name__ == "__main__":
    sys.exit(main())
