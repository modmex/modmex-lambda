from expects import equal, expect
from pydash import get
from modmex_lambda.connectors.dynamodb import Connector
from modmex_lambda.stream.flavors.update import Update
from modmex_lambda.stream.sources.dynamodb import dynamodb_source
from modmex_lambda.stream.sources.kinesis import kinesis_source
from modmex_lambda.stream.utils.dynamodb import update_expression
from modmex_lambda.stream.rules_registry import RulesRegistry
from tests.stream.flavors.source_events import dynamodb_stream_event, kinesis_event

def to_query_request(uow, _):
    return {
        'IndexName': 'DataIndex',
        'KeyConditionExpression': '#data = :data',
        'ExpressionAttributeNames': {
            '#data': 'data',
        },
        'ExpressionAttributeValues': {
            ':data': get(uow, 'event.thing.id'),
        },
        'ConsistentRead': True
    }

def to_get_request(uow, _):
    return {
        'RequestItems': {
            'Things': {
                'Keys': [
                    {
                        'pk': get(uow, 'query_response.entity_id'),
                        'sk': 'thing'
                    }
                ]
            }
        }
    }

def to_update_request(uow, _):
    entity = get(uow, 'batch_get_response.Responses.Things[0]', {})
    return {
        'Key': {
            'pk': get(uow, 'query_response.entity_id'),
            'sk': 'thing',
        },
        **update_expression({
            'last_event_id': get(uow, 'event.id'),
            'name': entity.get('name'),
        })
    }

def to_fallback_update_request(uow, _):
    return {
        'Key': {
            'pk': f"{get(uow, 'query_response.entity_id')}.fallback",
            'sk': 'thing',
        },
        **update_expression({
            'last_event_id': get(uow, 'event.id'),
        })
    }

def test_update_from_collected_event(monkeypatch):
    event = dynamodb_stream_event([
        {
            'keys': {'pk': 'evt-1', 'sk': 'EVENT'},
            'new_image': {
                'sequence_number': '0',
                'ttl': 1551818222,
                'data': 'thing-1',
                'event': {
                    'id': 'evt-1',
                    'type': 'thing-submitted',
                    'timestamp': 1548967022000,
                    'partition_key': 'thing-1',
                    'thing': {
                        'id': 'thing-1',
                    }
                }
            },
        }
    ])
    update_calls = []

    monkeypatch.setattr(Connector, 'query_all', lambda *_: [
        {'entity_id': 'thing-a'},
        {'entity_id': 'needs-fallback'},
    ])
    monkeypatch.setattr(Connector, 'batch_get', lambda _, params: {
        'Responses': {
            'Things': [
                {
                    'pk': get(params, 'RequestItems.Things.Keys[0].pk'),
                    'name': 'Thing One',
                }
            ]
        }
    })

    def _update(_, params):
        update_calls.append(params)
        if get(params, 'Key.pk') == 'needs-fallback':
            return {}
        return {'result': get(params, 'Key.pk')}

    monkeypatch.setattr(Connector, 'update', _update)

    collected = []

    def _on_next(_, uow):
        collected.append(uow)

    @dynamodb_source(
        RulesRegistry().registry(
            Update({
                'id': 'upd1',
                'event_type': 'thing-submitted',
                'table_name': 'Things',
                'to_query_request': to_query_request,
                'to_get_request': to_get_request,
                'to_update_request': to_update_request,
                'to_fallback_update_request': to_fallback_update_request,
            })
        ),
        concurrency=False,
        on_next=_on_next,
    )
    def handler(_event, _context):
        return {"statusCode": 200}

    handler(event, None)

    expect(len(collected)).to(equal(2))
    expect(get(collected, '[0].event.type')).to(equal('thing-submitted'))
    expect(get(collected, '[0].query_response')).to(equal({'entity_id': 'thing-a'}))
    expect(get(collected, '[0].batch_get_response.Responses.Things[0].pk')).to(
        equal('thing-a')
    )
    expect(get(collected, '[0].update_response')).to(equal({'result': 'thing-a'}))
    expect(get(collected, '[1].update_response')).to(
        equal({'result': 'needs-fallback.fallback'})
    )
    expect([get(c, 'Key.pk') for c in update_calls]).to(equal([
        'thing-a',
        'needs-fallback',
        'needs-fallback.fallback',
    ]))

def test_update_without_query(monkeypatch):
    event = kinesis_event([
        {
            'type': 'thing-direct',
            'timestamp': 1548967022000,
            'thing': {
                'id': 'thing-1',
                'name': 'Thing One',
            },
        }
    ])

    monkeypatch.setattr(Connector, 'update', lambda *_: {'result': 'OK'})

    collected = []

    def _on_next(_, uow):
        collected.append(uow)

    @kinesis_source(
        RulesRegistry().registry(
            Update({
                'id': 'upd-direct',
                'event_type': 'thing-direct',
                'table_name': 'Things',
                'to_update_request': lambda uow, _: {
                    'Key': {
                        'pk': get(uow, 'event.thing.id'),
                        'sk': 'thing',
                    },
                    **update_expression({
                        'name': get(uow, 'event.thing.name')
                    })
                },
            })
        ),
        concurrency=False,
        on_next=_on_next,
    )
    def handler(_event, _context):
        return {"statusCode": 200}

    handler(event, None)

    expect(len(collected)).to(equal(1))
    expect(get(collected, '[0].update_request.Key.pk')).to(equal('thing-1'))
    expect(get(collected, '[0].update_response')).to(equal({'result': 'OK'}))
