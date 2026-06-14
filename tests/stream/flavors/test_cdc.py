import logging
from typing import Any, Dict

from modmex_lambda.connectors.ieventbridge import IEventBridgeConnector
from modmex_lambda.stream.flavors.cdc import CdcRule, ChangeDataCapture
from modmex_lambda.stream.sources.dynamodb import dynamodb_source
from modmex_lambda.stream.utils.contracts import DynamoDBEvent, Uow
from modmex_lambda.stream.rules_registry import RulesRegistry
from tests.stream.flavors.source_events import dynamodb_stream_event

class FakeConnector(IEventBridgeConnector):
    def __init__(self):
        self.requests = []

    @property
    def client(self) -> Any:
        return None

    def put_events(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self.requests.append(params)
        return {
            'Entries': [
                {'EventId': f"event-{index}"}
                for index, _ in enumerate(params['Entries'])
            ]
        }

class FakeDependencyResolver:
    def __init__(self, connector):
        self.connector = connector
        self.resolved = []

    def resolve(self, dependency):
        self.resolved.append(dependency)
        return self.connector

def _to_captured_thing_event(uow: Uow[DynamoDBEvent]):
    return {
        'thing': uow['event']['raw']['new'],
        'raw': None,
    }

def _to_thing_event(uow: Uow[DynamoDBEvent]):
    return {
        'thing': uow['event']['raw']['new'],
    }

def _to_thing_events(uow: Uow[DynamoDBEvent]):
    thing = uow['event']['raw']['new']
    return [
        {
            'type': 'thing-created',
            'thing': thing,
        },
        {
            'type': 'thing-index-requested',
            'thing': {
                'id': thing['id'],
                'name': thing['name'],
            },
        },
    ]

def test_change_data_capture_enriches_matching_events():
    event = dynamodb_stream_event([
        {
            'keys': {'pk': '1', 'sk': 'thing'},
            'new_image': {
                "pk": "1",
                "sk": "thing",
                "discriminator": "thing",
                "timestamp": 1548967022000,
                "id": "1",
                "name": "Thing 1",
                "latched": False
            }
        },
    ])
    rule: CdcRule[DynamoDBEvent] = {
        'id': 'l1',
        'event_type': 'thing-created',
        'to_event': _to_captured_thing_event,
    }

    flavor = ChangeDataCapture[DynamoDBEvent](
        rule,
        logger=logging.getLogger('test-cdc'),
        connector=FakeConnector(),
    )

    collected = []
    @dynamodb_source(
        RulesRegistry().registry(flavor),
        concurrency=False,
        on_next=lambda _, uow: collected.append(uow),
    )
    def handler(_event, _context):
        return {"statusCode": 200}

    handler(event, None)

    assert len(collected) == 1
    assert collected[0]['event']['thing'] == {
        "pk": "1",
        "sk": "thing",
        "discriminator": "thing",
        "timestamp": 1548967022000,
        "id": "1",
        "name": "Thing 1",
        "latched": False
    }
    assert collected[0]['event']['raw'] is None

def test_change_data_capture_emits_multiple_events_from_one_uow():
    event = dynamodb_stream_event([
        {
            'keys': {'pk': '1', 'sk': 'thing'},
            'new_image': {
                "pk": "1",
                "sk": "thing",
                "discriminator": "thing",
                "timestamp": 1548967022000,
                "id": "1",
                "name": "Thing 1",
                "latched": False
            }
        },
    ])
    connector = FakeConnector()
    rule: CdcRule[DynamoDBEvent] = {
        'id': 'l1',
        'event_type': 'thing-created',
        'to_event': _to_thing_events,
    }
    flavor = ChangeDataCapture[DynamoDBEvent](
        rule,
        logger=logging.getLogger('test-cdc'),
        connector=connector,
    )

    collected = []
    @dynamodb_source(
        RulesRegistry().registry(flavor),
        concurrency=False,
        on_next=lambda _, uow: collected.append(uow),
    )
    def handler(_event, _context):
        return {"statusCode": 200}

    handler(event, None)

    assert [uow['event']['type'] for uow in collected] == [
        'thing-created',
        'thing-index-requested',
    ]
    assert collected[0]['event']['thing']['id'] == '1'
    assert collected[1]['event']['thing'] == {
        'id': '1',
        'name': 'Thing 1',
    }
    assert len(connector.requests) == 1
    assert [
        entry['DetailType']
        for entry in connector.requests[0]['Entries']
    ] == [
        'thing-created',
        'thing-index-requested',
    ]

def test_change_data_capture_filters_latched_and_non_matching_events():
    event = dynamodb_stream_event([
        {
            'keys': {'pk': '1', 'sk': 'thing'},
            'new_image': {
                "pk": "1",
                "sk": "thing",
                "discriminator": "thing",
                "timestamp": 1548967022000,
                "id": "latched",
                "latched": True
            }
        },
        {
            'keys': {'pk': '2', 'sk': 'other'},
            'new_image': {
                "pk": "2",
                "sk": "other",
                "discriminator": "other",
                "timestamp": 1548967023000,
                "id": "other",
                "latched": False
            }
        },
        {
            'keys': {'pk': '3', 'sk': 'thing'},
            'new_image': {
                "pk": "3",
                "sk": "thing",
                "discriminator": "thing",
                "timestamp": 1548967024000,
                "id": "captured",
                "latched": False
            }
        },
    ])
    rule: CdcRule[DynamoDBEvent] = {
        'id': 'l1',
        'event_type': 'thing-created',
        'to_event': _to_thing_event,
    }
    flavor = ChangeDataCapture[DynamoDBEvent](
        rule,
        logger=logging.getLogger('test-cdc'),
        connector=FakeConnector(),
    )

    collected = []
    @dynamodb_source(
        RulesRegistry().registry(flavor),
        concurrency=False,
        on_next=lambda _, uow: collected.append(uow),
    )
    def handler(_event, _context):
        return {"statusCode": 200}

    handler(event, None)

    assert [uow['event']['thing']['id'] for uow in collected] == ['captured']

def test_change_data_capture_resolves_publisher_connector_lazily():
    event = dynamodb_stream_event([
        {
            'keys': {'pk': '1', 'sk': 'thing'},
            'new_image': {
                "pk": "1",
                "sk": "thing",
                "discriminator": "thing",
                "timestamp": 1548967022000,
                "id": "1",
                "name": "Thing 1",
                "latched": False
            }
        },
    ])
    resolver = FakeDependencyResolver(FakeConnector())
    rule: CdcRule[DynamoDBEvent] = {
        'id': 'l1',
        'event_type': 'thing-created',
        'to_event': _to_captured_thing_event,
    }
    flavor = ChangeDataCapture[DynamoDBEvent](
        rule,
        logger=logging.getLogger('test-cdc'),
    )

    assert resolver.resolved == []

    @dynamodb_source(
        RulesRegistry().registry(flavor),
        concurrency=False,
        dependency_resolver=resolver,
    )
    def handler(_event, _context):
        return {"statusCode": 200}

    handler(event, None)

    assert resolver.resolved == [IEventBridgeConnector]
