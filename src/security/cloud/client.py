"""Cloud client configuration & authenticated HTTP transport.

 The desktop -> cloud session is a browser-independent HttpOnly cookie the
 operator acquires by logging into the web portal; the desktop stores the
 session token via the platform SecretProvider (DPAPI on Windows) and replays
 it as a cookie on every request. Device flow uses the device_token instead.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from src.core.errors import LicenseError, SecurityError
from src.core.logging import get_logger
from src.safety.secret_provider import SecretProvider, get_default_secret_provider

logger = get_logger("security.cloud.client")

_SESSION_SECRET_NAME = "CLOUD_SESSION_TOKEN"
_DEVICE_TOKEN_SECRET_NAME = "CLOUD_DEVICE_TOKEN"
_DEVICE_ID_SECRET_NAME = "CLOUD_DEVICE_ID"
LICENSE_TICKET_SECRET_NAME = "CLOUD_LICENSE_TICKET"

# Retry policy: transient network/5xx failures are retried with linear backoff.
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


@dataclass(slots=True)
class CloudConfig:
    """Connection settings for the Universal CAN Cloud API."""

    base_url: str = "http://localhost:8000"
    api_prefix: str = "/api/v1"
    timeout_seconds: float = 30.0
    upload_timeout_seconds: float = 120.0
    max_retries: int = 3
    retry_backoff_seconds: float = 1.5
    user_agent: str = "UniversalCAN-Desktop/13.0"
    # SEC-C-001: production builds must speak HTTPS. Loopback dev servers are
    # the only permitted plain-HTTP exception (no MITM surface on localhost).
    require_https: bool = True

    def __post_init__(self) -> None:
        self._validate_scheme()

    def _validate_scheme(self) -> None:
        """Fail closed on insecure transport (SEC-C-001).

        Only https:// URLs — or loopback (localhost / 127.0.0.1 / [::1]) for
        local development — are accepted. Any other http:// endpoint would
        expose the session cookie to network interception.
        """
        if not self.require_https:
            return
        url = self.base_url.strip().lower()
        if url.startswith("https://"):
            return
        if url.startswith("http://") and self._is_loopback(url):
            return
        raise SecurityError(
            "Cloud API base_url must use HTTPS (only loopback http://localhost "
            "is allowed for development); refusing insecure session transport",
            code="CLOUD_INSECURE_TRANSPORT",
            details={"base_url": self.base_url},
        )

    @staticmethod
    def _is_loopback(url: str) -> bool:
        """True when the http:// authority targets a loopback host."""
        try:
            authority = url.split("http://", 1)[1].split("/", 1)[0]
            host = authority.rsplit("@", 1)[-1].split(":", 1)[0].strip("[]")
        except IndexError:
            return False
        return host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}

    def endpoint(self, path: str, *, health_endpoint: bool = False) -> str:
        """Build a full URL; health endpoints live outside the api prefix."""
        if not path.startswith("/"):
            path = "/" + path
        prefix = "" if health_endpoint else self.api_prefix
        return f"{self.base_url.rstrip('/')}{prefix}{path}"


@dataclass(slots=True)
class CloudResponse:
    status: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8")) if self.body else None


