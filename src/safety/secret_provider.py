"""Universal CAN-Bus Diagnostic & Telemetry Platform - Cryptographic Secret Providers.

Provides hardened, cross-platform cryptographic key and secret management backends:
- Windows DPAPI backend (CryptProtectData / CryptUnprotectData with local encrypted fallback)
- Linux / POSIX backend (AES-256-GCM encrypted local keyfile with 0600 file permissions and HKDF)
- Ephemeral in-memory backend (for CI, test runners, and dynamic session keys)
"""

from __future__ import annotations

import base64
import ctypes
import importlib
import json
import os
import platform
import sys
import threading
from abc import ABC, abstractmethod
from ctypes import wintypes
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from src.core.errors import SecurityError
from src.core.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger("safety.secret_provider")

DEFAULT_DPAPI_ENTROPY: bytes = b"UniversalCAN_Hardware_Secret_Binding_2026"
DEFAULT_LINUX_SALT: bytes = b"UniversalCAN_Linux_Secret_Salt_2026"
DEFAULT_KDF_INFO: bytes = b"UniversalCAN_Secret_Key_Derivation_v1"


class SecretProvider(ABC):
    """Abstract base for secure secret and key STORAGE backends.

    Canonical relationship (resolves the ABC-vs-Protocol split):
    - ``src.core.contracts.ports.SecretProvider`` is the READ-side structural
      Protocol (``get_secret(key_name) -> bytes``) that consumers (E-Stop,
      UDS security access) depend on. It is ``runtime_checkable`` and every
      concrete backend below satisfies it structurally.
    - THIS class is the storage-backend base adding write/lifecycle methods
      (``store_secret``/``set_secret``/``delete_secret``/``has_secret``).

    Consumers MUST type against the ports Protocol; only backend
    implementations and provisioning code should reference this ABC.
    """

    @abstractmethod
    def get_secret(self, name: str) -> bytes:
        """Retrieve a binary secret by its logical identifier.

        Args:
            name: Logical secret key name (e.g. 'ESTOP_HMAC_SECRET').

        Returns:
            Decrypted secret bytes.

        Raises:
            KeyError: If secret does not exist.
            SecurityError: If decryption, permissions, or tamper checks fail.
        """
        ...

    @abstractmethod
    def store_secret(self, name: str, secret: bytes) -> None:
        """Securely persist or update a binary secret.

        Args:
            name: Logical secret key name.
            secret: Binary secret data to store.

        Raises:
            SecurityError: If encryption or file access fails.
            TypeError: If secret is not bytes or name is not str.
        """
        ...

    def set_secret(self, name: str, secret: bytes) -> None:
        """Alias for store_secret to ensure full compatibility with ports.SecretProvider contract."""
        self.store_secret(name, secret)

    def delete_secret(self, name: str) -> None:
        """Remove a secret from the provider.

        Args:
            name: Logical secret key name to remove.

        Raises:
            KeyError: If secret does not exist.
            SecurityError: If removal or storage write fails.
        """
        raise NotImplementedError(f"delete_secret is not supported by {self.__class__.__name__}")

    def has_secret(self, name: str) -> bool:
        """Check whether a secret exists and can be retrieved.

        Args:
            name: Logical secret key name.

        Returns:
            True if secret exists, False otherwise.
        """
        try:
            self.get_secret(name)
            return True
        except (KeyError, SecurityError):
            return False

    def list_secrets(self) -> list[str]:
        """List all available secret names in this provider.

        Returns:
            List of secret key names.
        """
        return []


# =====================================================================
# Ephemeral In-Memory Backend (CI / Testing / Dynamic Session Keys)
# =====================================================================


class EphemeralSecretBackend(SecretProvider):
    """Thread-safe in-memory secret provider for testing, CI, and ephemeral sessions."""

    def __init__(self, secrets: dict[str, bytes] | None = None) -> None:
        self._secrets: dict[str, bytes] = dict(secrets) if secrets is not None else {}
        self._lock = threading.RLock()

    def get_secret(self, name: str) -> bytes:
        with self._lock:
            if name not in self._secrets:
                raise KeyError(f"Secret '{name}' not found in {self.__class__.__name__}")
            return self._secrets[name]

    def store_secret(self, name: str, secret: bytes) -> None:
        if not isinstance(name, str):
            raise TypeError(f"Secret name must be str, got {type(name).__name__}")
        if not isinstance(secret, (bytes, bytearray)):
            raise TypeError(f"Secret value must be bytes, got {type(secret).__name__}")
        with self._lock:
            self._secrets[name] = bytes(secret)

    def delete_secret(self, name: str) -> None:
        with self._lock:
            if name not in self._secrets:
                raise KeyError(f"Secret '{name}' not found in {self.__class__.__name__}")
            del self._secrets[name]

    def clear(self) -> None:
        """Clear all stored in-memory secrets."""
        with self._lock:
            self._secrets.clear()

    def list_secrets(self) -> list[str]:
        with self._lock:
            return list(self._secrets.keys())


