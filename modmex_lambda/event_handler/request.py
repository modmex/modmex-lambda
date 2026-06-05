"""API Gateway event normalization."""

from __future__ import annotations

from typing import Any

from modmex_lambda.data_classes.common import BaseProxyEvent


class Request:
    
    __slots__ = (
        "_route_path",
        "_path_parameters",
        "_current_event",
        "_context",
    )
    
    def __init__(
        self,
        route_path: str,
        path_parameters: dict[str, Any],
        current_event: BaseProxyEvent,
        context: dict[str, Any] | None = None,
    )->None:
        self._route_path = route_path
        self._path_parameters = path_parameters
        self._current_event = current_event
        self._context = context if context is not None else {}

    
    @property
    def route(self) -> str:
        return self._route_path
    
    @property
    def path_parameters(self) -> dict[str, Any]:
        return self._path_parameters
    
    @property
    def method(self) -> str:
        return self._current_event.http_method.upper()
    
    @property
    def headers(self) -> dict[str, str]:
        return self._current_event.headers or {}
    
    @property
    def query_parameters(self) -> dict[str, str] | None:
        return self._current_event.query_string_parameters
    
    @property
    def resolved_event(self) -> BaseProxyEvent:
        return self._current_event
    
    @property
    def body(self) -> Any:
        return self._current_event.body
    
    @property
    def json_body(self) -> Any:
        return self._current_event.json_body
    
    @property
    def current_event(self) -> BaseProxyEvent:
        return self._current_event
    
    @property
    def context(self) -> dict[str, Any]:
        return self._context
