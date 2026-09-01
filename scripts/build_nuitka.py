"""Nuitka C++ Native Standalone Compilation Pipeline for Universal CAN Platform.

Compiles all core Python modules (src.*) into native C++ machine binaries with Link Time
Optimization (LTO), stripping all Python source code (.py/.pyc) to prevent decompilation.
Bundles the React+Tailwind UI bundle and 133 curated DBCs into the standalone distribution.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def ensure_frontend_built(frontend_dir: Path) -> None:
    """Ensure React/Tailwind frontend is built and dist/index.html exists."""
    dist_index = frontend_dir / "dist" / "index.html"
    if not dist_index.is_file():
        print(f"Frontend dist not found at {dist_index}. Building via npm run build...")
        subprocess.check_call(["cmd", "/c", "npm run build"], cwd=frontend_dir)
        if not dist_index.is_file():
            raise FileNotFoundError(f"Frontend build failed: {dist_index} missing after build.")
    print(f"Frontend bundle verified: {dist_index}")


def run_nuitka_build(onefile: bool = False, console: bool = False) -> int:
    """Execute Nuitka native C++ compilation command."""
    root_dir = Path(__file__).parent.parent.resolve()
    entry_point = root_dir / "src" / "main.py"
    output_dir = root_dir / "dist"
    frontend_dir = root_dir / "src" / "ui" / "frontend"
    frontend_dist = frontend_dir / "dist"
    dbc_dir = root_dir / "data" / "dbc"

    if not entry_point.is_file():
        raise FileNotFoundError(f"Entry point not found: {entry_point}")

    ensure_frontend_built(frontend_dir)

    mode_flag = "--onefile" if onefile else "--standalone"
    console_mode = "force" if console else "disable"

    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        mode_flag,
        "--lto=yes",
        "--msvc=latest",
        "--jobs=8",
        "--output-filename=Universal-CAN-Tool.exe",
        f"--output-dir={output_dir}",
        f"--windows-console-mode={console_mode}",
        "--include-package=src",
        "--include-package-data=cantools",
        "--nofollow-import-to=pytest,unittest,hypothesis,setuptools",
        f"--include-data-dir={frontend_dist}=src/ui/frontend/dist",
    ]

    if dbc_dir.is_dir():
        cmd.append(f"--include-data-dir={dbc_dir}=data/dbc")

    icon_file = root_dir / "assets" / "icon.ico"
    if icon_file.is_file():
        cmd.append(f"--windows-icon-from-ico={icon_file}")

    cmd.extend([
        "--assume-yes-for-downloads",
        "--remove-output",
        str(entry_point),
    ])

    print("=" * 70)
    print("UNIVERSAL CAN PLATFORM - NUITKA NATIVE C++ BUILD PIPELINE")
    print(f"Target: {'OneFile' if onefile else 'Standalone Folder'}")
    print(f"Console Mode: {console_mode}")
    print("Source Protection: All src.* modules compiled to C++ machine code")
    print("=" * 70)
    print(f"Command: {' '.join(cmd)}\n")

    return subprocess.call(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Universal CAN Platform with Nuitka Native Compiler")
    parser.add_argument("--onefile", action="store_true", help="Build single standalone .exe file")
    parser.add_argument("--console", action="store_true", help="Keep console window open for debugging")
    args = parser.parse_args()
    return run_nuitka_build(onefile=args.onefile, console=args.console)


if __name__ == "__main__":
    sys.exit(main())
