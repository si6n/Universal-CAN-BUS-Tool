"""Universal CAN Cloud client integration tests (Tasks 5.3/5.4 — desktop side).

 Uses a local mock cloud server (in-process, real HTTP on 127.0.0.1) that
 mirrors the Universal-CAN-Cloud API contract, so the full flow — device
 registration -> license activation -> resumable telemetry upload — is
 exercised end-to-end without the production backend.
"""

from __future__ import annotations

import base64
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.safety.secret_provider import EphemeralSecretBackend
from src.security.cloud.client import CloudClient, CloudConfig
from src.security.cloud.license_flow import LicenseFlow
from src.security.cloud.telemetry_uploader import TelemetryUploader, UploadProgress

# ---------------------------------------------------------------------------
# Mock cloud (mirrors backend/app routers contract)
# ---------------------------------------------------------------------------

class MockCloudState:
    def __init__(self) -> None:
        self.private_key = Ed25519PrivateKey.generate()
        self.device_token = "devtok_" + "x" * 32
        self.device_id = "11111111-1111-1111-1111-111111111111"
        self.session_counter = 0
        self.sessions: dict[str, dict] = {}
        self.chunks: dict[tuple[str, int], bytes] = {}
        self.activated = False
        self.registered_hwids: list[str] = []


STATE = MockCloudState()


def _sign_ticket(payload: dict) -> str:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    sig = STATE.private_key.sign(body)
    return (
        base64.urlsafe_b64encode(body).decode().rstrip("=")
        + "."
        + base64.urlsafe_b64encode(sig).decode().rstrip("=")
    )


