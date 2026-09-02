"""Universal CAN Cloud client integration (MASTER_PLAN Tasks 5.3 & 5.4 — client side).

 Bridges the desktop application to the Universal-CAN-Cloud SaaS:
   - Device registration  : POST /api/v1/devices/register  (HWID + DPAPI token store)
   - License activation  : POST /api/v1/licenses/activate  (Ed25519 ticket)
   - Telemetry upload    : resumable chunked MDF4 upload   (session -> chunks -> complete)
"""

from src.security.cloud.client import CloudClient, CloudConfig
from src.security.cloud.license_flow import DeviceRegistration, LicenseFlow
from src.security.cloud.telemetry_uploader import TelemetryUploader, UploadProgress

__all__ = [
    "CloudClient",
    "CloudConfig",
    "DeviceRegistration",
    "LicenseFlow",
    "TelemetryUploader",
    "UploadProgress",
]
