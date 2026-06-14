"""Lightweight structured logger for Lambda workloads."""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Callable, TextIO


_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}


class Logger:
    def __init__(
        self,
        *,
        service: str | None = None,
        stream: TextIO | None = None,
        json_serializer: Callable[[dict[str, Any]], str] | None = None,
        correlation_id_header: str = "x-correlation-id",
        level: str | int | None = None,
    ) -> None:
        self._service = service or os.getenv("SERVICE_NAME") or os.getenv("AWS_LAMBDA_FUNCTION_NAME") or "service"
        self._stream = stream or sys.stdout
        self._serialize = json_serializer or (lambda payload: json.dumps(payload, separators=(",", ":"), default=str))
        self._correlation_id_header = correlation_id_header.lower()
        self._level = self._resolve_level(level)
        self._persistent_keys: dict[str, Any] = {}
        self._context: object | None = None
        self._event: dict[str, Any] | None = None

    def set_context(self, *, context: object | None = None, event: dict[str, Any] | None = None) -> None:
        self._context = context
        self._event = event

    def append_keys(self, **kwargs: Any) -> None:
        self._persistent_keys.update(kwargs)

    def clear_state(self) -> None:
        self._persistent_keys.clear()

    def set_level(self, level: str | int) -> None:
        self._level = self._resolve_level(level)

    def is_enabled_for(self, level: str | int) -> bool:
        return self._resolve_level(level) >= self._level

    def debug(self, message: Any, *args: Any, **kwargs: Any) -> None:
        self._log("DEBUG", message, *args, **kwargs)

    def info(self, message: Any, *args: Any, **kwargs: Any) -> None:
        self._log("INFO", message, *args, **kwargs)

    def warning(self, message: Any, *args: Any, **kwargs: Any) -> None:
        self._log("WARNING", message, *args, **kwargs)

    def error(self, message: Any, *args: Any, exc_info: bool = False, **kwargs: Any) -> None:
        self._log("ERROR", message, *args, exc_info=exc_info, **kwargs)

    def critical(self, message: Any, *args: Any, exc_info: bool = False, **kwargs: Any) -> None:
        self._log("CRITICAL", message, *args, exc_info=exc_info, **kwargs)

    def _log(self, level: str, message: Any, *args: Any, exc_info: bool = False, **kwargs: Any) -> None:
        if not self.is_enabled_for(level):
            return

        record: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "service": self._service,
            "message": self._format_message(message, args),
        }
        record.update(self._persistent_keys)

        request_id = self._extract_request_id()
        if request_id:
            record["request_id"] = request_id

        correlation_id = self._extract_correlation_id()
        if correlation_id and "correlation_id" not in record:
            record["correlation_id"] = correlation_id

        record.update(kwargs)

        if exc_info:
            record["exception"] = traceback.format_exc()

        self._stream.write(self._serialize(record) + "\n")

    def _resolve_level(self, level: str | int | None) -> int:
        if isinstance(level, int):
            return level
        level_name = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
        return _LEVELS.get(level_name, _LEVELS["INFO"])

    def _format_message(self, message: Any, args: tuple[Any, ...]) -> Any:
        if not args:
            return message
        if isinstance(message, str):
            return message % args
        return message

    def _extract_request_id(self) -> str | None:
        if self._context is None:
            return None
        value = getattr(self._context, "aws_request_id", None)
        return str(value) if value else None

    def _extract_correlation_id(self) -> str | None:
        event = self._event
        if not isinstance(event, dict):
            return None

        headers = event.get("headers")
        if not isinstance(headers, dict):
            return None

        for key, value in headers.items():
            if str(key).lower() == self._correlation_id_header and value is not None:
                return str(value)
        return None


__all__ = ["Logger"]
