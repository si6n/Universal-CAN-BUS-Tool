"""High-Reliability ISO 14229 UDS ECU Flashing & Bootloader Reprogramming Engine.

Enforces CORE_SAFETY_FLOOR, dual-confirmation, and full UDS download sequence
(0x10 Extended/Programming -> 0x27 SecurityAccess -> 0x34 RequestDownload ->
 0x36 TransferData in blocks -> 0x37 RequestTransferExit -> 0x31 RoutineControl Checksum -> 0x11 ECUReset).
"""

from __future__ import annotations

import time
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from src.core.errors import ProtocolError, SafetyError
from src.core.logging import get_logger
from src.protocols.uds.services import DiagnosticSessionType

if TYPE_CHECKING:
    from src.protocols.uds.client import UdsClient
    from src.safety.gateway import TxSafetyGateway

logger = get_logger("protocols.uds.flasher")


class FlashingStep(StrEnum):
    """Sequential stages of the ECU reprogramming lifecycle."""

    IDLE = "Boşta (Hazır)"
    SAFETY_VALIDATION = "1. Güvenlik & Hız Kilidi Doğrulaması"
    EXTENDED_SESSION = "2. Genişletilmiş Diyagnostik Oturumu (0x10 0x03)"
    SECURITY_ACCESS = "3. Güvenlik Erişimi & Tohum-Anahtar (0x27)"
    PROGRAMMING_SESSION = "4. Programlama / Bootloader Oturumu (0x10 0x02)"
    REQUEST_DOWNLOAD = "5. Bellek İndirme Talebi (0x34)"
    TRANSFER_DATA = "6. Blok Veri Aktarımı (0x36)"
    TRANSFER_EXIT = "7. Aktarım Çıkışı ve Tamamlama (0x37)"
    CHECKSUM_VERIFICATION = "8. Sağlama Toplamı / CRC32 Doğrulaması (0x31)"
    ECU_RESET = "9. ECU Yeniden Başlatma / Hard Reset (0x11)"
    COMPLETED = "10. Flashing Başarıyla Tamamlandı"
    FAILED = "Hata / İptal Edildi"


@dataclass(slots=True)
class FlashingConfig:
    """Reprogramming configuration payload."""

    memory_address: int
    data: bytes
    block_size: int = 256  # 64, 128, 256, 512, 1024, 4096 bytes
    security_level: int = 1
    security_key: bytes | None = None
    # P1-5: ISO 14229 re-locks security on session transitions — the
    # programming session typically requires its own (usually higher)
    # security level. Defaults to security_level when not set.
    programming_security_level: int | None = None
    verify_checksum: bool = True
    checksum_routine_id: int = 0x0202
    reset_after_flash: bool = True
    reset_type: int = 0x01  # Hard Reset
    user_confirmed: bool = False

    def __post_init__(self) -> None:
        if self.block_size <= 0:
            raise ValueError(f"Invalid block_size {self.block_size}. Must be greater than 0.")
        if not self.data:
            raise ValueError("Flashing payload data cannot be empty.")

    @property
    def effective_programming_security_level(self) -> int:
        """Security level applied inside the programming session."""
        return self.programming_security_level if self.programming_security_level is not None else self.security_level


@dataclass(slots=True)
class FlashingProgress:
    """Progress update telemetry emitted to UI/callbacks."""

    current_step: FlashingStep
    step_index: int
    total_steps: int
    bytes_transferred: int
    total_bytes: int
    percent: float
    transfer_speed_kbps: float
    elapsed_time_s: float
    crc32_checksum: str


