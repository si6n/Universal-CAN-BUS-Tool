"""Nuitka C++ Standalone Compilation Script for Universal CAN Platform.

Builds a fully optimized, native C++ standalone executable with LTO and encrypted bytecode.
Bundles the modern React+Tailwind UI bundle into the single executable package.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_nuitka_build() -> int:
    """Execute Nuitka native compilation command."""
    root_dir = Path(__file__).parent.parent.resolve()  # F-41: absolute, symlink-safe
    entry_point = root_dir / "src" / "main.py"
    output_dir = root_dir / "dist"
    frontend_dist = root_dir / "src" / "ui" / "frontend" / "dist"

    if not entry_point.is_file():
        raise FileNotFoundError(f"Entry point not found: {entry_point}")
    if not (frontend_dist / "index.html").is_file():
        raise FileNotFoundError(
            f"Frontend dist missing: {frontend_dist} — run 'npm run build' in src/ui/frontend first"
        )

    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--lto=yes",
        "--include-package=src",
        f"--include-data-dir={frontend_dist}=src/ui/frontend/dist",
        f"--output-dir={output_dir}",
        "--windows-icon-from-ico=assets/icon.ico" if (root_dir / "assets" / "icon.ico").exists() else "",
        "--assume-yes-for-downloads",
        str(entry_point),
    ]

    cmd = [arg for arg in cmd if arg]
    print(f"Executing Nuitka build: {' '.join(cmd)}")
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(run_nuitka_build())