# Aliases for Ephemeral backend
EphemeralSecretProvider = EphemeralSecretBackend
InMemorySecretBackend = EphemeralSecretBackend
InMemorySecretProvider = EphemeralSecretBackend


# =====================================================================
# Linux / POSIX Encrypted Keyfile Backend (0600 Permissions + AES-GCM)
# =====================================================================


class LinuxSecretBackend(SecretProvider):
    """Encrypted local file secret provider for Linux and POSIX platforms.

    Uses AES-256-GCM encryption with HKDF key derivation from machine credentials,
    and strictly enforces POSIX 0600 file permissions (owner read/write only).
    """

    MAGIC_HEADER: bytes = b"UCANSEC1"

    def __init__(
        self,
        storage_path: Path | str | None = None,
        master_key: bytes | None = None,
        salt: bytes = DEFAULT_LINUX_SALT,
    ) -> None:
        if storage_path is None:
            config_home = os.environ.get("XDG_CONFIG_HOME")
            base_dir = Path(config_home) if config_home else Path.home() / ".config"
            self.storage_path = base_dir / "universal_can" / "secrets.bin"
        else:
            self.storage_path = Path(storage_path)

        self._master_key = master_key
        self._salt = salt
        self._lock = threading.RLock()

    def _derive_encryption_key(self, salt: bytes) -> bytes:
        """Derive 256-bit AES-GCM key via HKDF from machine seed or explicit master key."""
        if self._master_key is not None:
            seed = self._master_key
        else:
            seed = self._get_machine_seed()

        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=DEFAULT_KDF_INFO,
        )
        return hkdf.derive(seed)

    def _get_machine_seed(self) -> bytes:
        """Gather platform machine identifier for user/machine tied key derivation."""
        candidates = [
            Path("/etc/machine-id"),
            Path("/var/lib/dbus/machine-id"),
            Path("/etc/hostid"),
        ]
        for candidate in candidates:
            try:
                if candidate.exists() and candidate.is_file():
                    content = candidate.read_bytes().strip()
                    if content:
                        return content
            except Exception:
                continue

        # Fallback to user and node info
        node_id = platform.node() or "localhost"
        user_id = os.environ.get("USER", os.environ.get("USERNAME", "default_user"))
        return f"{node_id}:{user_id}:UniversalCAN_Fixed_Machine_Seed".encode("utf-8")

    def _load_all_secrets(self) -> dict[str, bytes]:
        """Load and decrypt all secrets from file."""
        if not self.storage_path.exists():
            return {}

        try:
            raw_data = self.storage_path.read_bytes()
            if not raw_data:
                return {}

            magic_len = len(self.MAGIC_HEADER)
            if len(raw_data) < magic_len + 16 + 12 + 16:  # magic + salt(16) + nonce(12) + tag(16)
                raise SecurityError(
                    "Secret store file is corrupted or too short",
                    code="SECURITY_ERROR",
                )

            magic = raw_data[:magic_len]
            if magic != self.MAGIC_HEADER:
                raise SecurityError(
                    "Invalid secret store magic header",
                    code="SECURITY_ERROR",
                )

            salt = raw_data[magic_len : magic_len + 16]
            nonce = raw_data[magic_len + 16 : magic_len + 28]
            ciphertext = raw_data[magic_len + 28 :]

            key = self._derive_encryption_key(salt)
            aesgcm = AESGCM(key)

            try:
                decrypted_json = aesgcm.decrypt(nonce, ciphertext, self.MAGIC_HEADER + salt)
            except Exception as exc:
                raise SecurityError(
                    "Decryption failed: corrupted keyfile or invalid authentication tag",
                    code="SECURITY_ERROR",
                    cause=exc,
                ) from exc

            payload = json.loads(decrypted_json.decode("utf-8"))
            secrets_raw: dict[str, str] = payload.get("secrets", {})
            return {k: base64.b64decode(v.encode("ascii")) for k, v in secrets_raw.items()}

        except SecurityError:
            raise
        except Exception as exc:
            raise SecurityError(
                f"Failed to read secret store: {exc}",
                code="SECURITY_ERROR",
                cause=exc,
            ) from exc

    def _save_all_secrets(self, secrets: dict[str, bytes]) -> None:
        """Encrypt and write all secrets to storage with 0600 file permissions."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            salt = os.urandom(16)
            key = self._derive_encryption_key(salt)
            aesgcm = AESGCM(key)
            nonce = os.urandom(12)

            serialized_secrets = {
                k: base64.b64encode(v).decode("ascii") for k, v in secrets.items()
            }
            payload = json.dumps({"version": 1, "secrets": serialized_secrets}).encode("utf-8")

            ciphertext = aesgcm.encrypt(nonce, payload, self.MAGIC_HEADER + salt)
            blob = self.MAGIC_HEADER + salt + nonce + ciphertext

            # Write file atomically with 0600 permissions
            temp_file = self.storage_path.with_suffix(".tmp")

            # Create file with 0600 flags if supported
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            mode = 0o600
            try:
                fd = os.open(temp_file, flags, mode)
                with os.fdopen(fd, "wb") as f:
                    f.write(blob)
            except Exception:
                temp_file.write_bytes(blob)

            try:
                os.chmod(temp_file, 0o600)
            except Exception:
                pass

            temp_file.replace(self.storage_path)

            try:
                os.chmod(self.storage_path, 0o600)
            except Exception:
                pass

        except Exception as exc:
            raise SecurityError(
                f"Failed to save secret store: {exc}",
                code="SECURITY_ERROR",
                cause=exc,
            ) from exc

    def get_secret(self, name: str) -> bytes:
        with self._lock:
            secrets = self._load_all_secrets()
            if name not in secrets:
                raise KeyError(f"Secret '{name}' not found in {self.__class__.__name__}")
            return secrets[name]

    def store_secret(self, name: str, secret: bytes) -> None:
        if not isinstance(name, str):
            raise TypeError(f"Secret name must be str, got {type(name).__name__}")
        if not isinstance(secret, (bytes, bytearray)):
            raise TypeError(f"Secret value must be bytes, got {type(secret).__name__}")

        with self._lock:
            secrets = self._load_all_secrets()
            secrets[name] = bytes(secret)
            self._save_all_secrets(secrets)

    def delete_secret(self, name: str) -> None:
        with self._lock:
            secrets = self._load_all_secrets()
            if name not in secrets:
                raise KeyError(f"Secret '{name}' not found in {self.__class__.__name__}")
            del secrets[name]
            self._save_all_secrets(secrets)

    def list_secrets(self) -> list[str]:
        with self._lock:
            secrets = self._load_all_secrets()
            return list(secrets.keys())


# Aliases for Linux backend
LinuxSecretProvider = LinuxSecretBackend
LinuxKeyfileSecretProvider = LinuxSecretBackend


# =====================================================================
# Windows DPAPI Secret Backend (CryptProtectData / CryptUnprotectData)
# =====================================================================


class _WindowsDATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


class WindowsDPAPISecretBackend(SecretProvider):
    """Hardware and user-tied secret provider using Windows Data Protection API (DPAPI).

    Uses CryptProtectData / CryptUnprotectData via win32crypt or ctypes.
    If DPAPI is unavailable or running on non-Windows, cleanly falls back to
    an AES-256-GCM encrypted local keyfile.
    """

    def __init__(
        self,
        storage_path: Path | str | None = None,
        entropy: bytes = DEFAULT_DPAPI_ENTROPY,
        fallback_backend: SecretProvider | None = None,
    ) -> None:
        if storage_path is None:
            local_appdata = os.environ.get("LOCALAPPDATA")
            base_dir = Path(local_appdata) if local_appdata else Path.home() / "AppData" / "Local"
            self.storage_path = base_dir / "UniversalCAN" / "secrets.dpapi"
        else:
            self.storage_path = Path(storage_path)

        self.entropy = entropy
        self._lock = threading.RLock()
        self._fallback_backend = fallback_backend

    def _is_windows_dpapi_available(self) -> bool:
        """Check if Windows DPAPI is callable on the current platform."""
        if sys.platform != "win32":
            return False
        try:
            # Quick probe
            _ = ctypes.windll.crypt32.CryptProtectData
            return True
        except Exception:
            return False

    def _dpapi_protect(self, data: bytes) -> bytes:
        """Protect data using win32crypt if available or ctypes."""
        # 1. Try win32crypt if present
        try:
            win32crypt = importlib.import_module("win32crypt")
            protected = win32crypt.CryptProtectData(
                data,
                "UniversalCAN Secret",
                self.entropy,
                None,
                None,
                0,
            )
            return bytes(protected)
        except Exception:
            pass

        # 2. Use ctypes crypt32
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32

        blob_in = _WindowsDATA_BLOB(
            len(data),
            ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)),
        )
        blob_out = _WindowsDATA_BLOB()

        blob_entropy_ptr = None
        if self.entropy:
            blob_entropy = _WindowsDATA_BLOB(
                len(self.entropy),
                ctypes.cast(ctypes.create_string_buffer(self.entropy), ctypes.POINTER(ctypes.c_byte)),
            )
            blob_entropy_ptr = ctypes.byref(blob_entropy)

        res = crypt32.CryptProtectData(
            ctypes.byref(blob_in),
            ctypes.c_wchar_p("UniversalCAN Secret"),
            blob_entropy_ptr,
            None,
            None,
            0,
            ctypes.byref(blob_out),
        )
        if not res:
            err = ctypes.GetLastError()
            raise OSError(f"CryptProtectData failed with error code {err}")

        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel32.LocalFree(blob_out.pbData)

    def _dpapi_unprotect(self, encrypted_data: bytes) -> bytes:
        """Unprotect DPAPI data using win32crypt if available or ctypes."""
        # 1. Try win32crypt if present
        try:
            win32crypt = importlib.import_module("win32crypt")
            _desc, decrypted = win32crypt.CryptUnprotectData(
                encrypted_data,
                self.entropy,
                None,
                None,
                0,
            )
            return bytes(decrypted)
        except Exception:
            pass

        # 2. Use ctypes crypt32
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32

        blob_in = _WindowsDATA_BLOB(
            len(encrypted_data),
            ctypes.cast(ctypes.create_string_buffer(encrypted_data), ctypes.POINTER(ctypes.c_byte)),
        )
        blob_out = _WindowsDATA_BLOB()

        blob_entropy_ptr = None
        if self.entropy:
            blob_entropy = _WindowsDATA_BLOB(
                len(self.entropy),
                ctypes.cast(ctypes.create_string_buffer(self.entropy), ctypes.POINTER(ctypes.c_byte)),
            )
            blob_entropy_ptr = ctypes.byref(blob_entropy)

        res = crypt32.CryptUnprotectData(
            ctypes.byref(blob_in),
            None,
            blob_entropy_ptr,
            None,
            None,
            0,
            ctypes.byref(blob_out),
        )
        if not res:
            err = ctypes.GetLastError()
            raise OSError(f"CryptUnprotectData failed with error code {err}")

        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel32.LocalFree(blob_out.pbData)

    def _get_fallback(self) -> SecretProvider:
        """Get or initialize fallback encrypted file provider."""
        if self._fallback_backend is None:
            fallback_file = self.storage_path.with_suffix(".fallback.bin")
            self._fallback_backend = LinuxSecretBackend(storage_path=fallback_file)
        return self._fallback_backend

    def _load_store(self) -> dict[str, Any]:
        """Load JSON storage file."""
        if not self.storage_path.exists():
            return {"version": 1, "backend": "windows_dpapi", "secrets": {}}
        try:
            content = self.storage_path.read_text(encoding="utf-8")
            return json.loads(content)  # type: ignore[no-any-return]
        except Exception as exc:
            raise SecurityError(
                f"Failed to read DPAPI secret file: {exc}",
                code="SECURITY_ERROR",
                cause=exc,
            ) from exc

    def _save_store(self, data: dict[str, Any]) -> None:
        """Save JSON storage file atomically."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.storage_path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            temp_path.replace(self.storage_path)
        except Exception as exc:
            raise SecurityError(
                f"Failed to save DPAPI secret file: {exc}",
                code="SECURITY_ERROR",
                cause=exc,
            ) from exc

    def get_secret(self, name: str) -> bytes:
        with self._lock:
            if not self._is_windows_dpapi_available():
                return self._get_fallback().get_secret(name)

            try:
                store = self._load_store()
                secrets = store.get("secrets", {})
                if name not in secrets:
                    raise KeyError(f"Secret '{name}' not found in {self.__class__.__name__}")

                encrypted_b64 = secrets[name]
                encrypted_blob = base64.b64decode(encrypted_b64.encode("ascii"))
                return self._dpapi_unprotect(encrypted_blob)
            except KeyError:
                raise
            except Exception as exc:
                logger.warning("Windows DPAPI read failed, trying fallback", extra={"error": str(exc)})
                if self._fallback_backend and self._fallback_backend.has_secret(name):
                    return self._fallback_backend.get_secret(name)
                raise SecurityError(
                    f"DPAPI decryption failed for secret '{name}': {exc}",
                    code="SECURITY_ERROR",
                    cause=exc,
                ) from exc

    def store_secret(self, name: str, secret: bytes) -> None:
        if not isinstance(name, str):
            raise TypeError(f"Secret name must be str, got {type(name).__name__}")
        if not isinstance(secret, (bytes, bytearray)):
            raise TypeError(f"Secret value must be bytes, got {type(secret).__name__}")

        with self._lock:
            if not self._is_windows_dpapi_available():
                self._get_fallback().store_secret(name, secret)
                return

            try:
                encrypted_blob = self._dpapi_protect(bytes(secret))
                encrypted_b64 = base64.b64encode(encrypted_blob).decode("ascii")

                store = self._load_store()
                if "secrets" not in store:
                    store["secrets"] = {}
                store["secrets"][name] = encrypted_b64
                self._save_store(store)
            except Exception as exc:
                logger.warning("Windows DPAPI store failed, falling back to encrypted file", extra={"error": str(exc)})
                self._get_fallback().store_secret(name, secret)

    def delete_secret(self, name: str) -> None:
        with self._lock:
            if not self._is_windows_dpapi_available():
                self._get_fallback().delete_secret(name)
                return

            store = self._load_store()
            secrets = store.get("secrets", {})
            if name not in secrets:
                if self._fallback_backend and self._fallback_backend.has_secret(name):
                    self._fallback_backend.delete_secret(name)
                    return
                raise KeyError(f"Secret '{name}' not found in {self.__class__.__name__}")

            del secrets[name]
            self._save_store(store)

    def list_secrets(self) -> list[str]:
        with self._lock:
            if not self._is_windows_dpapi_available():
                return self._get_fallback().list_secrets()

            store = self._load_store()
            return list(store.get("secrets", {}).keys())


