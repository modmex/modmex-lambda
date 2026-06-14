import json

import pytest

import modmex_lambda.stream.sources.base as source_base
from modmex_lambda.stream.events.dynamodb import to_dynamodb_records
from modmex_lambda.stream.events.kinesis import to_kinesis_records
from modmex_lambda.stream.events.s3 import to_s3_records
from modmex_lambda.stream.events.sns import to_sns_records
from modmex_lambda.stream.events.sqs import to_sqs_records
from modmex_lambda.stream.sources import (
    DynamoDBSource,
    dynamodb_source,
    kinesis_source,
    s3_source,
    sns_source,
    sqs_source,
)
from modmex_lambda.stream.rules_registry import RulesRegistry


class DummyPipeline:
    id = 'pipeline'

    def __call__(self, source):
        return source


class BindablePipeline(DummyPipeline):
    def __init__(self):
        self.dependency_resolver = None

    def bind(self, dependency_resolver):
        self.dependency_resolver = dependency_resolver
        return self


@pytest.mark.parametrize(
    "factory,raw_event,expected_id",
    [
        (
            dynamodb_source,
            to_dynamodb_records([
                {
                    "timestamp": 1548967023,
                    "keys": {
                        "pk": "1",
                        "sk": "thing"
                    },
                    "newImage": {
                        "pk": "1",
                        "sk": "thing",
                        "discriminator": "thing",
                        "timestamp": 1548967022000,
                        "id": "1",
                        "latched": False
                    }
                },
            ]),
            "0",
        ),
        (
            kinesis_source,
            to_kinesis_records([
                {
                    "id": "k1",
                    "type": "thing-created",
                    "timestamp": 1548967023,
                },
            ]),
            "k1",
        ),
        (
            s3_source,
            to_s3_records([
                {
                    "bucket": {
                        "name": "bucket"
                    },
                    "object": {
                        "key": "object-key"
                    },
                },
            ]),
            "object-key",
        ),
        (
            sns_source,
            to_sns_records([
                {
                    "msg": json.dumps({
                        "type": "thing-created",
                    }),
                },
            ]),
            "00000000-0000-0000-0000-000000000000",
        ),
        (
            sqs_source,
            to_sqs_records([
                {
                    "body": json.dumps({
                        "type": "thing-created",
                    }),
                },
            ]),
            "00000000-0000-0000-0000-000000000000",
        ),
    ],
)
def test_source_handler_runs_parsed_events(monkeypatch, factory, raw_event, expected_id):
    calls = []
    on_next = lambda *_: None
    on_error = lambda *_: None
    on_completed = lambda *_: None
    pipelines = [DummyPipeline()]
    registry = RulesRegistry().registry(*pipelines)

    def fake_run(events, registry, **kwargs):
        calls.append({
            "events": list(events),
            "pipelines": registry.build(),
            "kwargs": kwargs,
        })

    monkeypatch.setattr(source_base, 'run', fake_run)

    handler = factory(
        registry,
        concurrency=False,
        on_next=on_next,
        on_error=on_error,
        on_completed=on_completed,
    )
    result = handler.handle(raw_event, None)

    assert result == {"statusCode": 200}
    assert calls[0]["events"][0]["event"]["id"] == expected_id
    assert calls[0]["pipelines"] == pipelines
    assert calls[0]["kwargs"]["concurrency"] is False
    assert calls[0]["kwargs"]["on_next"] is on_next
    assert calls[0]["kwargs"]["on_error"] is on_error
    assert calls[0]["kwargs"]["on_completed"] is on_completed


def test_source_handler_can_be_used_as_decorator(monkeypatch):
    calls = []

    def fake_run(events, registry, **kwargs):
        calls.append({
            "events": list(events),
            "pipelines": registry.build(),
            "kwargs": kwargs,
        })

    monkeypatch.setattr(source_base, 'run', fake_run)

    @kinesis_source(RulesRegistry().registry(DummyPipeline()), concurrency=False)
    def handler(_event, _context):
        return {"statusCode": 202}

    result = handler(
        to_kinesis_records([
            {
                "id": "k1",
                "type": "thing-created",
                "timestamp": 1548967023,
            },
        ]),
        None,
    )

    assert result == {"statusCode": 202}
    assert calls[0]["events"][0]["event"]["id"] == "k1"


