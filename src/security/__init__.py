"""Security, Cryptography, Licensing and Anti-Tamper System."""

from src.security.anti_tamper.guard import AntiTamperGuard
from src.security.hwid.collector import (
    collect_bios_serial,
    collect_cpu_id,
    collect_cpu_processor_id,
    collect_disk_serial,
    collect_motherboard_uuid,
    collect_primary_mac,
    generate_hardware_fingerprint,
)
from src.security.knowledge_pack.pack_loader import (
    EncryptedKnowledgePackLoader,
    KnowledgePackManifest,
    secure_zero_memory,
)
from src.security.license.validator import (
    LicensePayload,
    LicenseValidator,
)

__all__ = [
    "AntiTamperGuard",
    "EncryptedKnowledgePackLoader",
    "KnowledgePackManifest",
    "LicensePayload",
    "LicenseValidator",
    "collect_bios_serial",
    "collect_cpu_id",
    "collect_cpu_processor_id",
    "collect_disk_serial",
    "collect_motherboard_uuid",
    "collect_primary_mac",
    "generate_hardware_fingerprint",
    "secure_zero_memory",
]
