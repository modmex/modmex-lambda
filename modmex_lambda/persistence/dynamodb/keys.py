"""Reusable DynamoDB key strategies.

These helpers keep key-shaping decisions explicit while letting repositories
stay focused on persistence behavior.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class KeyStrategy(ABC):
    """Build DynamoDB primary keys for ids and entities."""

    @abstractmethod
    def key_for_id(self, entity_id: Any, **context: Any) -> dict[str, str]:
        raise NotImplementedError

    @abstractmethod
    def key_for_entity(self, entity: Any, **context: Any) -> dict[str, str]:
        raise NotImplementedError


@dataclass(frozen=True)
class SingleEntityKeyStrategy(KeyStrategy):
    """Use the entity id as pk and a fixed discriminator as sk."""

    discriminator: str
    separator: str = "#"

    def key_for_id(self, entity_id: Any, **context: Any) -> dict[str, str]:
        return {
            "pk": f"{self.discriminator}{self.separator}{entity_id}",
            "sk": self.discriminator,
        }

    def key_for_entity(self, entity: Any, **context: Any) -> dict[str, str]:
        return self.key_for_id(_entity_attr(entity, "id"), **context)


@dataclass(frozen=True)
class TenantScopedSortKeyStrategy(KeyStrategy):
    """Use discriminator + entity id as pk and tenant name + tenant id as sk."""

    discriminator: str
    tenant_name: str = "tenant"
    tenant_field: str = "tenant_id"
    separator: str = "#"

    def key_for_id(self, entity_id: Any, **context: Any) -> dict[str, str]:
        tenant_id = _context_value(context, self.tenant_field)
        return {
            "pk": f"{self.discriminator}{self.separator}{entity_id}",
            "sk": f"{self.tenant_name}{self.separator}{tenant_id}",
        }

    def key_for_entity(self, entity: Any, **context: Any) -> dict[str, str]:
        tenant_id = _context_or_entity_value(context, entity, self.tenant_field)
        return self.key_for_id(_entity_attr(entity, "id"), **{self.tenant_field: tenant_id})



@dataclass(frozen=True)
class TenantPartitionKeyStrategy(KeyStrategy):
    """Use tenant name + tenant id as pk and discriminator + entity id as sk."""

    discriminator: str
    tenant_name: str = "tenant"
    tenant_field: str = "tenant_id"
    separator: str = "#"

    def key_for_id(self, entity_id: Any, **context: Any) -> dict[str, str]:
        tenant_id = _context_value(context, self.tenant_field)
        return {
            "pk": f"{self.tenant_name}{self.separator}{tenant_id}",
            "sk": f"{self.discriminator}{self.separator}{entity_id}",
        }

    def key_for_entity(self, entity: Any, **context: Any) -> dict[str, str]:
        tenant_id = _context_or_entity_value(context, entity, self.tenant_field)
        return self.key_for_id(_entity_attr(entity, "id"), **{self.tenant_field: tenant_id})

@dataclass(frozen=True)
class AggregateKeyStrategy(KeyStrategy):
    """Use aggregate name + aggregate id as pk and discriminator + entity id as sk."""

    discriminator: str
    aggregate_name: str
    aggregate_field: str
    separator: str = "#"
    

    def key_for_id(self, entity_id: Any, **context: Any) -> dict[str, str]:
        aggregate_id = _context_value(context, self.aggregate_field)
        return {
            "pk": f"{self.aggregate_name}{self.separator}{aggregate_id}",
            "sk": f"{self.discriminator}{self.separator}{entity_id}",
        }

    def key_for_entity(self, entity: Any, **context: Any) -> dict[str, str]:
        aggregate_id = _context_or_entity_value(context, entity, self.aggregate_field)
        return self.key_for_id(_entity_attr(entity, "id"), **{self.aggregate_field: aggregate_id})


def _context_value(context: dict[str, Any], field_name: str) -> Any:
    if field_name in context and context[field_name] is not None:
        return context[field_name]
    raise KeyError(f"Missing required key context: {field_name}")


def _context_or_entity_value(context: dict[str, Any], entity: Any, field_name: str) -> Any:
    if field_name in context and context[field_name] is not None:
        return context[field_name]
    value = _entity_attr(entity, field_name)
    if value is not None:
        return value
    raise AttributeError(f"Entity is missing required field: {field_name}")


def _entity_attr(entity: Any, field_name: str) -> Any:
    if isinstance(entity, dict):
        try:
            return entity[field_name]
        except KeyError as exc:
            raise AttributeError(f"Entity is missing required field: {field_name}") from exc
    try:
        return getattr(entity, field_name)
    except AttributeError as exc:
        raise AttributeError(f"Entity is missing required field: {field_name}") from exc
