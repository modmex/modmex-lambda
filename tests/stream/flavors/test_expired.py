from expects import equal, expect
from pydash import get
from modmex_lambda.stream.flavors.expired import Expired
from modmex_lambda.stream.sources.dynamodb import dynamodb_source
from modmex_lambda.stream.rules_registry import RulesRegistry
from tests.stream.flavors.source_events import dynamodb_stream_event

def test_expired(monkeypatch):
    monkeypatch.setenv('LOG_LEVEL', 'DEBUG')
    event = dynamodb_stream_event([
        {
            'event_name': 'INSERT',
            'keys': {'pk': 'not-expired', 'sk': 'EVENT'},
            'new_image': {'ttl': 1548967022, 'expire': True},
        },
        {
            'event_name': 'REMOVE',
            'timestamp': 1548967023,
            'keys': {'pk': 'no-expire', 'sk': 'EVENT'},
            'old_image': {
                'ttl': 1548967022,
                'event': {
                    'id': 'no-expire',
                    'type': 'thing-created',
                    'timestamp': 1548967022000,
                }
            },
        },
        {
            'event_name': 'REMOVE',
            'timestamp': 1548967021,
            'keys': {'pk': 'before-ttl', 'sk': 'EVENT'},
            'old_image': {
                'ttl': 1548967022,
                'expire': True,
                'event': {
                    'id': 'before-ttl',
                    'type': 'thing-created',
                    'timestamp': 1548967022000,
                }
            },
        },
        {
            'event_name': 'REMOVE',
            'timestamp': 1548967023,
            'keys': {'pk': 'expired', 'sk': 'EVENT'},
            'old_image': {
                'ttl': 1548967022,
                'expire': True,
                'event': {
                    'id': 'expired',
                    'type': 'thing.created',
                    'timestamp': 1548967022345,
                }
            },
        },
        {
            'event_name': 'REMOVE',
            'timestamp': 1548967024,
            'keys': {'pk': 'expired-custom', 'sk': 'EVENT'},
            'old_image': {
                'ttl': 1548967023,
                'expire': 'thing-timeout',
                'event': {
                    'id': 'expired-custom',
                    'type': 'thing-created',
                    'timestamp': 1548967023007,
                }
            },
        },
    ])

    collected = []

    def _on_next(_, uow):
        collected.append(uow)

    @dynamodb_source(
        RulesRegistry().registry(
            Expired({
                'id': 'expired',
            })
        ),
        concurrency=False,
        on_next=_on_next,
    )
    def handler(_event, _context):
        return {"statusCode": 200}

    handler(event, None)

    expect(len(collected)).to(equal(2))
    expect(get(collected, '[0].emit.id')).to(equal('3'))
    expect(get(collected, '[0].emit.type')).to(equal('thing.created.expired'))
    expect(get(collected, '[0].emit.timestamp')).to(equal(1548967022345))
    expect(get(collected, '[0].emit.triggers')).to(equal([
        {
            'id': 'expired',
            'type': 'thing.created',
            'timestamp': 1548967022345
        }
    ]))
    expect(get(collected, '[1].emit.type')).to(equal('thing-timeout'))
    expect(get(collected, '[1].emit.timestamp')).to(equal(1548967023007))
