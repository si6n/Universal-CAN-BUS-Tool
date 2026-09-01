"""Universal CAN-Bus Platform - Desktop Launcher & Bootstrap Controller.

Coordinates pre-flight environment checks, cloud authentication / HWID binding,
update validation, and secure execution of the core diagnostic application.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.logging import get_logger
from src.launcher.auth import AuthStatus, LauncherAuthManager
from src.launcher.prereqs import PrereqChecker, PrereqStatus
from src.launcher.updater import UpdateInfo, UpdateManager

logger = get_logger("launcher.app")


@dataclass(slots=True, frozen=True)
class LauncherPreflightReport:
    """Consolidated preflight readiness report."""

    can_launch: bool
    prereqs: list[PrereqStatus]
    auth_status: AuthStatus
    update_info: UpdateInfo
    target_executable: Path


class UniversalCanLauncher:
    """Master Launcher orchestration engine."""

    def __init__(self, current_version: str = "13.0.0") -> None:
        self.version = current_version
        self.auth_manager = LauncherAuthManager()
        self.update_manager = UpdateManager(current_version=self.version, cloud_client=self.auth_manager.client)

    @classmethod
    def resolve_target_executable(cls) -> Path:
        """Find the core application executable or main.py entry point."""
        root = Path(__file__).resolve().parent.parent.parent

        # 1. Check for Nuitka / PyInstaller compiled standalone executable
        dist_exe = root / "dist" / "Universal-CAN-Tool.exe"
        if dist_exe.is_file():
            return dist_exe

        standalone_dist = root / "dist" / "main.dist" / "Universal-CAN-Tool.exe"
        if standalone_dist.is_file():
            return standalone_dist

        # 2. Fallback to raw Python main.py
        return root / "src" / "main.py"

    def run_preflight(self, custom_update_manifest: dict[str, Any] | None = None) -> LauncherPreflightReport:
        """Execute all environment, auth, and update checks."""
        prereqs = PrereqChecker.run_all_checks()
        has_critical_failures = any(not p.is_available and p.is_critical for p in prereqs)

        auth_status = self.auth_manager.get_current_status()
        update_info = self.update_manager.check_for_updates(custom_manifest=custom_update_manifest)
        target_exe = self.resolve_target_executable()

        can_launch = not has_critical_failures and target_exe.exists()

        return LauncherPreflightReport(
            can_launch=can_launch,
            prereqs=prereqs,
            auth_status=auth_status,
            update_info=update_info,
            target_executable=target_exe,
        )

    def launch_main_app(self, extra_args: list[str] | None = None) -> int:
        """Spawn the core application executable."""
        target = self.resolve_target_executable()
        args = extra_args or []

        if target.suffix == ".py":
            cmd = [sys.executable, str(target)] + args
        else:
            cmd = [str(target)] + args

        logger.info("Launching Universal CAN Platform", extra={"target": str(target), "args": args})
        return subprocess.call(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(description="Universal CAN Platform - Launcher & Auto-Updater")
    parser.add_argument("--check-only", action="store_true", help="Run preflight checks and exit")
    parser.add_argument("--activate", type=str, help="Activate cloud license key")
    parser.add_argument("--device-name", type=str, default="Desktop Diagnostic Tool", help="Device name for registration")
    parser.add_argument("--launch", action="store_true", help="Launch the main application immediately")

    args, unknown = parser.parse_known_args()
    launcher = UniversalCanLauncher()

    if args.activate:
        print(f"Activating license key: {args.activate}...")
        try:
            claims = launcher.auth_manager.activate_with_key(args.activate, device_name=args.device_name)
            print(f"License Activated Successfully! Tier: {claims.tier}, Features: {list(claims.features)}")
        except Exception as exc:
            print(f"Activation Failed: {exc}")
            return 1

    report = launcher.run_preflight()
    print("=" * 65)
    print("UNIVERSAL CAN-BUS PLATFORM - LAUNCHER PRE-FLIGHT DIAGNOSTICS")
    print("=" * 65)
    print(f"Version: v{launcher.version} | HWID: {report.auth_status.hwid}")
    print(f"License Tier: {report.auth_status.tier} | Active: {report.auth_status.has_valid_license}")
    print(f"Target Binary: {report.target_executable}")
    print("-" * 65)
    print("Prerequisites & Drivers:")
    for p in report.prereqs:
        icon = "OK" if p.is_available else ("FAIL" if p.is_critical else "WARN")
        print(f"  [{icon}] {p.name}: {p.details}")
    print("-" * 65)

    if report.update_info.has_update:
        print(f"UPDATE AVAILABLE: v{report.update_info.latest_version} (Current: v{report.update_info.current_version})")
        if report.update_info.release_notes:
            print(f"  Release Notes: {report.update_info.release_notes}")

    if args.check_only:
        return 0 if report.can_launch else 1

    if report.can_launch or args.launch:
        return launcher.launch_main_app(extra_args=unknown)

    return 0


if __name__ == "__main__":
    sys.exit(main())
