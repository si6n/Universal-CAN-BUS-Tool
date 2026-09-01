"""Unit tests for AI Diagnostic Copilot reasoning engine and JSON parser."""

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from src.engine.ai.diagnostic_copilot import (
    AiDiagnosticCopilot,
    FaultSeverity,
)


def test_ai_copilot_critical_oil_pressure_analysis() -> None:
    copilot = AiDiagnosticCopilot()
    active_dtcs = [
        {"spn": 100, "fmi": 1, "description": "Engine Oil Pressure Low"},
    ]
    telemetry = {
        "EngineSpeed": 1800.0,
        "BoostPressure": 140.0,
        "CoolantTemp": 88.0,
    }
    ecus = ["Engine_ECU_0x00"]

    report = copilot.analyze_session(active_dtcs, telemetry, ecus)
    assert report.severity == FaultSeverity.CRITICAL_STOP
    assert "Motor Yağlama" in report.affected_subsystems[0]
    assert len(report.troubleshooting_steps) >= 2
    assert "Kritik düşük yağ basıncı" in report.likely_causes[0]


def test_ai_copilot_nominal_healthy_state() -> None:
    copilot = AiDiagnosticCopilot()
    report = copilot.analyze_session([], {"EngineSpeed": 1200.0, "BoostPressure": 120.0}, ["Engine_ECU_0x00"])
    assert report.severity == FaultSeverity.LOW
    assert "nominal" in report.summary.lower()
    assert len(report.troubleshooting_steps) == 1


def test_ai_copilot_overheating_scenario() -> None:
    copilot = AiDiagnosticCopilot()
    active_dtcs = [{"spn": 110, "fmi": 0, "description": "Engine Coolant Temperature High"}]
    report = copilot.analyze_session(active_dtcs, {"EngineSpeed": 2000.0, "CoolantTemp": 112.0}, ["ECU_0"])
    assert report.severity == FaultSeverity.CRITICAL_STOP
    assert any("Soğutma" in s for s in report.affected_subsystems)


def test_ai_copilot_injector_fault_scenario() -> None:
    copilot = AiDiagnosticCopilot()
    active_dtcs = [{"spn": 653, "fmi": 5, "description": "Cylinder 3 Injector Open Circuit"}]
    report = copilot.analyze_session(active_dtcs, {"EngineSpeed": 1500.0}, ["ECU_0"])
    assert report.severity == FaultSeverity.MEDIUM
    assert any("Silindir #3" in s for s in report.affected_subsystems)


def test_ai_copilot_turbo_boost_fault_scenario() -> None:
    copilot = AiDiagnosticCopilot()
    active_dtcs = [{"spn": 102, "fmi": 18, "description": "Boost Pressure Low"}]
    report = copilot.analyze_session(active_dtcs, {"EngineSpeed": 2200.0, "BoostPressure": 90.0}, ["ECU_0"])
    assert report.severity == FaultSeverity.MEDIUM
    assert any("Turbo" in s for s in report.affected_subsystems)


def test_ai_copilot_dpf_fault_scenario() -> None:
    copilot = AiDiagnosticCopilot()
    active_dtcs = [{"spn": 3251, "fmi": 0, "description": "DPF Differential Pressure High"}]
    report = copilot.analyze_session(active_dtcs, {"EngineSpeed": 1800.0}, ["ECU_0"])
    assert report.severity == FaultSeverity.MEDIUM
    assert any("DPF" in s for s in report.affected_subsystems)


def test_clean_and_parse_json_raw_object() -> None:
    raw = '{"summary": "Test Diagnosis", "severity": "HIGH", "likely_causes": ["Cause 1"]}'
    parsed = AiDiagnosticCopilot._clean_and_parse_json(raw)
    assert parsed["summary"] == "Test Diagnosis"
    assert parsed["severity"] == "HIGH"
    assert parsed["likely_causes"] == ["Cause 1"]


def test_clean_and_parse_json_markdown_fenced() -> None:
    raw = """```json
    {
        "summary": "Turbo boost pressure leak detected",
        "severity": "MEDIUM",
        "root_cause_probability": "%85",
        "likely_causes": ["Intercooler hose split"],
        "troubleshooting_steps": [
            {"step_number": 1, "action": "Check intercooler clamp", "target_component": "Hose", "difficulty": "Kolay"}
        ],
        "affected_subsystems": ["Turbocharger"],
        "telemetry_correlations": ["Low boost at high RPM"]
    }
    ```"""
    parsed = AiDiagnosticCopilot._clean_and_parse_json(raw)
    assert parsed["summary"] == "Turbo boost pressure leak detected"
    assert parsed["severity"] == "MEDIUM"
    assert len(parsed["troubleshooting_steps"]) == 1


def test_clean_and_parse_json_markdown_fenced_without_language_tag() -> None:
    raw = """```
    {
        "summary": "Fuel rail pressure sensor intermittent",
        "severity": "LOW"
    }
    ```"""
    parsed = AiDiagnosticCopilot._clean_and_parse_json(raw)
    assert parsed["summary"] == "Fuel rail pressure sensor intermittent"
    assert parsed["severity"] == "LOW"


