from typing import Any

from expects import equal, expect
from pydash import get

from modmex_lambda.connectors.idynamodb import IDynamodbConnector
from modmex_lambda.connectors.ieventbridge import IEventBridgeConnector
from modmex_lambda.stream.flavors.job import Job
from modmex_lambda.stream.rules_registry import RulesRegistry
from modmex_lambda.stream.sources.dynamodb import dynamodb_source
from modmex_lambda.stream.utils.dynamodb import timestamp_condition, update_expression
from tests.stream.flavors.source_events import dynamodb_stream_event


class FakeDynamoDBConnector(IDynamodbConnector):
    def __init__(self, pages=None):
        self.table_name = 'Things'
        self.retry_config = {}
        self.pages = list(pages or [])
        self.query_page_calls = []
        self.update_calls = []

    @property
    def client(self) -> Any:
        return None

    def get(self, input_params):
        return {}

    def update(self, input_params):
        self.update_calls.append(input_params)
        return {'updated': get(input_params, 'Key.pk')}

    def put(self, input_params):
        return {}

    def query(self, input_params):
        return {}

    def query_all(self, input_params):
        return []

    def query_page(self, input_params):
        self.query_page_calls.append(input_params)
        return self.pages.pop(0)

    def scan(self, input_params):
        return {}

    def batch_get(self, input_params):
        return {}

    def bulk_insert(self, items):
        return None

    def bulk_delete(self, items):
        return None


class FakeEventBridgeConnector(IEventBridgeConnector):
    def __init__(self):
        self.put_events_calls = []

    @property
    def client(self) -> Any:
        return None

    def put_events(self, params):
        self.put_events_calls.append(params)
        return {'Entries': [{'EventId': str(index)} for index, _ in enumerate(params['Entries'])]}


class FakeDependencyResolver:
    def __init__(self, dynamodb_connector, eventbridge_connector):
        self.dynamodb_connector = dynamodb_connector
        self.eventbridge_connector = eventbridge_connector

    def resolve(self, dependency):
        if dependency.__name__ == 'IDynamodbConnector':
            return self.dynamodb_connector
        if dependency.__name__ == 'IEventBridgeConnector':
            return self.eventbridge_connector
        raise ValueError(dependency)


def to_query_split_request(uow, _rule):
    return {
        'ExclusiveStartKey': get(uow, 'event.raw.new.cursor'),
        'ExpressionAttributeNames': {
            '#discriminator': 'discriminator',
        },
        'ExpressionAttributeValues': {
            ':discriminator': 'thing',
        },
        'Limit': 2,
    }


def to_event(uow, _rule):
    return {
        'type': 'thing-pending-detected',
        'raw': get(uow, 'query_split_response.Item'),
    }


def to_cursor_update_request(uow, _rule):
    return {
        'Key': {
            'pk': get(uow, 'event.raw.new.pk'),
            'sk': get(uow, 'event.raw.new.sk'),
        },
        **update_expression({
            'cursor': get(uow, 'query_split_response.LastEvaluatedKey'),
            'timestamp': get(uow, 'event.timestamp'),
        }),
        **timestamp_condition(),
    }


