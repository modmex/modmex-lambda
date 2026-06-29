"""DynamoDB helpers for materialized view update requests."""

from __future__ import annotations

from typing import Any, Callable

from modmex_lambda.persistence.dynamodb.expressions import timestamp_condition, update_expression
from modmex_lambda.persistence.dynamodb.stream_fields import stream_entity_fields
from modmex_lambda.stream.utils.time import ttl as stream_ttl


class DynamoDBUpdateRequestMixin:
    """Build DynamoDB UpdateItem requests with a timestamp guard by default."""

    def build_update_request(
        self,
        *,
        key: dict[str, Any],
        fields: dict[str, Any],
        timestamp_condition_enabled: bool = True,
    ) -> dict[str, Any]:
        request = {
            "Key": key,
            **update_expression(fields),
        }

        if timestamp_condition_enabled:
            request.update(timestamp_condition())

        return request


class MaterializedViewMixin(DynamoDBUpdateRequestMixin):
    """Map stream unit-of-work events into DynamoDB materialized view updates."""

    discriminator: str
    materialized_source_name: str | None = None
    materialized_last_modified_by: str | None = "system"
    use_ttl: bool = False
    days_ttl: int = 30

    @classmethod
    def materialized_update_request_mapper(cls) -> Callable[[dict[str, Any]], dict[str, Any]]:
        materializer = cls.__new__(cls)
        return materializer.to_materialized_update_request

    def to_materialized_update_request(self, uow: dict[str, Any]) -> dict[str, Any]:
        entity_name = self.materialized_source_name or self.discriminator
        entity = uow["event"][entity_name]

        return self.build_update_request(
            key=self.materialized_key(uow, entity),
            fields=self.materialized_fields(uow, entity),
        )

    def materialized_key(self, uow: dict[str, Any], entity: dict[str, Any]) -> dict[str, Any]:
        return {
            "pk": entity["id"],
            "sk": entity.get("sk", self.discriminator),
        }

    def materialized_fields(self, uow: dict[str, Any], entity: dict[str, Any]) -> dict[str, Any]:
        timestamp = uow["event"]["timestamp"]
        source_name = self.materialized_source_name or self.discriminator
        fields = {
            **{key: value for key, value in entity.items() if key not in ["pk", "sk"]},
            **stream_entity_fields(
                self.discriminator,
                timestamp=timestamp,
                deleted=True if uow["event"]["type"] == f"{source_name}-deleted" else None,
                latched=True,
                ttl=stream_ttl(timestamp, self.days_ttl) if self.use_ttl else None,
            ),
        }
        if self.materialized_last_modified_by is not None:
            fields["last_modified_by"] = self.materialized_last_modified_by
        return fields


__all__ = ["DynamoDBUpdateRequestMixin", "MaterializedViewMixin"]
