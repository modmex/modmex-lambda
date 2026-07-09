"""Reusable DynamoDB key strategies.

These helpers keep key-shaping decisions explicit while letting repositories
stay focused on persistence behavior.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Mapping



AggregateNameResolver = Callable[..., str]
AggregateIdResolver = Callable[..., str]


class KeyStrategy(ABC):
    """Build DynamoDB primary keys for ids and entities."""

    @abstractmethod
    def key_for_id(self, record_id: Any, **context: Any) -> dict[str, str]:
        raise NotImplementedError

    @abstractmethod
    def key_for_record(self, record: Any, **context: Any) -> dict[str, str]:
        raise NotImplementedError


@dataclass(frozen=True)
class SingleEntityKeyStrategy(KeyStrategy):
    """Use the record id as pk and a fixed discriminator as sk."""

    discriminator: str
    separator: str = "#"

    def key_for_id(self, record_id: Any, **context: Any) -> dict[str, str]:
        return {
            "pk": f"{self.discriminator}{self.separator}{record_id}",
            "sk": self.discriminator,
        }

    def key_for_record(self, record: Any, **context: Any) -> dict[str, str]:
        return self.key_for_id(_record_attr(record, "id"), **context)


@dataclass(frozen=True)
class TenantScopedSortKeyStrategy(KeyStrategy):
    """Use discriminator + record id as pk and tenant name + tenant id as sk."""

    discriminator: str
    tenant_name: str = "tenant"
    tenant_field: str = "tenant_id"
    separator: str = "#"

    def key_for_id(self, record_id: Any, **context: Any) -> dict[str, str]:
        tenant_id = _context_value(context, self.tenant_field)
        return {
            "pk": f"{self.discriminator}{self.separator}{record_id}",
            "sk": f"{self.tenant_name}{self.separator}{tenant_id}",
        }

    def key_for_record(self, record: Any, **context: Any) -> dict[str, str]:
        tenant_id = _context_or_record_value(context, record, self.tenant_field)
        return self.key_for_id(_record_attr(record, "id"), **{self.tenant_field: tenant_id})



@dataclass(frozen=True)
class TenantPartitionKeyStrategy(KeyStrategy):
    """Use tenant name + tenant id as pk and discriminator + record id as sk."""

    discriminator: str
    tenant_name: str = "tenant"
    tenant_field: str = "tenant_id"
    separator: str = "#"

    def key_for_id(self, record_id: Any, **context: Any) -> dict[str, str]:
        tenant_id = _context_value(context, self.tenant_field)
        return {
            "pk": f"{self.tenant_name}{self.separator}{tenant_id}",
            "sk": f"{self.discriminator}{self.separator}{record_id}",
        }

    def key_for_record(self, record: Any, **context: Any) -> dict[str, str]:
        tenant_id = _context_or_record_value(context, record, self.tenant_field)
        return self.key_for_id(_record_attr(record, "id"), **{self.tenant_field: tenant_id})

@dataclass(frozen=True)
class AggregateKeyStrategy(KeyStrategy):
    """Use aggregate name + aggregate id as pk and discriminator + record id as sk."""

    discriminator: str
    aggregate_name: str | AggregateNameResolver
    aggregate_field: str | AggregateIdResolver
    separator: str = "#"

    def key_for_id(self, record_id: Any, **context: Any) -> dict[str, str]:
        aggregate_name = self._resolve_aggregate_name(
            record=None,
            record_id=record_id,
            context=context,
        )

        aggregate_id = self._resolve_aggregate_id(
            record=None,
            record_id=record_id,
            context=context,
        )

        return self._build_key(
            aggregate_name=aggregate_name,
            aggregate_id=aggregate_id,
            record_id=record_id,
        )

    def key_for_record(self, record: Any, **context: Any) -> dict[str, str]:
        record_id = _record_attr(record, "id")

        aggregate_name = self._resolve_aggregate_name(
            record=record,
            record_id=record_id,
            context=context,
        )

        aggregate_id = self._resolve_aggregate_id(
            record=record,
            record_id=record_id,
            context=context,
        )

        return self._build_key(
            aggregate_name=aggregate_name,
            aggregate_id=aggregate_id,
            record_id=record_id,
        )

    def _build_key(
        self,
        *,
        aggregate_name: str,
        aggregate_id: Any,
        record_id: Any,
    ) -> dict[str, str]:
        return {
            "pk": f"{aggregate_name}{self.separator}{aggregate_id}",
            "sk": f"{self.discriminator}{self.separator}{record_id}",
        }

    def _resolve_aggregate_name(
        self,
        *,
        record: Any | None,
        record_id: Any,
        context: Mapping[str, Any],
    ) -> str:
        if callable(self.aggregate_name):
            return self.aggregate_name(
                record=record,
                record_id=record_id,
                context=context,
            )

        return self.aggregate_name

    def _resolve_aggregate_id(
        self,
        *,
        record: Any | None,
        record_id: Any,
        context: Mapping[str, Any],
    ) -> Any:
        if callable(self.aggregate_field):
            return self.aggregate_field(
                record=record,
                record_id=record_id,
                context=context,
            )

        if record is None:
            return _context_value(context, self.aggregate_field)

        return _context_or_record_value(context, record, self.aggregate_field)
    


def _context_value(context: dict[str, Any], field_name: str) -> Any:
    if field_name in context and context[field_name] is not None:
        return context[field_name]
    raise KeyError(f"Missing required key context: {field_name}")


def _context_or_record_value(context: dict[str, Any], record: Any, field_name: str) -> Any:
    if field_name in context and context[field_name] is not None:
        return context[field_name]
    value = _record_attr(record, field_name)
    if value is not None:
        return value
    raise AttributeError(f"record is missing required field: {field_name}")


def _record_attr(record: Any, field_name: str) -> Any:
    if isinstance(record, dict):
        try:
            return record[field_name]
        except KeyError as exc:
            raise AttributeError(f"record is missing required field: {field_name}") from exc
    try:
        return getattr(record, field_name)
    except AttributeError as exc:
        raise AttributeError(f"record is missing required field: {field_name}") from exc
