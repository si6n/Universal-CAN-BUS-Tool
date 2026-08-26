"""Automated One-Click Standalone Windows .EXE Builder for Universal CAN-Bus Diagnostic v13.0."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def build_exe() -> int:
    root_dir = Path(__file__).parent.parent.resolve()
    frontend_dir = root_dir / "src" / "ui" / "frontend"
    frontend_dist = frontend_dir / "dist"

    print("==================================================")
    print(">>> Universal CAN-Bus Platform v13.0 - EXE Builder")
    print("==================================================")

    # 1. Check & Build Frontend if needed
    if not frontend_dist.exists() or not (frontend_dist / "index.html").exists():
        print("[1/2] Frontend React+Tailwind paketi derleniyor...")
        ret = subprocess.call('cmd.exe /c "npm run build"', cwd=str(frontend_dir), shell=True)
        if ret != 0:
            print("[HATA] Frontend derleme hatasi!")
            return ret
    else:
        print("[1/2] Frontend React+Tailwind paketi hazir.")

    # 2. Package into Ultra-Fast & Compact Standalone .EXE using PyInstaller
    print("[2/2] Tek parca Windows .EXE derleniyor...")
    entry_point = root_dir / "src" / "main.py"
    data_arg = f"{frontend_dist};src/ui/frontend/dist"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=Universal_CAN_Diagnostic",
        "--onefile",
        "--noconsole",
        "--clean",
        f"--add-data={data_arg}",
        # Exclude legacy unused heavy GUI packages
        "--exclude-module=PySide6",
        "--exclude-module=pyqtgraph",
        "--exclude-module=shiboken6",
        "--exclude-module=tkinter",
        "--exclude-module=matplotlib",
        # Explicit hidden imports for webview and automotive CAN engine
        "--hidden-import=webview",
        "--hidden-import=clr_loader",
        "--hidden-import=pythonnet",
        "--hidden-import=bottle",
        "--hidden-import=proxy_tools",
        "--hidden-import=can",
        "--hidden-import=cantools",
        "--hidden-import=asammdf",
        f"--distpath={root_dir / 'dist'}",
        f"--workpath={root_dir / 'build'}",
        str(entry_point),
    ]

    print("Komut calistiriliyor...")
    ret = subprocess.call(cmd, cwd=str(root_dir))
    if ret == 0:
        exe_path = root_dir / "dist" / "Universal_CAN_Diagnostic.exe"
        print("==================================================")
        print("TEBRIKLER! .EXE dosyaniz basariyla olusturuldu:")
        print(f"Dosya Konumu: {exe_path}")
        print("==================================================")
    return ret


if __name__ == "__main__":
    sys.exit(build_exe())