class MockCloudHandler(BaseHTTPRequestHandler):
    """Implements the exact cloud contract used by the desktop client."""

    def log_message(self, *args) -> None:  # silence
        pass

    def _json(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._json(200, {"status": "ok"})
            return
        # GET /api/v1/telematics/sessions/{sid} — resume state query
        parts = self.path.split("/")
        if len(parts) == 6 and parts[4] == "sessions":
            session = STATE.sessions.get(parts[5])
            if session is None:
                self._json(404, {"detail": "session not found"})
            else:
                self._json(200, session)
            return
        self._json(404, {"detail": "not found"})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")

        if self.path == "/api/v1/devices/register":
            STATE.registered_hwids.append(body["hwid"])
            self._json(
                201,
                {
                    "device_id": STATE.device_id,
                    "device_token": STATE.device_token,
                    "hwid_resets_remaining": 1,
                },
            )
            return

        if self.path == "/api/v1/licenses/activate":
            if body.get("device_token") != STATE.device_token:
                self._json(403, {"detail": "bad device token"})
                return
            STATE.activated = True
            import time

            now = int(time.time())
            ticket = _sign_ticket(
                {
                    "iss": "universal-can-cloud",
                    "aud": "diagnostic-desktop-app",
                    "kid": "key-2026-v1",
                    "license_id": "lic_test123",
                    "organization_id": "org_test",
                    "device_id": STATE.device_id,
                    "tier": "marine_pro",
                    "features": ["j1939", "nmea2000"],
                    "iat": now,
                    "exp": now + 3600,
                    "offline_until": now + 7 * 86400,
                    "schema_version": 1,
                    "nonce": body["nonce"],
                }
            )
            self._json(
                200,
                {"license_token": ticket, "expires_at": str(now + 3600), "offline_until": str(now + 7 * 86400)},
            )
            return

        if self.path == "/api/v1/telematics/sessions":
            STATE.session_counter += 1
            sid = f"ses_{STATE.session_counter:04d}"
            total = (body["declared_size_bytes"] + body["chunk_size_bytes"] - 1) // body["chunk_size_bytes"]
            STATE.sessions[sid] = {
                "id": sid,
                "total_chunks": total,
                "received_chunks": 0,
                "uploaded_size_bytes": 0,
                "declared_size_bytes": body["declared_size_bytes"],
                "declared_sha256": body["declared_sha256"],
                "chunk_size_bytes": body["chunk_size_bytes"],
                "status": "uploading",
                "vehicle_vin": body.get("vehicle_vin"),
                "archive_s3_key": None,
            }
            self._json(201, STATE.sessions[sid])
            return

        if self.path.startswith("/api/v1/telematics/sessions/") and self.path.endswith("/complete"):
            sid = self.path.split("/")[5]
            session = STATE.sessions[sid]
            session["status"] = "processing"
            self._json(200, {"session_id": sid, "status": "processing", "job_id": "job-1"})
            return

        self._json(404, {"detail": "not found"})

    def do_PUT(self) -> None:
        # /api/v1/telematics/sessions/{sid}/chunks/{idx}
        parts = self.path.split("/")
        if len(parts) == 8 and parts[6] == "chunks":
            sid, idx = parts[5], int(parts[7])
            length = int(self.headers.get("Content-Length", "0"))
            chunk = self.rfile.read(length)
            session = STATE.sessions[sid]
            if not (0 <= idx < session["total_chunks"]):
                self._json(400, {"detail": "out of range"})
                return
            STATE.chunks[(sid, idx)] = chunk
            session["received_chunks"] += 1
            session["uploaded_size_bytes"] += len(chunk)
            self._json(
                200,
                {
                    "session_id": sid,
                    "chunk_index": idx,
                    "received": True,
                    "received_chunks": session["received_chunks"],
                    "uploaded_size_bytes": session["uploaded_size_bytes"],
                },
            )
            return
        self._json(404, {"detail": "not found"})


@pytest.fixture(scope="module")
def mock_cloud():
    server = HTTPServer(("127.0.0.1", 0), MockCloudHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture
def client(mock_cloud):
    STATE.__init__()  # reset between tests
    return CloudClient(
        config=CloudConfig(base_url=mock_cloud),
        secret_provider=EphemeralSecretBackend(),
    )


@pytest.fixture
def flow(client) -> LicenseFlow:
    return LicenseFlow(client, public_key=STATE.private_key.public_key())


# ---------------------------------------------------------------------------
# Device registration & license activation (Task 5.3)
# ---------------------------------------------------------------------------

def test_device_registration_stores_token_under_dpapi(client) -> None:
    reg = flow_register(client)
    assert reg.device_id == STATE.device_id
    assert reg.device_token == STATE.device_token
    # Token persisted via SecretProvider (Ephemeral in tests, DPAPI in prod).
    assert client.get_device_token() == STATE.device_token


def flow_register(client) -> object:
    flow = LicenseFlow(client, public_key=STATE.private_key.public_key())
    return flow.register_device("Atolye-PC-01", hwid="a" * 64)


def test_activation_rejects_without_device_token(client) -> None:
    from src.core.errors import LicenseError

    flow = LicenseFlow(client, public_key=STATE.private_key.public_key())
    with pytest.raises(LicenseError, match="No device token"):
        flow.activate_license("lic_test123")


def test_license_activation_full_flow(flow) -> None:
    flow.register_device("Atolye-PC-01", hwid="b" * 64)
    claims = flow.activate_license("lic_test123")

    assert claims.license_id == "lic_test123"
    assert claims.tier == "marine_pro"
    assert claims.features == ("j1939", "nmea2000")
    assert claims.device_id == STATE.device_id
    assert claims.key_id == "key-2026-v1"
    assert STATE.activated


def test_ticket_verification_rejects_forged_signature(flow) -> None:
    from src.core.errors import LicenseError

    evil_key = Ed25519PrivateKey.generate()
    body = json.dumps({"iss": "universal-can-cloud", "aud": "diagnostic-desktop-app"}).encode()
    sig = evil_key.sign(body)
    forged = base64.urlsafe_b64encode(body).decode() + "." + base64.urlsafe_b64encode(sig).decode()

    with pytest.raises(LicenseError, match="signature"):
        flow.verify_cloud_ticket(forged)


def test_ticket_verification_rejects_wrong_issuer(flow) -> None:
    import time

    from src.core.errors import LicenseError

    now = int(time.time())
    # Full canonical schema but a hostile issuer — must be rejected on iss/aud.
    body = json.dumps(
        {
            "iss": "evil-cloud",
            "aud": "diagnostic-desktop-app",
            "kid": "key-2026-v1",
            "license_id": "lic_fake",
            "organization_id": "org_x",
            "device_id": "dev_x",
            "tier": "marine_pro",
            "features": ["j1939"],
            "iat": now,
            "exp": now + 3600,
            "offline_until": now + 86400,
            "schema_version": 1,
            "nonce": "n" * 12,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    sig = STATE.private_key.sign(body)
    token = base64.urlsafe_b64encode(body).decode() + "." + base64.urlsafe_b64encode(sig).decode()

    with pytest.raises(LicenseError, match="issuer"):
        flow.verify_cloud_ticket(token)


# ---------------------------------------------------------------------------
# Resumable telemetry upload (Task 5.4)
# ---------------------------------------------------------------------------

def test_telemetry_upload_end_to_end(client, tmp_path: Path) -> None:
    # Force small chunks for the test (backend minimum is 1 MB — mock accepts any).
    payload = bytes(range(256)) * 4096  # 1 MB
    session_file = tmp_path / "session.mdf4"
    session_file.write_bytes(payload)

    received: list[UploadProgress] = []

    uploader = TelemetryUploader(
        client,
        chunk_size=256 * 1024,  # 4 chunks
        progress_callback=received.append,
    )
    result = uploader.upload_file(session_file, vehicle_vin="TR-TEST-001")

    assert result.status == "processing"
    assert result.session_id.startswith("ses_")

    # All chunks reached the server with byte-exact content.
    sid = result.session_id
    reassembled = b"".join(STATE.chunks[(sid, i)] for i in range(4))
    assert hashlib.sha256(reassembled).hexdigest() == hashlib.sha256(payload).hexdigest()

    # Progress reporting fired with the final state.
    assert received[-1].uploaded_chunks == 4
    assert received[-1].percent == 100.0


def test_upload_rejects_missing_file(client) -> None:
    from src.core.errors import LicenseError

    uploader = TelemetryUploader(client)
    with pytest.raises(LicenseError, match="not found"):
        uploader.upload_file("Z:/yok/böyle.mf4")


def test_resume_queries_session_state(client, tmp_path: Path) -> None:
    payload = b"x" * (512 * 1024)
    session_file = tmp_path / "partial.mdf4"
    session_file.write_bytes(payload)

    uploader = TelemetryUploader(client, chunk_size=256 * 1024)
    result = uploader.upload_file(session_file)

    progress = uploader.resume(result.session_id)
    assert progress.total_chunks == 2
    assert progress.uploaded_chunks == 2
    assert progress.status in ("uploading", "processing")
