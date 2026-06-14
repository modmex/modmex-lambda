from __future__ import annotations

import io
import json

from modmex_lambda.logging import Logger


class Context:
    aws_request_id = "req-123"


def test_logger_outputs_json_with_required_fields() -> None:
    stream = io.StringIO()
    logger = Logger(service="orders", stream=stream)

    logger.info("Order created", order_id="o-1")

    payload = json.loads(stream.getvalue().strip())
    assert payload["level"] == "INFO"
    assert payload["service"] == "orders"
    assert payload["message"] == "Order created"
    assert payload["order_id"] == "o-1"
    assert "timestamp" in payload


def test_logger_includes_request_id_and_correlation_id_from_context_and_event() -> None:
    stream = io.StringIO()
    logger = Logger(service="orders", stream=stream)
    logger.set_context(context=Context(), event={"headers": {"X-Correlation-Id": "corr-1"}})

    logger.info("hello")

    payload = json.loads(stream.getvalue().strip())
    assert payload["request_id"] == "req-123"
    assert payload["correlation_id"] == "corr-1"


def test_logger_append_keys_and_clear_state() -> None:
    stream = io.StringIO()
    logger = Logger(service="orders", stream=stream)

    logger.append_keys(tenant="mx")
    logger.info("before-clear")
    logger.clear_state()
    logger.info("after-clear")

    lines = [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]
    assert lines[0]["tenant"] == "mx"
    assert "tenant" not in lines[1]


def test_logger_defaults_service_and_level_from_environment(monkeypatch) -> None:
    stream = io.StringIO()
    monkeypatch.setenv("SERVICE_NAME", "payments")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    logger = Logger(stream=stream)

    logger.debug("hello %s", "world")

    payload = json.loads(stream.getvalue().strip())
    assert payload["service"] == "payments"
    assert payload["level"] == "DEBUG"
    assert payload["message"] == "hello world"


def test_logger_filters_messages_below_configured_level(monkeypatch) -> None:
    stream = io.StringIO()
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    logger = Logger(stream=stream)

    logger.debug("hidden")
    logger.info("visible")

    lines = [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]
    assert [line["message"] for line in lines] == ["visible"]


def test_logger_levels_exception_and_non_string_message() -> None:
    stream = io.StringIO()
    logger = Logger(service="orders", stream=stream, level=10)

    logger.set_level("DEBUG")
    logger.warning({"event": "warn"})
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        logger.error("failed", exc_info=True)
        logger.critical("failed %s", "hard", exc_info=True)

    lines = [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]
    assert lines[0]["level"] == "WARNING"
    assert lines[0]["message"] == {"event": "warn"}
    assert lines[1]["level"] == "ERROR"
    assert "RuntimeError: boom" in lines[1]["exception"]
    assert lines[2]["level"] == "CRITICAL"
    assert lines[2]["message"] == "failed hard"
    assert "RuntimeError: boom" in lines[2]["exception"]


def test_logger_ignores_missing_context_and_malformed_headers() -> None:
    stream = io.StringIO()
    logger = Logger(service="orders", stream=stream)

    logger.set_context(context=object(), event={"headers": "not-a-dict"})
    logger.info("hello")

    payload = json.loads(stream.getvalue().strip())
    assert "request_id" not in payload
    assert "correlation_id" not in payload
