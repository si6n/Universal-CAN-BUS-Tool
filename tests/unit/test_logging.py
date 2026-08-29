"""Unit tests for structured logging and JSON formatting."""

import json
import logging

from src.core.logging import JsonFormatter, get_logger, setup_logging


def test_json_formatter_standard() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Test message content",
        args=(),
        exc_info=None,
    )
    record.timestamp_ns = 123456789
    record.extra = {"user_id": "technician_1", "device": "pcan0"}

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["logger"] == "test_logger"
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "Test message content"
    assert parsed["timestamp_ns"] == 123456789
    assert parsed["user_id"] == "technician_1"
    assert parsed["device"] == "pcan0"


def test_setup_logging_and_get_logger() -> None:
    root_logger = setup_logging(level=logging.DEBUG, json_output=False)
    assert root_logger.name == "universal_can"
    assert root_logger.level == logging.DEBUG

    sub_logger = get_logger("hal.test")
    assert sub_logger.name == "universal_can.hal.test"
