from __future__ import annotations

import pytest

from modmex_lambda.persistence.dynamodb import (
    DefaultStreamFieldsStrategy,
    StreamFieldsStrategy,
    stream_entity_fields,
)


def test_stream_entity_fields_builds_standard_stream_contract_fields(monkeypatch) -> None:
    monkeypatch.setenv("REGION", "us-west-2")

    fields = stream_entity_fields(
        "thing",
        timestamp=1548967022000,
        deleted=True,
        latched=False,
        ttl=1549053422,
    )

    assert fields == {
        "discriminator": "thing",
        "deleted": True,
        "latched": False,
        "ttl": 1549053422,
        "awsregion": "us-west-2",
        "timestamp": 1548967022000,
    }


def test_stream_entity_fields_allows_explicit_region(monkeypatch) -> None:
    monkeypatch.setenv("REGION", "us-west-2")

    fields = stream_entity_fields(
        "thing",
        timestamp=1548967022000,
        awsregion="us-east-1",
    )

    assert fields == {
        "discriminator": "thing",
        "deleted": None,
        "latched": False,
        "ttl": None,
        "awsregion": "us-east-1",
        "timestamp": 1548967022000,
    }


def test_stream_fields_strategy_is_abstract() -> None:
    with pytest.raises(TypeError):
        StreamFieldsStrategy()


def test_default_stream_fields_strategy_builds_save_fields(monkeypatch) -> None:
    monkeypatch.setenv("REGION", "us-west-2")
    strategy = DefaultStreamFieldsStrategy("thing")

    fields = strategy.fields_for_save(
        {
            "pk": "thing-1",
            "sk": "thing",
            "name": "Desk",
            "discriminator": "wrong",
            "timestamp": 1,
        },
        timestamp=1548967022000,
        ttl=1549053422,
    )

    assert fields == {
        "name": "Desk",
        "discriminator": "thing",
        "deleted": None,
        "latched": False,
        "ttl": 1549053422,
        "awsregion": "us-west-2",
        "timestamp": 1548967022000,
    }


def test_default_stream_fields_strategy_builds_delete_fields(monkeypatch) -> None:
    monkeypatch.setenv("REGION", "us-west-2")
    strategy = DefaultStreamFieldsStrategy("thing")

    fields = strategy.fields_for_delete(
        {
            "pk": "thing-1",
            "sk": "thing",
            "name": "Desk",
            "deleted": None,
        },
        timestamp=1548967022000,
    )

    assert fields == {
        "name": "Desk",
        "discriminator": "thing",
        "deleted": True,
        "latched": False,
        "ttl": None,
        "awsregion": "us-west-2",
        "timestamp": 1548967022000,
    }


def test_default_stream_fields_strategy_can_calculate_timestamp(monkeypatch) -> None:
    monkeypatch.setattr("modmex_lambda.persistence.dynamodb.stream_fields.now", lambda: 1548967022000)
    monkeypatch.setenv("REGION", "us-west-2")
    strategy = DefaultStreamFieldsStrategy("thing")

    fields = strategy.fields_for_save({"name": "Desk"})

    assert fields["timestamp"] == 1548967022000
    assert fields["ttl"] is None


def test_default_stream_fields_strategy_can_calculate_ttl_from_configuration(monkeypatch) -> None:
    monkeypatch.setattr("modmex_lambda.persistence.dynamodb.stream_fields.now", lambda: 1000)
    strategy = DefaultStreamFieldsStrategy("thing", use_ttl=True, days_ttl=2)

    fields = strategy.fields_for_save({"name": "Desk"})

    assert fields["timestamp"] == 1000
    assert fields["ttl"] == 172801