class CloudClient:
    """Minimal authenticated HTTP client for the cloud REST API.

    Session strategy (MASTER_PLAN §3.2):
      1. The operator logs into the web portal once and pastes the session
         token into the desktop settings; it is stored under DPAPI.
      2. Device-scoped calls (telemetry upload, activation) prefer the
         device_token issued at registration.
    """

    def __init__(
        self,
        config: CloudConfig | None = None,
        secret_provider: SecretProvider | None = None,
    ) -> None:
        self.config = config or CloudConfig()
        self._secrets = secret_provider or get_default_secret_provider()

    # ------------------------------------------------------------------
    # Credential storage (DPAPI-backed)
    # ------------------------------------------------------------------
    def store_session_token(self, token: str) -> None:
        self._secrets.store_secret(_SESSION_SECRET_NAME, token.encode("utf-8"))
        logger.info("Cloud session token stored (DPAPI)")

    def has_session_token(self) -> bool:
        return self._secrets.has_secret(_SESSION_SECRET_NAME)

    def clear_session_token(self) -> None:
        if self._secrets.has_secret(_SESSION_SECRET_NAME):
            self._secrets.delete_secret(_SESSION_SECRET_NAME)

    def store_device_token(self, token: str) -> None:
        self._secrets.store_secret(_DEVICE_TOKEN_SECRET_NAME, token.encode("utf-8"))
        logger.info("Cloud device token stored (DPAPI)")

    def get_device_token(self) -> str | None:
        if not self._secrets.has_secret(_DEVICE_TOKEN_SECRET_NAME):
            return None
        return self._secrets.get_secret(_DEVICE_TOKEN_SECRET_NAME).decode("utf-8")

    def clear_device_token(self) -> None:
        if self._secrets.has_secret(_DEVICE_TOKEN_SECRET_NAME):
            self._secrets.delete_secret(_DEVICE_TOKEN_SECRET_NAME)

    def store_device_id(self, device_id: str) -> None:
        self._secrets.store_secret(_DEVICE_ID_SECRET_NAME, device_id.encode("utf-8"))
        logger.info("Cloud device ID stored (DPAPI)")

    def get_device_id(self) -> str | None:
        if not self._secrets.has_secret(_DEVICE_ID_SECRET_NAME):
            return None
        return self._secrets.get_secret(_DEVICE_ID_SECRET_NAME).decode("utf-8")

    def clear_device_id(self) -> None:
        if self._secrets.has_secret(_DEVICE_ID_SECRET_NAME):
            self._secrets.delete_secret(_DEVICE_ID_SECRET_NAME)

    def store_license_ticket(self, ticket_token: str) -> None:
        """Persist the signed license ticket for offline re-verification (grace)."""
        self._secrets.store_secret(LICENSE_TICKET_SECRET_NAME, ticket_token.encode("utf-8"))
        logger.info("Cloud license ticket stored (DPAPI)")

    # ------------------------------------------------------------------
    # HTTP core (urllib to stay dependency-free; PyInstaller friendly)
    # ------------------------------------------------------------------
    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        raw_body: bytes | None = None,
        content_type: str | None = None,
        extra_headers: dict[str, str] | None = None,
        health_endpoint: bool = False,
    ) -> CloudResponse:
        url = self.config.endpoint(path, health_endpoint=health_endpoint)
        data = raw_body
        headers = {
            "User-Agent": self.config.user_agent,
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        }
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif content_type:
            headers["Content-Type"] = content_type

        session = None
        if self._secrets.has_secret(_SESSION_SECRET_NAME):
            session = self._secrets.get_secret(_SESSION_SECRET_NAME).decode("utf-8")
        if session:
            headers["Cookie"] = f"ucan_session={session}"
        if extra_headers:
            headers.update(extra_headers)

        last_exc: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                req = urllib.request.Request(url, data=data, headers=headers, method=method)
                with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                    return CloudResponse(
                        status=resp.status,
                        body=resp.read(),
                        headers={k: v for k, v in resp.headers.items()},
                    )
            except urllib.error.HTTPError as exc:
                body = exc.read() if exc.fp else b""
                if exc.code in _RETRY_STATUSES and attempt < self.config.max_retries:
                    self._sleep_backoff(attempt, exc.headers)
                    continue
                return CloudResponse(status=exc.code, body=body, headers=dict(exc.headers or {}))
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_exc = exc
                if attempt < self.config.max_retries:
                    self._sleep_backoff(attempt, None)
                    continue
                break

        raise SecurityError(
            f"Cloud API unreachable after {self.config.max_retries + 1} attempts: {last_exc}",
            code="CLOUD_UNREACHABLE",
            cause=last_exc,
        )

    def _sleep_backoff(self, attempt: int, response_headers: Any) -> None:
        """Honour Retry-After when the server sent one; otherwise linear backoff."""
        import time as _time

        delay = self.config.retry_backoff_seconds * (attempt + 1)
        if response_headers is not None:
            retry_after = response_headers.get("Retry-After")
            if retry_after is not None:
                try:
                    delay = max(delay, float(retry_after))
                except (TypeError, ValueError):
                    pass  # non-numeric Retry-After (HTTP-date) — fall back to backoff
        _time.sleep(delay)
        logger.debug("Retrying cloud request", extra={"attempt": attempt + 1, "delay_s": delay})


def ensure_cloud_available(client: CloudClient) -> None:
    """Fail fast with a friendly error when the cloud is unreachable."""
    resp = client.request("GET", "/health", health_endpoint=True)
    if resp.status != 200:
        raise LicenseError("Cloud health check failed", code="CLOUD_HEALTH_CHECK_FAILED")
