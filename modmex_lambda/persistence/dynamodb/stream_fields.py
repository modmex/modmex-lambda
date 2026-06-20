"""Fields used by modmex-lambda stream-compatible DynamoDB items."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from modmex_lambda.stream.utils.time import now, ttl as stream_ttl


def stream_entity_fields(
    discriminator: str,
    *,
    timestamp: int,
    deleted: bool | None = None,
    latched: bool = False,
    ttl: int | None = None,
    awsregion: str | None = None,
) -> dict[str, Any]:
    """Build standard fields consumed by modmex-lambda stream processors."""

    fields = {
        "discriminator": discriminator,
        "deleted": deleted,
        "latched": latched,
        "ttl": ttl,
        "awsregion": awsregion if awsregion is not None else os.getenv("REGION"),
        "timestamp": timestamp,
    }
    return fields


class StreamFieldsStrategy(ABC):
    """Build stream-compatible item fields for DynamoDB writes."""

    @abstractmethod
    def fields_for_save(
        self,
        data: dict[str, Any],
        *,
        timestamp: int | None = None,
        ttl: int | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def fields_for_delete(
        self,
        data: dict[str, Any],
        *,
        timestamp: int | None = None,
        ttl: int | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class DefaultStreamFieldsStrategy(StreamFieldsStrategy):
    """Default stream field contract used by modmex-lambda stream processors."""

    discriminator: str
    key_fields: tuple[str, ...] = field(default=("pk", "sk"))
    use_ttl: bool = False
    days_ttl: int = 30

    def fields_for_save(
        self,
        data: dict[str, Any],
        *,
        timestamp: int | None = None,
        ttl: int | None = None,
    ) -> dict[str, Any]:
        timestamp = self._timestamp(timestamp)
        return {
            **self._without_key_fields(data),
            **stream_entity_fields(
                self.discriminator,
                timestamp=timestamp,
                deleted=None,
                latched=False,
                ttl=self._ttl(timestamp, ttl),
            ),
        }

    def fields_for_delete(
        self,
        data: dict[str, Any],
        *,
        timestamp: int | None = None,
        ttl: int | None = None,
    ) -> dict[str, Any]:
        timestamp = self._timestamp(timestamp)
        return {
            **self._without_key_fields(data),
            **stream_entity_fields(
                self.discriminator,
                timestamp=timestamp,
                deleted=True,
                latched=False,
                ttl=self._ttl(timestamp, ttl),
            ),
        }

    def _without_key_fields(self, data: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in data.items()
            if key not in self.key_fields
        }

    def _timestamp(self, timestamp: int | None) -> int:
        return timestamp if timestamp is not None else now()

    def _ttl(self, timestamp: int, ttl: int | None) -> int | None:
        if ttl is not None:
            return ttl
        if self.use_ttl:
            return stream_ttl(timestamp, self.days_ttl)
        return None
