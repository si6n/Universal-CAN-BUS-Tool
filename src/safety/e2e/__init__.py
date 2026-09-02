"""Universal CAN-Bus Diagnostic & Telemetry Platform - E2E Safety Subsystem.

Provides comprehensive End-to-End (E2E) functional safety modules:
- CRC-8 Algorithms & 256-entry lookup tables (SAE J1850 0x1D, AUTOSAR 0x2F)
- Standardized & OEM Profiles (AUTOSAR P1/P2, Toyota, VAG MQB, Volvo)
- Stateful Rx Validation Engine (E2ESafetyValidator)
- Outbound Tx Packaging Engine (E2ESafetyPackager)

Compliant with ISO 26262 ASIL-D, AUTOSAR CP R4.4, and SAE J1850.
"""

from src.safety.e2e.crc import (
    CRC8_TABLE_0X1D,
    CRC8_TABLE_0X2F,
    DEFAULT_CRC_INIT,
    DEFAULT_CRC_XOR,
    POLYNOMIAL_0X1D,
    POLYNOMIAL_0X2F,
    calculate_crc8,
    calculate_crc8_0x1d,
    calculate_crc8_0x2f,
    calculate_crc8_bitwise,
    calculate_crc8_sae_j1850,
    calculate_crc8_update,
    generate_crc8_table,
)
from src.safety.e2e.packager import E2ESafetyPackager
from src.safety.e2e.profiles import (
    E2EProfileConfig,
    E2EProfileType,
    E2EStatus,
    compute_checksum,
    extract_counter,
    extract_crc,
    inject_counter,
    inject_crc,
)
from src.safety.e2e.validator import (
    E2ESafetyValidator,
    E2EValidationResult,
    StreamRxState,
)

__all__ = [
    "CRC8_TABLE_0X1D",
    "CRC8_TABLE_0X2F",
    "DEFAULT_CRC_INIT",
    "DEFAULT_CRC_XOR",
    "POLYNOMIAL_0X1D",
    "POLYNOMIAL_0X2F",
    "E2EProfileConfig",
    "E2EProfileType",
    "E2ESafetyPackager",
    "E2ESafetyValidator",
    "E2EStatus",
    "E2EValidationResult",
    "StreamRxState",
    "calculate_crc8",
    "calculate_crc8_0x1d",
    "calculate_crc8_0x2f",
    "calculate_crc8_bitwise",
    "calculate_crc8_sae_j1850",
    "calculate_crc8_update",
    "compute_checksum",
    "extract_counter",
    "extract_crc",
    "generate_crc8_table",
    "inject_counter",
    "inject_crc",
]
