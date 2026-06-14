import os
from pydash import get
from expects import equal, expect
from modmex_lambda.stream.flavors.correlate import Correlate
from modmex_lambda.connectors.dynamodb import Connector
from modmex_lambda.stream.sources.dynamodb import dynamodb_source
from modmex_lambda.stream.rules_registry import RulesRegistry
from tests.stream.flavors.source_events import dynamodb_stream_event

PIPELINES = [
    Correlate({
        'id': 'crl1',
        'event_type': 'c1',
        'correlation_key': 'thing.id',
    }),
    Correlate({
        'id': 'crl2',
        'event_type': 'c1',
        'correlation_key': 'thing.id',
        'correlation_key_suffix': 'x',
        'ttl': 11,
    }),
    Correlate({
        'id': 'crl3',
        'event_type': 'c3',
        'correlation_key': lambda uow: '|'.join([
            get(uow, 'event.thing.group'),
            get(uow, 'event.thing.category')
        ]),
        'expire': True
    })
]

def test_correlate(monkeypatch):
    event = dynamodb_stream_event([
        {
            "keys": {"pk": "1", "sk": "EVENT"},
            "new_image": {
                "sequence_number": "0",
                "ttl": 1551818222,
                "data": "1",
                "event": {
                    "id": "1",
                    "type": "c1",
                    "timestamp": 1548967022000,
                    "partition_key": "11",
                    "thing": {
                        "id": "11",
                        "name": "Thing One",
                        "description": "This is thing one"
                    }
                },
            }
        },
        {
            "keys": {"pk": "3", "sk": "EVENT"},
            "new_image": {
                "sequence_number": "0",
                "ttl": 1551818222,
                "data": "3",
                "event": {
                    "id": "3",
                    "type": "c3",
                    "timestamp": 1548967022000,
                    "partition_key": "33",
                    "thing": {
                        "id": "33",
                        "name": "Thing Three",
                        "description": "This is thing three",
                        "group": "A",
                        "category": "B"
                    }
                },
            }
        }
    ])

    monkeypatch.setattr(Connector, "put", lambda *_: {'result': 'OK'})

    collected  = []

    def _on_next(_, uow):
        collected.append(uow)

    @dynamodb_source(
        RulesRegistry().registry(*PIPELINES),
        concurrency=False,
        on_next = _on_next
    )
    def handler(_event, _context):
        return {"statusCode": 200}

    handler(event, None)

    expect(len(collected)).to(equal(3))
    expect(get(collected, '[0].pipeline')).to(equal('crl1'))
    expect(get(collected, '[0].event.type')).to(equal('c1'))
    expect(get(collected, '[0].put_request')).to(equal({
        "Item": {
            "pk": "11",
            "sk": "1",
            "discriminator": "CORREL",
            "ttl": 1551818222,
            "expire": None,
            "timestamp": 1548967022000,
            "sequence_number": "0",
            "suffix": None,
            "rule_id": "crl1",
            "awsregion": os.getenv('REGION'),
            "event": {
                "id": "1",
                "type": "c1",
                "timestamp": 1548967022000,
                "partition_key": "11",
                "thing": {
                    "id": "11",
                    "name": "Thing One",
                    "description": "This is thing one"
                }
            }
        }
    }))

    expect(get(collected, '[1].pipeline')).to(equal('crl2'))
    expect(get(collected, '[1].event.type')).to(equal('c1'))
    expect(get(collected, '[1].put_request.Item.pk')).to(equal('11.x'))
    expect(get(collected, '[1].put_request.Item.ttl')).to(equal(1549917422))

    expect(get(collected, '[2].pipeline')).to(equal('crl3'))
    expect(get(collected, '[2].event.type')).to(equal('c3'))
    expect(get(collected, '[2].put_request.Item.pk')).to(equal('A|B'))
    expect(get(collected, '[2].put_request.Item.expire')).to(equal(True))
