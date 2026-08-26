"""Windows Hardware Fingerprint (HWID) Collection via WMI/CIM API.

Collects 4-component hardware identity as specified in MASTER_PLAN.md Section 2.3:
  1. Motherboard UUID (Win32_ComputerSystemProduct.UUID)
  2. CPU Processor ID (Win32_Processor.ProcessorId)
  3. System Physical Disk Serial (PhysicalDrive0 via Win32_DiskDrive)
  4. BIOS Serial Number (Win32_BIOS.SerialNumber)

These components are hashed together to produce a stable, deterministic hardware fingerprint.
"""

from __future__ import annotations

import hashlib
import platform
import subprocess
import sys
import uuid

from src.core.logging import get_logger

logger = get_logger("security.hwid")

# Sentinel values that indicate invalid/missing WMI data
_INVALID_UUIDS = frozenset(
    {
        "00000000-0000-0000-0000-000000000000",
        "ffffffff-ffff-ffff-ffff-ffffffffffff",
        "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF",
        "",
    }
)


def _run_powershell(command: str) -> str:
    """Execute a single PowerShell command and return the trimmed output."""
    if sys.platform != "win32":
        return ""
    try:
        cmd = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            command,
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError) as exc:
        logger.warning(f"PowerShell command failed: {command}", extra={"error": str(exc)})
        return ""


def _wmi_query(wmi_class: str, field: str) -> str:
    """Execute a single WMI query via PowerShell and return the trimmed value."""
    return _run_powershell(f"(Get-CimInstance -ClassName {wmi_class}).{field}")


def collect_motherboard_uuid() -> str:
    """Collect Motherboard UUID from Win32_ComputerSystemProduct."""
    uuid_str = _wmi_query("Win32_ComputerSystemProduct", "UUID")
    if uuid_str.upper() in _INVALID_UUIDS or not uuid_str:
        # Fallback: use machine name + platform node
        uuid_str = f"FALLBACK-{platform.node()}"
        logger.info("Motherboard UUID invalid, using fallback", extra={"fallback": uuid_str})
    return uuid_str


def collect_cpu_processor_id() -> str:
    """Collect CPU Processor ID from Win32_Processor."""
    return _wmi_query("Win32_Processor", "ProcessorId") or "UNKNOWN_CPU"


def collect_cpu_id() -> str:
    """Collect CPU Processor ID from Win32_Processor."""
    return collect_cpu_processor_id()


def collect_disk_serial() -> str:
    """Collect system disk serial from the boot drive (PhysicalDrive0)."""
    serial = _run_powershell("(Get-CimInstance -ClassName Win32_DiskDrive | Select-Object -First 1).SerialNumber")
    return serial.strip() if serial else "UNKNOWN_DISK"


def collect_bios_serial() -> str:
    """Collect BIOS Serial Number from Win32_BIOS."""
    return _wmi_query("Win32_BIOS", "SerialNumber") or "UNKNOWN_BIOS"


def collect_primary_mac() -> str:
    """Collect primary network adapter MAC address."""
    mac = _run_powershell(
        "(Get-CimInstance -ClassName Win32_NetworkAdapterConfiguration -Filter 'IPEnabled=True' | Select-Object -First 1).MACAddress"
    )
    if mac:
        return mac.strip()
    node = uuid.getnode()
    return ":".join(f"{(node >> i) & 0xFF:02X}" for i in range(40, -8, -8))


def generate_hardware_fingerprint() -> str:
    """Generate a deterministic SHA-256 hardware fingerprint from 4 components.

    Returns:
        64-character hex string representing the hardware identity hash.
    """
    if sys.platform != "win32":
        # Non-Windows: return a platform-based identifier (for dev/test)
        fallback = f"NON_WIN32-{platform.node()}-{platform.machine()}-{platform.processor()}"
        return hashlib.sha256(fallback.encode("utf-8")).hexdigest()

    mb_uuid = collect_motherboard_uuid()
    cpu_id = collect_cpu_processor_id()
    disk_serial = collect_disk_serial()
    bios_serial = collect_bios_serial()

    components = f"{mb_uuid}|{cpu_id}|{disk_serial}|{bios_serial}"

    fingerprint = hashlib.sha256(components.encode("utf-8")).hexdigest()

    logger.info(
        "Hardware fingerprint generated",
        extra={
            "mb_uuid": mb_uuid[:8] + "...",
            "cpu_id": cpu_id[:8] + "...",
            "disk": disk_serial[:8] + "...",
            "bios": bios_serial[:8] + "...",
        },
    )

    return fingerprint