def test_source_factory_rejects_unknown_options():
    with pytest.raises(TypeError):
        kinesis_source(RulesRegistry().registry(DummyPipeline()), unknown=True)


def test_source_handler_call_rejects_unknown_options():
    handler = kinesis_source(RulesRegistry().registry(DummyPipeline()))

    with pytest.raises(TypeError):
        handler(
            to_kinesis_records([
                {
                    "id": "k1",
                    "type": "thing-created",
                    "timestamp": 1548967023,
                },
            ]),
            None,
            unknown=True,
        )


def test_dynamodb_source_uses_parser_options(monkeypatch):
    calls = []

    def fake_run(events, registry, **kwargs):
        calls.append({
            "events": list(events),
            "pipelines": registry.build(),
            "kwargs": kwargs,
        })

    monkeypatch.setattr(source_base, 'run', fake_run)

    handler = dynamodb_source(
        RulesRegistry().registry(DummyPipeline()),
        parser_options={
            "pk_fn": "custom_pk",
            "sk_fn": "custom_sk",
            "discriminator_fn": "kind",
            "event_type_prefix": "entity",
        },
    )
    handler.handle(
        to_dynamodb_records([
            {
                "timestamp": 1548967023,
                "keys": {
                    "custom_pk": "1",
                    "custom_sk": "thing"
                },
                "newImage": {
                    "custom_pk": "1",
                    "custom_sk": "thing",
                    "kind": "ignored-by-prefix",
                    "timestamp": 1548967022000,
                    "id": "1",
                    "latched": False
                }
            },
        ]),
        None,
    )

    assert calls[0]["events"][0]["event"]["partition_key"] == "1"
    assert calls[0]["events"][0]["event"]["type"] == "entity-created"


def test_dynamodb_source_class_uses_parser_options(monkeypatch):
    calls = []

    def fake_run(events, registry, **kwargs):
        calls.append({
            "events": list(events),
            "pipelines": registry.build(),
            "kwargs": kwargs,
        })

    monkeypatch.setattr(source_base, 'run', fake_run)

    source = DynamoDBSource(
        RulesRegistry().registry(DummyPipeline()),
        parser_options={
            "pk_fn": "custom_pk",
            "sk_fn": "custom_sk",
            "discriminator_fn": "kind",
            "event_type_prefix": "entity",
        },
    )
    source.handle(
        to_dynamodb_records([
            {
                "timestamp": 1548967023,
                "keys": {
                    "custom_pk": "1",
                    "custom_sk": "thing"
                },
                "newImage": {
                    "custom_pk": "1",
                    "custom_sk": "thing",
                    "kind": "ignored-by-prefix",
                    "timestamp": 1548967022000,
                    "id": "1",
                    "latched": False
                }
            },
        ]),
        None,
    )

    assert calls[0]["events"][0]["event"]["partition_key"] == "1"
    assert calls[0]["events"][0]["event"]["type"] == "entity-created"


def test_source_handler_binds_dependency_resolver(monkeypatch):
    pipeline = BindablePipeline()
    dependency_resolver = object()

    def fake_run(events, registry, **_kwargs):
        list(events)
        registry.build()

    monkeypatch.setattr(source_base, 'run', fake_run)

    kinesis_source(
        RulesRegistry().registry(pipeline),
        dependency_resolver=dependency_resolver,
    ).handle(
        to_kinesis_records([
            {
                "id": "k1",
                "type": "thing-created",
                "timestamp": 1548967023,
            },
        ]),
        None,
    )

    assert pipeline.dependency_resolver is dependency_resolver
