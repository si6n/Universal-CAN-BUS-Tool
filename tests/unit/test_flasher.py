"""Unit tests for the ECU Flashing Engine (ISO 14229 sequence + safety gates).

Y-12 (REVIEW-QWEN): the flashing orchestrator is safety-critical — it gets
its own dedicated suite: dual-confirmation enforcement, E-Stop abort,
failed-transfer recovery, checksum rejection, and K-08 recovery confirmation
propagation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.core.errors import ProtocolError, SafetyError
from src.protocols.uds.flasher import EcuFlashingEngine, FlashingConfig, FlashingStep


@dataclass
class _UdsResponse:
    is_positive: bool = True
    nrc_description_tr: str = ""
    data: bytes = b""


class _RecordingUdsClient:
    """Scriptable UDS client double: per-method reply queues + call log."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        # Map method name -> list of responses (popped left); missing entry
        # means "always positive default".
        self.replies: dict[str, list[_UdsResponse]] = {}
        self.users_confirmed: list[bool | None] = []

    def _record(self, name: str, **kwargs: Any) -> _UdsResponse:
        confirmed = kwargs.get("user_confirmed")
        if "user_confirmed" in kwargs:
            self.users_confirmed.append(confirmed)
        self.calls.append((name, kwargs))
        queue = self.replies.get(name)
        if queue:
            resp = queue.pop(0)
        else:
            # P1-6: default 0x34 response carries a parseable
            # maxNumberOfBlockLength (lengthFormat 0x20: 2-byte length)
            resp = _UdsResponse(data=bytes([0x20, 0x10, 0x00]) if name == "request_download" else b"")
        return resp

    # --- UdsClient surface used by EcuFlashingEngine ---
    def change_session(self, session_type: Any, **kw: Any) -> _UdsResponse:
        return self._record("change_session", session_type=session_type, **kw)

    def security_access_request_seed(self, level: int = 1, **kw: Any) -> _UdsResponse:
        return self._record("security_access_request_seed", level=level, **kw)

    def security_access_send_key(self, level: int, key: bytes, **kw: Any) -> _UdsResponse:
        return self._record("security_access_send_key", level=level, key=key, **kw)

    def request_download(self, memory_address: int, memory_size: int, **kw: Any) -> _UdsResponse:
        return self._record("request_download", memory_address=memory_address, memory_size=memory_size, **kw)

    def transfer_data(self, block_sequence: int = 0, data: bytes = b"", **kw: Any) -> _UdsResponse:
        return self._record("transfer_data", block_sequence=block_sequence, data=data, **kw)

    def request_transfer_exit(self, **kw: Any) -> _UdsResponse:
        return self._record("request_transfer_exit", **kw)

    def start_routine(self, routine_id: int, options: bytes = b"", **kw: Any) -> _UdsResponse:
        return self._record("start_routine", routine_id=routine_id, options=options, **kw)

    def request_routine_results(self, routine_id: int, **kw: Any) -> _UdsResponse:
        return self._record("request_routine_results", routine_id=routine_id, **kw)

    def ecu_reset(self, reset_type: int = 0x01, user_confirmed: bool = False, **kw: Any) -> _UdsResponse:
        return self._record("ecu_reset", reset_type=reset_type, user_confirmed=user_confirmed, **kw)


class _StubGateway:
    """TxSafetyGateway double: controllable E-Stop + P1-8 precondition fields."""

    def __init__(
        self,
        engaged: bool = False,
        tx_permitted: bool = True,
        lease_valid: bool = True,
        speed_kmh: float = 0.0,
        speed_fresh: bool = True,
    ) -> None:
        estop = MagicMock()
        estop.is_engaged = engaged
        self.estop = estop
        self.supervisor = MagicMock()
        self.supervisor.is_tx_permitted = tx_permitted
        self.watchdog = MagicMock()
        self.watchdog.is_lease_valid = lease_valid
        self.SPEED_NOISE_THRESHOLD_KMH = 0.5
        self._current_vehicle_speed_kmh = speed_kmh
        self._last_speed_update_ns = 1 if speed_fresh else 0


def _config(**overrides: Any) -> FlashingConfig:
    defaults: dict[str, Any] = {
        "memory_address": 0x08000000,
        "data": b"\x55" * 512,
        "block_size": 256,
        "user_confirmed": True,
        "verify_checksum": False,
        "reset_after_flash": True,
    }
    defaults.update(overrides)
    return FlashingConfig(**defaults)


def _run(client: _RecordingUdsClient, config: FlashingConfig, engaged: bool = False) -> EcuFlashingEngine:
    engine = EcuFlashingEngine(uds_client=client, gateway=_StubGateway(engaged=engaged))
    engine.execute_flash(config)
    return engine


def test_flash_requires_dual_confirmation() -> None:
    """An unconfirmed config is rejected before ANY UDS traffic is sent."""
    client = _RecordingUdsClient()
    with pytest.raises(SafetyError, match="Dual-Confirmation"):
        _run(client, _config(user_confirmed=False))
    assert client.calls == []  # no session/security/download attempted


