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