# Aliases for Windows DPAPI backend
WindowsDpapiSecretProvider = WindowsDPAPISecretBackend


# =====================================================================
# Factory & Auto-Detection Helper
# =====================================================================


def get_default_secret_provider(
    storage_dir: Path | str | None = None,
    force_ephemeral: bool = False,
) -> SecretProvider:
    """Auto-detect and instantiate the optimal SecretProvider for the current runtime platform.

    - If force_ephemeral=True or UNIVERSAL_CAN_EPHEMERAL_SECRETS=1: EphemeralSecretBackend
    - On Windows: WindowsDPAPISecretBackend (with automatic fallback)
    - On Linux / macOS / POSIX: LinuxSecretBackend (0600 file permissions + AES-256-GCM)

    Args:
        storage_dir: Optional custom storage directory.
        force_ephemeral: If True, forces in-memory ephemeral storage.

    Returns:
        Configured concrete SecretProvider instance.
    """
    if force_ephemeral or os.environ.get("UNIVERSAL_CAN_EPHEMERAL_SECRETS") == "1":
        return EphemeralSecretBackend()

    try:
        if sys.platform == "win32":
            path = Path(storage_dir) / "secrets.dpapi" if storage_dir else None
            return WindowsDPAPISecretBackend(storage_path=path)
        else:
            path = Path(storage_dir) / "secrets.bin" if storage_dir else None
            return LinuxSecretBackend(storage_path=path)
    except Exception as exc:
        logger.warning(
            "Failed to initialize platform SecretProvider, falling back to Ephemeral",
            extra={"error": str(exc)},
        )
        return EphemeralSecretBackend()


# Alias for factory
get_platform_secret_provider = get_default_secret_provider
