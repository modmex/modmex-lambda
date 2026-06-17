from expects import equal, expect, have_key
from modmex_lambda.stream.flavors.collect import Collect
from modmex_lambda.connectors.dynamodb import Connector
from modmex_lambda.stream.sources.kinesis import kinesis_source
from modmex_lambda.stream.rules_registry import RulesRegistry
from tests.stream.flavors.source_events import kinesis_event

PIPELINES = [
    Collect({
        'id': 'p1',
        'event_type': [
            'thing-created',
        ],
    })
]

def test_collect(monkeypatch):
    print("-----")

    event = kinesis_event([
        {
            'id': 'e1',
            'type': 'thing-created',
            'timestamp': 1548967023,
            'partition_key': '0',
            'thing': {
                "pk": "1",
                "sk": "thing",
                "discriminator": "thing",
                "timestamp": 1548967022000,
                "id": "1",
                "name": "Thing 1",
                "latched": False
            }
        }
    ])

    collected = []
    _errors = []

    monkeypatch.setattr(Connector, "put", lambda *_: {'result': 'OK'})

    def _on_next(_, ouw):
        collected.append(ouw)

    def _on_error(_, error):
        _errors.append(error)

    @kinesis_source(
        RulesRegistry().registry(*PIPELINES),
        concurrency=False,
        on_next = _on_next,
        on_error = _on_error
    )
    def handler(_event, _context):
        return {"statusCode": 200}

    handler(event, None)

    expect(len(collected)).to(equal(1))
    expect(collected[0]).to(have_key('put_request'))
    expect(collected[0]['put_request']).to(equal({
        'Item': {
            'pk': 'e1',
            'sk': 'EVENT',
            'discriminator': 'EVENT',
            'timestamp': 1548967023,
            'awsregion': None,
            'sequence_number': '0',
            'ttl': 4400167,
            'expire': None,
            'data': '0',
            'event': {
                'id': 'e1',
                'type': 'thing-created',
                'timestamp': 1548967023,
                'partition_key': '0',
                'thing': {
                    'pk': '1',
                    'sk': 'thing',
                    'discriminator': 'thing',
                    'timestamp': 1548967022000,
                    'id': '1',
                    'name': 'Thing 1',
                    'latched': False
                }
            }
        }
    }))


def test_collect_correlation_key_and_sequence_number_variants():
    string_rule = Collect({
        'id': 'p1',
        'event_type': ['thing-created'],
        'correlation_key': 'thing.id',
    })
    callable_rule = Collect({
        'id': 'p2',
        'event_type': ['thing-created'],
        'correlation_key': lambda uow: 'callable-key',
        'include_raw': True,
    })
    uow = {
        'event': {
            'id': 'e1',
            'type': 'thing-created',
            'timestamp': 1548967023,
            'partition_key': 'partition-key',
            'thing': {'id': 'thing-1'},
            'raw': {'secret': True},
        },
        'record': {
            'attributes': {
                'SequenceNumber': 'sqs-seq',
            },
        },
    }

    keyed = string_rule._correlation_key(uow)
    callable_keyed = callable_rule._correlation_key(uow)
    put_request = callable_rule._to_put_request(callable_keyed)

    expect(keyed['key']).to(equal('thing-1'))
    expect(callable_keyed['key']).to(equal('callable-key'))
    expect(put_request['put_request']['Item']['sequence_number']).to(equal('sqs-seq'))
    expect(put_request['put_request']['Item']['event']).to(equal(uow['event']))
