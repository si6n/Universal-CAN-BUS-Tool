"""Hardware Abstraction Layer (HAL) CAN interface definitions and exports."""

from __future__ import annotations

from src.core.contracts.ports import InMemoryTxPort, TxPort
from src.hal.base import AbstractBus, BusMetrics, BusState
from src.hal.virtual import VirtualBus

__all__ = [
    "AbstractBus",
    "BusMetrics",
    "BusState",
    "InMemoryTxPort",
    "TxPort",
    "VirtualBus",
]
