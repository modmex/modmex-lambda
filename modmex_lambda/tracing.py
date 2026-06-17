"""Lazy OpenTelemetry-compatible tracing helpers."""

from __future__ import annotations

import inspect
import os
from contextlib import contextmanager
from functools import wraps
from importlib import import_module
from typing import Any, Callable, Iterator, Mapping, TypeVar


F = TypeVar("F", bound=Callable[..., Any])


class _NoopSpan:
    def set_attribute(self, _key: str, _value: Any) -> None:
        return None

    def add_event(self, _name: str, attributes: Mapping[str, Any] | None = None) -> None:
        return None

    def record_exception(self, _exception: BaseException) -> None:
        return None


class Tracer:
    """Tiny lazy tracer facade.

    The core package does not depend on OpenTelemetry. If ``opentelemetry-api``
    is unavailable, all operations are no-ops.
    """

    def __init__(
        self,
        *,
        service: str | None = None,
        enabled: bool = True,
        tracer_provider: Any | None = None,
    ) -> None:
        self.service = service or os.getenv("SERVICE_NAME") or os.getenv("AWS_LAMBDA_FUNCTION_NAME") or "service"
        self.enabled = enabled
        self.tracer_provider = tracer_provider
        self._tracer: Any | None = None
        self._cold_start = True

    def capture_method(
        self,
        func: F | None = None,
        *,
        name: str | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> F | Callable[[F], F]:
        def decorator(method: F) -> F:
            span_name = name or method.__qualname__

            if inspect.iscoroutinefunction(method):

                @wraps(method)
                async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                    with self._start_span(span_name, attributes=attributes):
                        return await method(*args, **kwargs)

                return async_wrapper  # type: ignore[return-value]

            @wraps(method)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                with self._start_span(span_name, attributes=attributes):
                    return method(*args, **kwargs)

            return wrapper  # type: ignore[return-value]

        if func is None:
            return decorator
        return decorator(func)

    def capture_lambda_handler(
        self,
        func: F | None = None,
        *,
        name: str | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> F | Callable[[F], F]:
        def decorator(handler: F) -> F:
            span_name = name or handler.__name__

            @wraps(handler)
            def wrapper(event: Any, context: Any, *args: Any, **kwargs: Any) -> Any:
                with self._start_span(span_name, attributes=attributes) as span:
                    self._set_lambda_context_attributes(span, context)
                    return handler(event, context, *args, **kwargs)

            return wrapper  # type: ignore[return-value]

        if func is None:
            return decorator
        return decorator(func)

    def set_attribute(self, key: str, value: Any) -> None:
        span = self._current_span()
        span.set_attribute(key, value)

    def add_event(self, name: str, attributes: Mapping[str, Any] | None = None) -> None:
        span = self._current_span()
        span.add_event(name, attributes=attributes)

    @contextmanager
    def _start_span(
        self,
        name: str,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> Iterator[Any]:
        tracer = self._get_tracer()
        if tracer is None:
            yield _NoopSpan()
            return

        try:
            span_context = tracer.start_as_current_span(name)
        except AttributeError:
            yield _NoopSpan()
            return

        with span_context as span:
            for key, value in (attributes or {}).items():
                span.set_attribute(key, value)
            try:
                yield span
            except Exception as exc:
                span.record_exception(exc)
                self._set_error_status(span)
                raise

    def _get_tracer(self) -> Any | None:
        if not self.enabled:
            return None
        if self._tracer is not None:
            return self._tracer

        try:
            trace = import_module("opentelemetry.trace")
        except ImportError:
            return None

        self._tracer = trace.get_tracer(
            __name__,
            tracer_provider=self.tracer_provider,
        )
        return self._tracer

    def _current_span(self) -> Any:
        if not self.enabled:
            return _NoopSpan()

        try:
            trace = import_module("opentelemetry.trace")
        except ImportError:
            return _NoopSpan()

        try:
            return trace.get_current_span()
        except AttributeError:
            return _NoopSpan()

    def _set_lambda_context_attributes(self, span: Any, context: Any) -> None:
        if self._cold_start:
            span.set_attribute("faas.coldstart", True)
            self._cold_start = False
        else:
            span.set_attribute("faas.coldstart", False)

        request_id = getattr(context, "aws_request_id", None)
        if request_id:
            span.set_attribute("faas.execution", str(request_id))

        function_name = getattr(context, "function_name", None)
        if function_name:
            span.set_attribute("faas.name", str(function_name))

    def _set_error_status(self, span: Any) -> None:
        try:
            trace = import_module("opentelemetry.trace")
            span.set_status(trace.Status(trace.StatusCode.ERROR))
        except (ImportError, AttributeError):
            return


__all__ = ["Tracer"]