def test_job_starts_from_created_job_record_and_flushes_cursor():
    dynamodb_connector = FakeDynamoDBConnector([
        {
            'LastEvaluatedKey': {
                'pk': 'thing-2',
                'sk': 'thing',
            },
            'Items': [
                {
                    'pk': 'thing-1',
                    'sk': 'thing',
                    'status': 'PENDING',
                },
                {
                    'pk': 'thing-2',
                    'sk': 'thing',
                    'status': 'PENDING',
                },
            ],
        }
    ])
    eventbridge_connector = FakeEventBridgeConnector()
    resolver = FakeDependencyResolver(dynamodb_connector, eventbridge_connector)
    event = dynamodb_stream_event([
        {
            'keys': {'pk': 'job-1', 'sk': 'job'},
            'new_image': {
                'pk': 'job-1',
                'sk': 'job',
                'discriminator': 'job',
            },
            'timestamp': 1572832690,
        },
    ])
    collected = []

    @dynamodb_source(
        RulesRegistry().registry(
            Job({
                'id': 'pending-things-started',
                'event_type': 'job-created',
                'to_query_split_request': to_query_split_request,
                'to_event': to_event,
                'to_cursor_update_request': to_cursor_update_request,
            })
        ),
        concurrency=False,
        dependency_resolver=resolver,
        on_next=lambda _, uow: collected.append(uow),
    )
    def handler(_event, _context):
        return {'statusCode': 200}

    handler(event, None)

    expect(len(collected)).to(equal(3))
    expect(dynamodb_connector.query_page_calls[0]).to(equal({
        'ExpressionAttributeNames': {
            '#discriminator': 'discriminator',
        },
        'ExpressionAttributeValues': {
            ':discriminator': 'thing',
        },
        'Limit': 2,
    }))
    expect(get(collected, '[0].emit.raw.pk')).to(equal('thing-1'))
    expect(get(collected, '[1].emit.raw.pk')).to(equal('thing-2'))
    expect(get(collected, '[2].cursor_update_request.Key')).to(equal({
        'pk': 'job-1',
        'sk': 'job',
    }))
    expect(get(collected, '[2].cursor_update_request.ExpressionAttributeValues.:cursor')).to(equal({
        'pk': 'thing-2',
        'sk': 'thing',
    }))
    expect(len(eventbridge_connector.put_events_calls[0]['Entries'])).to(equal(2))


def test_job_continues_from_cursor_and_clears_cursor_when_done():
    dynamodb_connector = FakeDynamoDBConnector([
        {
            'Items': [
                {
                    'pk': 'thing-3',
                    'sk': 'thing',
                    'status': 'PENDING',
                },
                {
                    'pk': 'thing-4',
                    'sk': 'thing',
                    'status': 'PENDING',
                    'deleted': True,
                },
            ],
        }
    ])
    eventbridge_connector = FakeEventBridgeConnector()
    resolver = FakeDependencyResolver(dynamodb_connector, eventbridge_connector)
    event = dynamodb_stream_event([
        {
            'event_name': 'MODIFY',
            'keys': {'pk': 'job-1', 'sk': 'job'},
            'new_image': {
                'pk': 'job-1',
                'sk': 'job',
                'discriminator': 'job',
                'cursor': {
                    'pk': 'thing-2',
                    'sk': 'thing',
                },
            },
            'old_image': {
                'pk': 'job-1',
                'sk': 'job',
                'discriminator': 'job',
            },
            'timestamp': 1572832694,
        },
    ])
    collected = []

    @dynamodb_source(
        RulesRegistry().registry(
            Job({
                'id': 'pending-things-continued',
                'event_type': 'job-updated',
                'job_filters': [lambda uow, _rule: bool(get(uow, 'event.raw.new.cursor'))],
                'filters': [
                    lambda uow, _rule: not get(
                        uow,
                        'query_split_response.Item.deleted',
                        False,
                    )
                ],
                'to_query_split_request': to_query_split_request,
                'to_event': to_event,
                'to_cursor_update_request': to_cursor_update_request,
            })
        ),
        concurrency=False,
        dependency_resolver=resolver,
        on_next=lambda _, uow: collected.append(uow),
    )
    def handler(_event, _context):
        return {'statusCode': 200}

    handler(event, None)

    expect(len(collected)).to(equal(2))
    expect(dynamodb_connector.query_page_calls[0]['ExclusiveStartKey']).to(equal({
        'pk': 'thing-2',
        'sk': 'thing',
    }))
    expect(get(collected, '[0].emit.raw.pk')).to(equal('thing-3'))
    expect(get(collected, '[1].cursor_update_request.ExpressionAttributeValues')).to(equal({
        ':timestamp': 1572832694000,
    }))
    expect(get(collected, '[1].cursor_update_request.UpdateExpression')).to(
        equal('SET #timestamp = :timestamp REMOVE #cursor')
    )
    expect(len(eventbridge_connector.put_events_calls[0]['Entries'])).to(equal(1))