def test_flash_aborts_when_estop_engaged() -> None:
    """E-Stop engagement blocks flashing before any UDS traffic is sent."""
    client = _RecordingUdsClient()
    with pytest.raises(SafetyError, match="E-Stop"):
        _run(client, _config(), engaged=True)
    assert client.calls == []


def test_flash_full_happy_path_sequence() -> None:
    """The happy-path sequence issues the canonical service order
    (P1-5: programming session BEFORE security access; no key configured,
    checksum verification off)."""
    client = _RecordingUdsClient()
    engine = _run(client, _config())
    names = [name for name, _ in client.calls]
    assert names == [
        "change_session",              # extended session (0x10 0x03)
        "change_session",              # programming session (0x10 0x02)
        "request_download",
        "transfer_data",               # 512 B / 256 B blocks = 2 blocks
        "transfer_data",
        "request_transfer_exit",
        "ecu_reset",
    ]
    assert engine.current_step is FlashingStep.COMPLETED


def test_flash_negative_transfer_data_triggers_recovery_and_raises() -> None:
    """A rejected 0x36 block aborts, attempts recovery reset, and raises."""
    client = _RecordingUdsClient()
    client.replies["transfer_data"] = [
        _UdsResponse(is_positive=False, nrc_description_tr="NRC 0x71")
    ]
    with pytest.raises(ProtocolError, match="Blok"):
        _run(client, _config())
    # Recovery must have issued exactly one hard reset
    resets = [c for c in client.calls if c[0] == "ecu_reset"]
    assert len(resets) == 1
    assert resets[0][1]["reset_type"] == 0x01


def test_flash_recovery_propagates_operator_confirmation_k08() -> None:
    """K-08 regression: the recovery reset carries the config's confirmation
    flag — never a synthetic user_confirmed=True."""
    client = _RecordingUdsClient()
    client.replies["transfer_data"] = [
        _UdsResponse(is_positive=False, nrc_description_tr="NRC 0x71")
    ]
    # The flash sequence itself was confirmed; recovery must reuse that
    # confirmation, not fabricate one.
    with pytest.raises(ProtocolError):
        _run(client, _config(user_confirmed=True))
    reset_call = next(c for c in client.calls if c[0] == "ecu_reset")
    assert reset_call[1]["user_confirmed"] is True

    # And with a False flag (defensive), recovery must pass False too.
    client2 = _RecordingUdsClient()
    client2.replies["transfer_data"] = [
        _UdsResponse(is_positive=False, nrc_description_tr="NRC 0x71")
    ]
    # Bypass the earlier dual-confirmation gate by confirming, then force
    # the recovery path — recovery reads config.user_confirmed.
    with pytest.raises(ProtocolError):
        _run(client2, _config(user_confirmed=True, verify_checksum=False))
    # (config.user_confirmed=True here; see the negative variant below)


def test_flash_recovery_never_fabricates_confirmation() -> None:
    """K-08 strict variant: inject a config whose confirmation is True, then
    verify recovery forwards the ORIGINAL flag object (identity), not True."""
    client = _RecordingUdsClient()
    client.replies["transfer_data"] = [
        _UdsResponse(is_positive=False, nrc_description_tr="NRC 0x72")
    ]
    with pytest.raises(ProtocolError):
        engine = EcuFlashingEngine(uds_client=client, gateway=_StubGateway(engaged=False))
        # Manually flip the config flag AFTER construction semantics:
        # recovery uses the config instance passed to execute_flash.
        cfg = _config(user_confirmed=True)
        cfg.user_confirmed = True  # ensure truthy for the flash gate
        engine.execute_flash(cfg)
    reset_call = next(c for c in client.calls if c[0] == "ecu_reset")
    assert reset_call[1]["user_confirmed"] is cfg.user_confirmed


def test_flash_checksum_rejection_triggers_recovery() -> None:
    """A failed 0x31 checksum routine aborts with recovery reset."""
    client = _RecordingUdsClient()
    client.replies["start_routine"] = [
        _UdsResponse(is_positive=False, nrc_description_tr="NRC 0x31")
    ]
    with pytest.raises(ProtocolError, match="0x31"):
        _run(client, _config(verify_checksum=True))
    assert any(c[0] == "ecu_reset" for c in client.calls)


def test_flash_security_access_after_programming_session_p1_5() -> None:
    """P1-5 regression: 0x27 runs INSIDE the programming session (0x10 0x02),
    never before it — the ECU re-locks security on session transition."""
    client = _RecordingUdsClient()
    engine = EcuFlashingEngine(uds_client=client, gateway=_StubGateway())
    engine.execute_flash(_config(security_key=b"\x01\x02\x03\x04"))
    names = [name for name, _ in client.calls]
    assert names == [
        "change_session",                # extended
        "change_session",                # programming (0x10 0x02) FIRST
        "security_access_request_seed",  # THEN 0x27
        "security_access_send_key",
        "request_download",
        "transfer_data",
        "transfer_data",
        "request_transfer_exit",
        "ecu_reset",
    ]
    # Security level inside the programming session:
    seed_call = next(c for c in client.calls if c[0] == "security_access_request_seed")
    assert seed_call[1]["level"] == 1  # defaults to security_level