class EcuFlashingEngine:
    """Deterministic, step-by-step UDS ECU reprogramming orchestrator."""

    TOTAL_STEPS: int = 10

    def __init__(
        self,
        uds_client: UdsClient,
        gateway: TxSafetyGateway,
        on_progress: Callable[[FlashingProgress], None] | None = None,
        on_log: Callable[[str, str], None] | None = None,
    ) -> None:
        self.uds_client = uds_client
        self.gateway = gateway
        self.on_progress = on_progress
        self.on_log = on_log

        self.current_step: FlashingStep = FlashingStep.IDLE
        self._is_cancelled = False

    def cancel(self) -> None:
        """Signal engine to abort flashing safely at next boundary."""
        self._is_cancelled = True
        self._log("İptal talebi alındı! Flashing durduruluyor...", "warning")

    def _check_cancelled(self) -> None:
        """P1-8: cancellation is honoured at EVERY step boundary, not only
        inside the 0x36 loop — steps 2-9 can each take seconds on a slow bus."""
        if self._is_cancelled:
            raise ProtocolError("Flashing kullanıcı tarafından iptal edildi.")

    @staticmethod
    def _parse_max_block_length(download_response: Any) -> int:
        """Parse maxNumberOfBlockLength from a positive 0x34 response (P1-6).

        Response layout per ISO 14229-1 §14.2:
            lengthFormatIdentifier (1B) | maxNumberOfBlockLength (n bytes)

        The high nibble encodes the width (1..8, 0xF = variable) and the
        low nibble the address unit size. An unparsable/absent value fails
        closed — the caller must never flash with an unbounded block size.
        """
        data = getattr(download_response, "data", None)
        if not data or len(data) < 1:
            raise ProtocolError(
                "0x34 yanıtı maxNumberOfBlockLength içermiyor — sınırsız blok boyutu ile flash reddedildi (fail-closed)"
            )
        length_format = data[0]
        num_bytes = (length_format >> 4) & 0x0F
        if not (1 <= num_bytes <= 8):
            raise ProtocolError(
                f"0x34 yanıtı geçersiz lengthFormatIdentifier (0x{length_format:02X}) — flash reddedildi (fail-closed)"
            )
        raw = bytes(data[1 : 1 + num_bytes])
        if len(raw) < num_bytes:
            raise ProtocolError("0x34 yanıtı maxNumberOfBlockLength alanı kesik — flash reddedildi (fail-closed)")
        value = int.from_bytes(raw, byteorder="big")
        if value <= 0:
            raise ProtocolError("0x34 yanıtı maxNumberOfBlockLength=0 — flash reddedildi (fail-closed)")
        return value

    def _assert_gateway_preconditions(self) -> None:
        """P1-8: verify every TX precondition before touching the ECU.

        Once the first session-control frame leaves, a mid-sequence gateway
        rejection leaves the ECU in a programming session with the recovery
        reset itself blocked (ESTOP_ACTIVE). Checking supervisor state,
        watchdog lease, and speed interlock up front turns those failures
        into step-1 SafetyErrors — before the ECU is disturbed.
        """
        estop = self.gateway.estop
        if estop.is_engaged:
            raise SafetyError("E-Stop aktifken flashing yapılamaz!")

        supervisor = getattr(self.gateway, "supervisor", None)
        if supervisor is not None and not getattr(supervisor, "is_tx_permitted", True):
            raise SafetyError(
                "Güvenlik süpervizörü TX izni vermiyor (FAULT/ARMED olmayan durum) — flashing reddedildi."
            )

        watchdog = getattr(self.gateway, "watchdog", None)
        if watchdog is not None and not getattr(watchdog, "is_lease_valid", True):
            raise SafetyError(
                "TX watchdog kira süresi geçersiz — flashing reddedildi (lease yenileyin)."
            )

        # Speed interlock: gateway exposes the freshest speed telemetry.
        last_update_ns = getattr(self.gateway, "_last_speed_update_ns", None)
        if last_update_ns == 0:
            raise SafetyError("Hız telemetrisi yok/taze değil — hareketli araçta flashing reddedildi.")
        speed = getattr(self.gateway, "_current_vehicle_speed_kmh", 0.0)
        threshold = getattr(self.gateway, "SPEED_NOISE_THRESHOLD_KMH", 0.5)
        if speed is not None and speed > threshold:
            raise SafetyError(
                f"Araç hareket halinde ({speed:.1f} km/s > {threshold} km/s) — flashing reddedildi."
            )

    def _log(self, message: str, level: str = "info") -> None:
        if self.on_log:
            self.on_log(message, level)
        if level == "error":
            logger.error(message)
        elif level == "warning":
            logger.warning(message)
        else:
            logger.info(message)

    def _emit_progress(
        self,
        step: FlashingStep,
        step_idx: int,
        bytes_sent: int,
        total_bytes: int,
        start_time: float,
        crc_str: str,
    ) -> None:
        self.current_step = step
        now = time.monotonic()
        elapsed = max(0.001, now - start_time)
        pct = (bytes_sent / total_bytes * 100.0) if total_bytes > 0 else 0.0
        speed_kbps = (bytes_sent / 1024.0) / elapsed

        progress = FlashingProgress(
            current_step=step,
            step_index=step_idx,
            total_steps=self.TOTAL_STEPS,
            bytes_transferred=bytes_sent,
            total_bytes=total_bytes,
            percent=round(pct, 1),
            transfer_speed_kbps=round(speed_kbps, 2),
            elapsed_time_s=round(elapsed, 2),
            crc32_checksum=crc_str,
        )

        if self.on_progress:
            self.on_progress(progress)

    def execute_flash(self, config: FlashingConfig) -> bool:
        """Execute full end-to-end ECU flashing cycle synchronously."""
        self._is_cancelled = False
        start_time = time.monotonic()
        total_bytes = len(config.data)
        if total_bytes == 0:
            raise ValueError("Flashing payload data is empty")

        crc32_val = zlib.crc32(config.data) & 0xFFFFFFFF
        crc_hex = f"0x{crc32_val:08X}"

        self._log(
            f"🚀 Flashing Başlatılıyor: Boyut={total_bytes} bayt, Hedef Adres=0x{config.memory_address:08X}, CRC32={crc_hex}",
            "info",
        )

        recovery_needed = False
        try:
            # 1. Safety Validation
            self._emit_progress(FlashingStep.SAFETY_VALIDATION, 1, 0, total_bytes, start_time, crc_hex)
            self._log("Adım 1/10: Hız kilidi ve güvenlik kontrolleri yapılıyor...", "info")
            if not config.user_confirmed:
                raise SafetyError("Flashing işlemi operatörün açık çift onayını (Dual-Confirmation) gerektirir.")

            if self.gateway.estop.is_engaged:
                raise SafetyError("Acil Durdurma (E-Stop) aktifken flashing yapılamaz!")

            # P1-8: verify ALL gateway preconditions BEFORE a single byte
            # reaches the ECU. Once the ECU leaves its default session a
            # failed TX must recover it — cheaper to fail here, at step 1.
            self._assert_gateway_preconditions()

            # 2. Extended Diagnostic Session
            self._emit_progress(FlashingStep.EXTENDED_SESSION, 2, 0, total_bytes, start_time, crc_hex)
            self._log("Adım 2/10: Genişletilmiş Diyagnostik Oturumu (0x10 0x03) açılıyor...", "info")
            self._check_cancelled()
            resp = self.uds_client.change_session(DiagnosticSessionType.EXTENDED_DIAGNOSTIC_SESSION)
            if not resp.is_positive:
                raise ProtocolError(f"Genişletilmiş oturum açılamadı: {resp.nrc_description_tr} (NRC 0x{resp.nrc:02X})")
            # From here on the ECU is out of its default session; a failure
            # must attempt best-effort recovery before surfacing the error.
            recovery_needed = True

            # 3. Programming Session (P1-5: 0x10 0x02 BEFORE 0x27 — the ECU
            # re-locks security access on session transition; the normative
            # reprogramming order is 0x10 0x02 -> 0x27 -> 0x34, with the
            # bootloader applying its own seed/key ladder).
            self._emit_progress(FlashingStep.PROGRAMMING_SESSION, 3, 0, total_bytes, start_time, crc_hex)
            self._log("Adım 3/10: Bootloader Programlama Oturumu (0x10 0x02) açılıyor...", "info")
            self._check_cancelled()
            resp = self.uds_client.change_session(DiagnosticSessionType.PROGRAMMING_SESSION)
            if not resp.is_positive:
                raise ProtocolError(f"Programlama oturumuna geçilemedi: {resp.nrc_description_tr}")

            # 4. Security Access inside the programming session (optional/if configured)
            self._emit_progress(FlashingStep.SECURITY_ACCESS, 4, 0, total_bytes, start_time, crc_hex)
            if config.security_key is not None:
                sec_level = config.effective_programming_security_level
                self._log(f"Adım 4/10: Güvenlik Erişimi (0x27 Level {sec_level}) doğrulanıyor...", "info")
                self._check_cancelled()
                seed_resp = self.uds_client.security_access_request_seed(level=sec_level)
                if not seed_resp.is_positive:
                    raise ProtocolError(f"Güvenlik tohumu alınamadı: {seed_resp.nrc_description_tr}")
                key_resp = self.uds_client.security_access_send_key(level=sec_level, key=config.security_key)
                if not key_resp.is_positive:
                    raise ProtocolError(f"Güvenlik anahtarı reddedildi: {key_resp.nrc_description_tr}")
                self._log("Güvenlik kilidi başarıyla açıldı.", "info")
            else:
                self._log("Adım 4/10: Güvenlik Erişimi adımı atlandı (Anahtarsız mod).", "info")

            # 5. Request Download
            self._emit_progress(FlashingStep.REQUEST_DOWNLOAD, 5, 0, total_bytes, start_time, crc_hex)
            self._log(
                f"Adım 5/10: İndirme Talebi (0x34) gönderiliyor (Adres: 0x{config.memory_address:08X}, Boyut: {total_bytes})...",
                "info",
            )
            self._check_cancelled()
            resp = self.uds_client.request_download(
                memory_address=config.memory_address,
                memory_size=total_bytes,
                user_confirmed=config.user_confirmed,
            )
            if not resp.is_positive:
                raise ProtocolError(f"RequestDownload ECU tarafından reddedildi: {resp.nrc_description_tr}")

            # P1-6: the ECU's maxNumberOfBlockLength bounds every 0x36
            # message (SID + BSC + payload). Effective block size is
            # min(config, max_len - 2); an unparsable/absent value fails
            # closed — flashing with an unbounded block size is how a
            # half-erased ECU happens.
            max_block_len = self._parse_max_block_length(resp)
            effective_block_size = min(config.block_size, max(max_block_len - 2, 1))
            if effective_block_size < config.block_size:
                self._log(
                    f"Blok boyutu ECU sınırına göre {config.block_size} → {effective_block_size} bayta düşürüldü "
                    f"(maxNumberOfBlockLength={max_block_len}).",
                    "info",
                )

            # 6. Transfer Data in Blocks
            self._log(f"Adım 6/10: Blok aktarımı başlatılıyor (Blok Boyutu: {effective_block_size} B)...", "info")
            bytes_sent = 0
            block_seq = 1

            while bytes_sent < total_bytes:
                self._check_cancelled()

                chunk = config.data[bytes_sent : bytes_sent + effective_block_size]
                resp = self.uds_client.transfer_data(block_sequence=block_seq, data=chunk)
                if not resp.is_positive:
                    raise ProtocolError(f"Blok #{block_seq} aktarımı reddedildi: {resp.nrc_description_tr}")

                # P1-6: verify the ECU echoed our block sequence counter.
                if resp.data and len(resp.data) >= 1 and resp.data[0] != (block_seq & 0xFF):
                    raise ProtocolError(
                        f"Blok #{block_seq} yanıtı BSC uyuşmazlığı (ECU: {resp.data[0]:02X})"
                    )

                bytes_sent += len(chunk)
                block_seq = (block_seq + 1) & 0xFF  # Wraps naturally from 0xFF to 0x00 per ISO 14229-1

                self._emit_progress(
                    FlashingStep.TRANSFER_DATA,
                    6,
                    bytes_sent,
                    total_bytes,
                    start_time,
                    crc_hex,
                )

            self._log(f"Tüm {total_bytes} bayt başarıyla aktarıldı.", "info")

            # 7. Request Transfer Exit
            self._emit_progress(FlashingStep.TRANSFER_EXIT, 7, total_bytes, total_bytes, start_time, crc_hex)
            self._log("Adım 7/10: Aktarım Çıkışı (0x37) gönderiliyor...", "info")
            self._check_cancelled()
            resp = self.uds_client.request_transfer_exit()
            if not resp.is_positive:
                raise ProtocolError(f"RequestTransferExit reddedildi: {resp.nrc_description_tr}")

            # 8. Checksum / Routine Verification
            self._emit_progress(FlashingStep.CHECKSUM_VERIFICATION, 8, total_bytes, total_bytes, start_time, crc_hex)
            if config.verify_checksum:
                self._check_cancelled()
                self._log(f"Adım 8/10: Sağlama toplamı doğrulanıyor (CRC32: {crc_hex})...", "info")
                crc_bytes = crc32_val.to_bytes(4, byteorder="big")
                resp = self.uds_client.start_routine(
                    routine_id=config.checksum_routine_id,
                    options=crc_bytes,
                    user_confirmed=config.user_confirmed,
                )
                if not resp.is_positive:
                    raise ProtocolError(f"Sağlama toplamı doğrulama başlatılamadı: {resp.nrc_description_tr}")

                # P2: Request Routine Results (0x31 0x03) to ensure ECU validates CRC
                result_resp = self.uds_client.request_routine_results(routine_id=config.checksum_routine_id)
                if not result_resp.is_positive:
                    raise ProtocolError(f"Sağlama toplamı sonuç sorgusu reddedildi: {result_resp.nrc_description_tr}")

                # P1-7: an empty routineStatusRecord is NOT proof of a valid
                # image — fail closed. Resetting an unverified (possibly
                # corrupt) image is the brick path.
                if not result_resp.data or len(result_resp.data) < 1:
                    raise ProtocolError(
                        "ECU sağlama toplamı sonucu boş döndü (routineStatusRecord yok) — "
                        "doğrulanmamış imaj üzerinde reset atılamaz (fail-closed)"
                    )
                status_code = result_resp.data[0]
                if status_code not in (0x00, 0x01):
                    raise ProtocolError(f"ECU sağlama toplamı (CRC32) uyumsuzluğu tespit etti (Durum: 0x{status_code:02X})")

                self._log("✅ Sağlama toplamı (CRC32) ECU tarafından başarıyla doğrulandı.", "info")
            else:
                self._log("Adım 8/10: Sağlama toplamı doğrulama adımı atlandı.", "info")

            # 9. ECU Reset
            self._emit_progress(FlashingStep.ECU_RESET, 9, total_bytes, total_bytes, start_time, crc_hex)
            if config.reset_after_flash:
                self._check_cancelled()
                self._log("Adım 9/10: ECU yeniden başlatılıyor (Hard Reset 0x11)...", "info")
                with_reset_resp = self.uds_client.ecu_reset(
                    reset_type=config.reset_type, user_confirmed=config.user_confirmed
                )
                if not with_reset_resp.is_positive:
                    self._log(f"ECU Reset uyarısı: {with_reset_resp.nrc_description_tr}", "warning")
                else:
                    self._log("ECU Reset komutu kabul edildi.", "info")

            # 10. Completed
            self._emit_progress(FlashingStep.COMPLETED, 10, total_bytes, total_bytes, start_time, crc_hex)
            elapsed_final = time.monotonic() - start_time
            self._log(f"🎉 ECU Flashing işlemi {elapsed_final:.2f} saniyede BAŞARIYLA TAMAMLANDI!", "info")
            return True

        except Exception as exc:
            self.current_step = FlashingStep.FAILED
            self._log(f"❌ Flashing Hatası: {exc}", "error")
            if recovery_needed:
                self._best_effort_recovery(config)
            raise

    def _best_effort_recovery(self, config: FlashingConfig) -> None:
        """Attempt to return the ECU to a safe state after a failed flash.

        The incomplete transfer is deliberately NOT finalized (no 0x37); a hard
        reset (0x11 0x01) lets the bootloader validate/discard the uncommitted
        image on its own. Recovery failures are logged and swallowed so they
        never mask the original error.

        K-08: the operator confirmation flows from the flashing config —
        recovery never grants dual-confirmation on its own. (Recovery is only
        reachable from an already operator-confirmed flashing sequence, but
        the gateway must see the original confirmation, not a synthetic one.)
        """
        self._log("Kurtarma: ECU güvenli duruma döndürülmeye çalışılıyor (Hard Reset)...", "warning")
        try:
            resp = self.uds_client.ecu_reset(
                reset_type=0x01, user_confirmed=config.user_confirmed
            )
            if resp.is_positive:
                self._log("Kurtarma: ECU Hard Reset kabul edildi.", "info")
            else:
                self._log(f"Kurtarma: ECU Hard Reset reddedildi: {resp.nrc_description_tr}", "warning")
        except Exception as recovery_exc:  # noqa: BLE001
            self._log(f"Kurtarma başarısız (ECU olduğu durumda bırakıldı): {recovery_exc}", "error")