def test_clean_and_parse_json_with_conversational_text() -> None:
    raw = """Sure! Here is the detailed vehicle analysis you requested:

    ```json
    {
        "summary": "All systems nominal",
        "severity": "INFO"
    }
    ```

    Please let me know if you need further help!"""
    parsed = AiDiagnosticCopilot._clean_and_parse_json(raw)
    assert parsed["summary"] == "All systems nominal"
    assert parsed["severity"] == "INFO"


def test_clean_and_parse_json_outermost_brackets_fallback() -> None:
    raw = 'Here is the JSON: {"summary": "Direct brackets without markdown", "severity": "LOW"} End of report.'
    parsed = AiDiagnosticCopilot._clean_and_parse_json(raw)
    assert parsed["summary"] == "Direct brackets without markdown"
    assert parsed["severity"] == "LOW"


def test_clean_and_parse_json_invalid_raises_decode_error() -> None:
    with pytest.raises(json.JSONDecodeError):
        AiDiagnosticCopilot._clean_and_parse_json("This is definitely not JSON and has no braces at all.")


def test_gemini_fallback_on_corrupted_response() -> None:
    copilot = AiDiagnosticCopilot(gemini_api_key="valid-mock-api-key-longer-than-10-chars")

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(
        {"candidates": [{"content": {"parts": [{"text": "Corrupted response {not valid json"}]}}]}
    ).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        report = copilot.analyze_session(
            [{"spn": 100, "fmi": 1}],
            {"EngineSpeed": 1500.0},
            ["ECU_0"],
        )
        # Should gracefully fall back to local expert engine
        assert report.ai_model_used == "Yerel Otomotiv Uzman Motoru (Çevrimdışı)"
        assert report.severity == FaultSeverity.CRITICAL_STOP


def test_gemini_successful_markdown_analysis() -> None:
    copilot = AiDiagnosticCopilot(gemini_api_key="valid-mock-api-key-longer-than-10-chars")

    llm_payload = """```json
    {
        "summary": "Gemini Cloud Diagnosis: Low Fuel Pressure",
        "severity": "MEDIUM",
        "root_cause_probability": "%94",
        "likely_causes": ["Clogged fuel filter"],
        "troubleshooting_steps": [
            {"step_number": 1, "action": "Replace secondary fuel filter", "target_component": "Fuel Filter", "difficulty": "Orta"}
        ],
        "affected_subsystems": ["Fuel Rail"],
        "telemetry_correlations": ["Fuel pressure dip"]
    }
    ```"""

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"candidates": [{"content": {"parts": [{"text": llm_payload}]}}]}).encode(
        "utf-8"
    )
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        report = copilot.analyze_session([], {}, ["ECU_0"])
        assert "Google Gemini" in report.ai_model_used and "Flash" in report.ai_model_used
        assert report.summary == "Gemini Cloud Diagnosis: Low Fuel Pressure"
        assert report.severity == FaultSeverity.MEDIUM
        assert len(report.troubleshooting_steps) == 1
        assert report.troubleshooting_steps[0].action == "Replace secondary fuel filter"


def test_gemini_fallback_on_http_errors() -> None:
    """Verify that HTTP network errors (503, 500, timeout) fall back gracefully to local offline engine."""
    copilot = AiDiagnosticCopilot(gemini_api_key="valid-mock-api-key-longer-than-10-chars")

    http_error = urllib.error.HTTPError(
        url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        code=503,
        msg="Service Unavailable",
        hdrs=None,  # type: ignore[arg-type]
        fp=None,
    )

    with patch("urllib.request.urlopen", side_effect=http_error):
        report = copilot.analyze_session(
            [{"spn": 100, "fmi": 1}],
            {"EngineSpeed": 1500.0},
            ["ECU_0"],
        )
        assert report.ai_model_used == "Yerel Otomotiv Uzman Motoru (Çevrimdışı)"
        assert report.severity == FaultSeverity.CRITICAL_STOP


# ============================================================================
# F-03: API key transport DoD tests — key in x-goog-api-key header,
# never in the URL (CWE-598)
# ============================================================================


def test_gemini_request_carries_key_in_header_not_url() -> None:
    """F-03 DoD: the Gemini call must pass the key via x-goog-api-key header."""
    captured: dict = {}

    def fake_urlopen(req, timeout=None):  # noqa: ANN001
        captured["url"] = req.full_url
        captured["headers"] = {k.lower(): v for k, v in req.header_items()}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}
        ).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        return mock_resp

    copilot = AiDiagnosticCopilot(gemini_api_key="AIza-mock-key-0123456789abcdef")
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        copilot.analyze_live_telemetry(
            rpm=1800.0, boost_bar=1.6, coolant_temp=85.0, dtc_codes=["P0300"], user_prompt="Sorun ne?"
        )

    assert "?key=" not in captured["url"], "API key leaked into URL"
    assert "apikey=" not in captured["url"].lower()
    assert captured["headers"].get("x-goog-api-key") == "AIza-mock-key-0123456789abcdef"


def test_gemini_endpoint_constant_matches_readme_model() -> None:
    """F-42/E-9 DoD: single endpoint constant pinned to gemini-2.0-flash."""
    from src.engine.ai.diagnostic_copilot import GEMINI_ENDPOINT

    assert GEMINI_ENDPOINT.endswith("gemini-2.0-flash:generateContent")
    assert "?key=" not in GEMINI_ENDPOINT
