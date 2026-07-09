from __future__ import annotations

from dataclasses import dataclass

import pytest

from modmex_lambda.persistence.dynamodb import (
    AggregateKeyStrategy,
    KeyStrategy,
    SingleEntityKeyStrategy,
    TenantPartitionKeyStrategy,
    TenantScopedSortKeyStrategy,
)


@dataclass
class Thing:
    id: str
    tenant_id: str | None = None
    aggregate_id: str | None = None
    account_id: str | None = None
    order_id: str | None = None


def test_key_strategy_is_abstract() -> None:
    with pytest.raises(TypeError):
        KeyStrategy()


def test_single_record_key_strategy_uses_id_as_pk_and_discriminator_as_sk() -> None:
    strategy = SingleEntityKeyStrategy("thing")

    assert strategy.key_for_id("thing-1") == {"pk": "thing#thing-1", "sk": "thing"}
    assert strategy.key_for_record(Thing(id="thing-2")) == {"pk": "thing#thing-2", "sk": "thing"}
    assert strategy.key_for_record({"id": "thing-3"}) == {"pk": "thing#thing-3", "sk": "thing"}


def test_tenant_scoped_sort_key_strategy_uses_record_id_and_tenant_scoped_sk() -> None:
    strategy = TenantScopedSortKeyStrategy("thing")

    assert strategy.key_for_id("thing-1", tenant_id="acme") == {
        "pk": "thing#thing-1",
        "sk": "tenant#acme",
    }
    assert strategy.key_for_record(Thing(id="thing-2", tenant_id="modmex")) == {
        "pk": "thing#thing-2",
        "sk": "tenant#modmex",
    }
    assert strategy.key_for_record(Thing(id="thing-3", tenant_id="ignored"), tenant_id="acme") == {
        "pk": "thing#thing-3",
        "sk": "tenant#acme",
    }


def test_tenant_scoped_sort_key_strategy_supports_custom_field_and_separator() -> None:
    strategy = TenantScopedSortKeyStrategy(
        "thing",
        tenant_name="account",
        separator=":",
        tenant_field="account_id",
    )

    assert strategy.key_for_record(Thing(id="thing-1", account_id="acct-1")) == {
        "pk": "thing:thing-1",
        "sk": "account:acct-1",
    }


def test_tenant_partition_key_strategy_uses_tenant_as_pk_and_record_scoped_sk() -> None:
    strategy = TenantPartitionKeyStrategy("thing")

    assert strategy.key_for_id("thing-1", tenant_id="acme") == {
        "pk": "tenant#acme",
        "sk": "thing#thing-1",
    }
    assert strategy.key_for_record(Thing(id="thing-2", tenant_id="modmex")) == {
        "pk": "tenant#modmex",
        "sk": "thing#thing-2",
    }


def test_tenant_partition_key_strategy_supports_custom_field_and_separator() -> None:
    strategy = TenantPartitionKeyStrategy(
        "thing",
        tenant_name="account",
        separator=":",
        tenant_field="account_id",
    )

    assert strategy.key_for_record(Thing(id="thing-1", account_id="acct-1")) == {
        "pk": "account:acct-1",
        "sk": "thing:thing-1",
    }


def test_aggregate_key_strategy_uses_aggregate_pk_and_record_sk() -> None:
    strategy = AggregateKeyStrategy("item", "order", "aggregate_id")

    assert strategy.key_for_id("item-1", aggregate_id="order-1") == {
        "pk": "order#order-1",
        "sk": "item#item-1",
    }
    assert strategy.key_for_record(Thing(id="item-2", aggregate_id="order-2")) == {
        "pk": "order#order-2",
        "sk": "item#item-2",
    }


def test_aggregate_key_strategy_supports_custom_field_and_separator() -> None:
    strategy = AggregateKeyStrategy("item", "order", separator=":", aggregate_field="order_id")

    assert strategy.key_for_record(Thing(id="item-1", order_id="order-1")) == {
        "pk": "order:order-1",
        "sk": "item:item-1",
    }


def test_aggregate_key_strategy_for_entity_with_callable() -> None:
    strategy = AggregateKeyStrategy(
        discriminator="audit",
        aggregate_name=lambda record, **_: record.entity_type,
        aggregate_field=lambda record, **_: record.entity_id,
    )

    @dataclass
    class Audit:
        id: str
        entity_type: str
        entity_id: str

    entity = Audit(id="audit-1", entity_type="order", entity_id="order-1")

    assert strategy.key_for_record(entity) == {
        "pk": "order#order-1",
        "sk": "audit#audit-1",
    }


def test_aggregate_key_strategy_for_id_with_callable() -> None:
    strategy = AggregateKeyStrategy(
        discriminator="audit",
        aggregate_name=lambda context, **_: context["entity_type"],
        aggregate_field=lambda context, **_: context["entity_id"],
    )

    assert strategy.key_for_id(
        "audit-1",
        entity_type="order",
        entity_id="order-1",
    ) == {
        "pk": "order#order-1",
        "sk": "audit#audit-1",
    }


def test_aggregate_key_strategy_callable_aggregate_name_supports_record_and_id() -> None:
    @dataclass
    class Audit:
        id: str
        entity_type: str
        entity_id: str

    strategy = AggregateKeyStrategy(
        discriminator="audit",
        aggregate_name=lambda record=None, context=None, **_: (
            record.entity_type if record is not None else context["entity_type"]
        ),
        aggregate_field=lambda record=None, context=None, **_: (
            record.entity_id if record is not None else context["entity_id"]
        ),
        separator="#",
    )

    entity = Audit(
        id="audit-1",
        entity_type="order",
        entity_id="order-1",
    )

    assert strategy.key_for_record(entity) == {
        "pk": "order#order-1",
        "sk": "audit#audit-1",
    }

    assert strategy.key_for_id(
        "audit-1",
        entity_type="order",
        entity_id="order-1",
    ) == {
        "pk": "order#order-1",
        "sk": "audit#audit-1",
    }



def test_required_context_errors_are_explicit() -> None:
    strategy = TenantPartitionKeyStrategy("thing")

    with pytest.raises(KeyError, match="tenant_id"):
        strategy.key_for_id("thing-1")

    with pytest.raises(AttributeError, match="tenant_id"):
        strategy.key_for_record(Thing(id="thing-1"))