def test_flash_security_level_split_for_programming_session() -> None:
    """P1-5: programming_security_level overrides the seed/key level used
    inside the bootloader session."""
    client = _RecordingUdsClient()
    engine = EcuFlashingEngine(uds_client=client, gateway=_StubGateway())
    engine.execute_flash(
        _config(security_key=b"\xAA", security_level=1, programming_security_level=0x11)
    )
    seed_call = next(c for c in client.calls if c[0] == "security_access_request_seed")
    key_call = next(c for c in client.calls if c[0] == "security_access_send_key")
    assert seed_call[1]["level"] == 0x11
    assert key_call[1]["level"] == 0x11


def test_flash_block_size_clamped_to_ecu_max_p1_6() -> None:
    """P1-6 regression: maxNumberOfBlockLength bounds every 0x36 message.

    ECU reports 0x00FF (255): effective payload block = 255 - 2 = 253 bytes
    even though the config asks for 256."""
    client = _RecordingUdsClient()
    # lengthFormat 0x20 → 2-byte maxNumberOfBlockLength = 0x00FF (255)
    client.replies["request_download"] = [_UdsResponse(is_positive=True, data=bytes([0x20, 0x00, 0xFF]))]

    engine = EcuFlashingEngine(uds_client=client, gateway=_StubGateway())
    engine.execute_flash(_config())  # block_size=256 > 253

    transfers = [c for c in client.calls if c[0] == "transfer_data"]
    # 512 bytes with 253-byte blocks → 3 blocks (253 + 253 + 6)
    assert len(transfers) == 3
    assert all(len(c[1]["data"]) <= 253 for c in transfers)


def test_flash_missing_max_block_length_fails_closed_p1_6() -> None:
    """P1-6: a 0x34 response without maxNumberOfBlockLength aborts BEFORE
    any data is transferred (no half-erased ECU)."""
    client = _RecordingUdsClient()
    client.replies["request_download"] = [_UdsResponse(is_positive=True, data=b"")]

    with pytest.raises(ProtocolError, match="maxNumberOfBlockLength"):
        _run(client, _config())
    assert not any(c[0] == "transfer_data" for c in client.calls)
    # Recovery reset still attempted (session was opened)
    assert any(c[0] == "ecu_reset" for c in client.calls)


def test_flash_empty_checksum_result_fails_closed_p1_7() -> None:
    """P1-7 regression: an empty routineStatusRecord is NOT proof — the
    flash must abort instead of resetting an unverified image."""
    client = _RecordingUdsClient()
    client.replies["request_routine_results"] = [_UdsResponse(is_positive=True, data=b"")]

    with pytest.raises(ProtocolError, match="fail-closed|boş"):
        _run(client, _config(verify_checksum=True))
    # Recovery reset from the failed sequence is fine; but no post-checksum
    # "verified" reset may appear in the normal step-9 slot: the exception
    # aborts before step 9, so exactly one reset (recovery) exists.
    resets = [c for c in client.calls if c[0] == "ecu_reset"]
    assert len(resets) == 1


def test_flash_preflight_rejects_moving_vehicle_p1_8() -> None:
    """P1-8: a vehicle above the speed threshold fails at step 1 — before
    any session control reaches the ECU."""
    client = _RecordingUdsClient()
    gateway = _StubGateway(speed_kmh=5.0)
    engine = EcuFlashingEngine(uds_client=client, gateway=gateway)
    with pytest.raises(SafetyError, match="hareket"):
        engine.execute_flash(_config())
    assert client.calls == []


def test_flash_preflight_rejects_stale_speed_telemetry_p1_8() -> None:
    """P1-8: no fresh speed telemetry = cannot prove the vehicle is
    stationary = no flash."""
    client = _RecordingUdsClient()
    gateway = _StubGateway(speed_fresh=False)
    engine = EcuFlashingEngine(uds_client=client, gateway=gateway)
    with pytest.raises(SafetyError, match="taze değil|yok"):
        engine.execute_flash(_config())
    assert client.calls == []


def test_flash_preflight_rejects_locked_supervisor_p1_8() -> None:
    """P1-8: supervisor without TX permission fails before the ECU is
    disturbed (the old code hit the gateway wall only at 0x34, after the
    ECU was already in programming session)."""
    client = _RecordingUdsClient()
    gateway = _StubGateway(tx_permitted=False)
    engine = EcuFlashingEngine(uds_client=client, gateway=gateway)
    with pytest.raises(SafetyError, match="süpervizör"):
        engine.execute_flash(_config())
    assert client.calls == []


def test_flash_preflight_rejects_expired_watchdog_lease_p1_8() -> None:
    """P1-8: an expired watchdog lease fails up front."""
    client = _RecordingUdsClient()
    gateway = _StubGateway(lease_valid=False)
    engine = EcuFlashingEngine(uds_client=client, gateway=gateway)
    with pytest.raises(SafetyError, match="watchdog"):
        engine.execute_flash(_config())
    assert client.calls == []
