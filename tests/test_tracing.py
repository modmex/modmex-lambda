from __future__ import annotations

import sys
import types

import pytest

from modmex_lambda.tracing import Tracer


class Context:
    aws_request_id = "req-1"
    function_name = "orders"


class FakeStatusCode:
    ERROR = "ERROR"


class FakeStatus:
    def __init__(self, code):
        self.code = code


class FakeSpan:
    def __init__(self, name):
        self.name = name
        self.attributes = {}
        self.events = []
        self.exceptions = []
        self.status = None

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def add_event(self, name, attributes=None):
        self.events.append((name, attributes))

    def record_exception(self, exception):
        self.exceptions.append(exception)

    def set_status(self, status):
        self.status = status


class FakeSpanContext:
    def __init__(self, span):
        self.span = span

    def __enter__(self):
        return self.span

    def __exit__(self, *_):
        return False


class FakeOtelTrace(types.ModuleType):
    Status = FakeStatus
    StatusCode = FakeStatusCode

    def __init__(self):
        super().__init__("opentelemetry.trace")
        self.spans = []
        self.current_span = FakeSpan("current")

    def get_tracer(self, *_args, **_kwargs):
        return self

    def start_as_current_span(self, name):
        span = FakeSpan(name)
        self.spans.append(span)
        return FakeSpanContext(span)

    def get_current_span(self):
        return self.current_span


@pytest.fixture
def fake_otel(monkeypatch):
    trace = FakeOtelTrace()
    package = types.ModuleType("opentelemetry")
    package.trace = trace
    monkeypatch.setitem(sys.modules, "opentelemetry", package)
    monkeypatch.setitem(sys.modules, "opentelemetry.trace", trace)
    return trace


def test_tracer_is_noop_without_opentelemetry(monkeypatch):
    monkeypatch.delitem(sys.modules, "opentelemetry", raising=False)
    monkeypatch.delitem(sys.modules, "opentelemetry.trace", raising=False)
    tracer = Tracer()
    calls = []

    @tracer.capture_method
    def work():
        tracer.set_attribute("key", "value")
        tracer.add_event("event")
        calls.append("work")
        return "ok"

    assert work() == "ok"
    assert calls == ["work"]


def test_tracer_defaults_service_like_logger(monkeypatch):
    monkeypatch.delenv("SERVICE_NAME", raising=False)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    assert Tracer().service == "service"

    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "lambda-name")
    assert Tracer().service == "lambda-name"

    monkeypatch.setenv("SERVICE_NAME", "orders")
    assert Tracer().service == "orders"
    assert Tracer(service="explicit").service == "explicit"


def test_tracer_capture_lambda_handler_sets_lambda_attributes(fake_otel):
    tracer = Tracer(service="orders")

    @tracer.capture_lambda_handler
    def handler(_event, _context):
        return {"ok": True}

    assert handler({}, Context()) == {"ok": True}
    assert handler({}, Context()) == {"ok": True}

    first, second = fake_otel.spans
    assert first.name == "handler"
    assert first.attributes["faas.coldstart"] is True
    assert first.attributes["faas.execution"] == "req-1"
    assert first.attributes["faas.name"] == "orders"
    assert second.attributes["faas.coldstart"] is False


def test_tracer_capture_method_records_attributes_events_and_exceptions(fake_otel):
    tracer = Tracer()

    @tracer.capture_method(name="custom", attributes={"component": "test"})
    def work():
        tracer.set_attribute("inside", True)
        tracer.add_event("step", {"n": 1})
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        work()

    span = fake_otel.spans[0]
    assert span.name == "custom"
    assert span.attributes["component"] == "test"
    assert fake_otel.current_span.attributes["inside"] is True
    assert fake_otel.current_span.events == [("step", {"n": 1})]
    assert isinstance(span.exceptions[0], RuntimeError)
    assert span.status.code == "ERROR"


def test_tracer_does_not_swallow_user_attribute_errors(fake_otel):
    tracer = Tracer()

    @tracer.capture_method
    def work():
        raise AttributeError("missing")

    with pytest.raises(AttributeError, match="missing"):
        work()

    assert isinstance(fake_otel.spans[0].exceptions[0], AttributeError)
