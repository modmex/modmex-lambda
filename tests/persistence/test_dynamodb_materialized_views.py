from __future__ import annotations

from modmex_lambda.persistence.dynamodb import DynamoDBUpdateRequestMixin, MaterializedViewMixin


class ThingMaterializer(MaterializedViewMixin):
    discriminator = "thing"
    use_ttl = True
    days_ttl = 1


class ThingSearchMaterializer(MaterializedViewMixin):
    discriminator = "thing-search"
    materialized_source_name = "thing"

    def materialized_key(self, uow, entity):
        return {
            "pk": entity["tenant_id"],
            "sk": f"thing-search#{entity['id']}",
        }

    def materialized_fields(self, uow, entity):
        return {
            **super().materialized_fields(uow, entity),
            "search_text": f"{entity['name']} {entity['tenant_id']}",
        }


def test_update_request_mixin_builds_timestamp_guarded_update_request() -> None:
    request = DynamoDBUpdateRequestMixin().build_update_request(
        key={"pk": "thing-1", "sk": "thing"},
        fields={"name": "Desk", "timestamp": 1548967022000},
    )

    assert request["Key"] == {"pk": "thing-1", "sk": "thing"}
    assert request["ExpressionAttributeValues"][":name"] == "Desk"
    assert request["ExpressionAttributeValues"][":timestamp"] == 1548967022000
    assert request["ConditionExpression"] == "attribute_not_exists(#timestamp) OR #timestamp < :timestamp"


def test_update_request_mixin_can_skip_timestamp_condition() -> None:
    request = DynamoDBUpdateRequestMixin().build_update_request(
        key={"pk": "thing-1", "sk": "thing"},
        fields={"name": "Desk"},
        timestamp_condition_enabled=False,
    )

    assert "ConditionExpression" not in request


def test_materialized_view_mixin_replicates_event_entity_with_stream_fields(monkeypatch) -> None:
    monkeypatch.setenv("REGION", "us-west-2")
    uow = {
        "event": {
            "type": "thing-deleted",
            "timestamp": 1548967022000,
            "thing": {
                "id": "thing-1",
                "pk": "thing#thing-1",
                "sk": "thing",
                "name": "Desk",
            },
        },
    }

    request = ThingMaterializer().to_materialized_update_request(uow)

    assert request["Key"] == {"pk": "thing#thing-1", "sk": "thing"}
    assert request["ExpressionAttributeValues"][":id"] == "thing-1"
    assert request["ExpressionAttributeValues"][":name"] == "Desk"
    assert request["ExpressionAttributeValues"][":discriminator"] == "thing"
    assert request["ExpressionAttributeValues"][":deleted"] is True
    assert request["ExpressionAttributeValues"][":latched"] is True
    assert request["ExpressionAttributeValues"][":ttl"] == 1549053422
    assert request["ExpressionAttributeValues"][":awsregion"] == "us-west-2"
    assert request["ExpressionAttributeValues"][":last_modified_by"] == "system"
    assert "#pk" not in request["ExpressionAttributeNames"]
    assert "#sk" not in request["ExpressionAttributeNames"]
    assert request["ConditionExpression"] == "attribute_not_exists(#timestamp) OR #timestamp < :timestamp"


def test_materialized_view_mixin_supports_custom_source_key_and_fields() -> None:
    uow = {
        "event": {
            "type": "thing-updated",
            "timestamp": 1548967022000,
            "thing": {
                "id": "thing-1",
                "tenant_id": "tenant-1",
                "name": "Desk",
            },
        },
    }

    request = ThingSearchMaterializer().to_materialized_update_request(uow)

    assert request["Key"] == {"pk": "tenant-1", "sk": "thing-search#thing-1"}
    assert request["ExpressionAttributeValues"][":discriminator"] == "thing-search"
    assert request["ExpressionAttributeValues"][":search_text"] == "Desk tenant-1"


def test_materialized_view_mixin_class_mapper_uses_class_configuration() -> None:
    mapper = ThingMaterializer.materialized_update_request_mapper()
    uow = {
        "event": {
            "type": "thing-updated",
            "timestamp": 1548967022000,
            "thing": {"id": "thing-1", "name": "Desk"},
        },
    }

    request = mapper(uow)

    assert request["Key"] == {"pk": "thing-1", "sk": "thing"}
    assert request["ExpressionAttributeValues"][":ttl"] == 1549053422
