import json
from expects import expect, equal
from pydash import get
from modmex_lambda.stream.flavors.s3 import S3
from modmex_lambda.stream.sources.kinesis import kinesis_source
from modmex_lambda.stream.utils.time import ttl
from modmex_lambda.stream.rules_registry import RulesRegistry
from tests.stream.flavors.source_events import kinesis_event

DISCRIMINATOR = 'thing'

def to_put_request(uow):
    return {
        'Key': f"{get(uow,'split.id') or get(uow, 'event.thing.id')}/thing",
        'Body': json.dumps({
            **(get(uow,'split') or get(uow, 'event.thing')),
            'discriminator': 'thing',
            'ttl':  ttl(uow['event']['timestamp'], 1),
            'timestamp': uow['event']['timestamp'],
        })
    }

PIPELINES = [
    S3({
        'id': 'mv1',
        'event_type': 'm1',
        'filters': [lambda *_: True],
        'to_s3': to_put_request
    }),
    S3({
        'id': 'other1',
        'event_type': 'x9',
    }),
    S3({
        'id': 'split',
        'event_type': 'split',
        'split_on': 'event.root.things',
        'to_s3': to_put_request
    }),
    S3({
        'id': 'split-custom',
        'event_type': 'split',
        'split_on': lambda uow,_: list(map(
            lambda t: {
                **uow,
                'split': t
            },
            get(uow, 'event.root.things', [])
        )),
        'to_s3': to_put_request
    }),
]

def test_materialize_s3():
    event = kinesis_event([
        {
            'type': 'm1',
            'timestamp': 1548967022000,
            'thing': {
                'id': '1',
                'name': 'Thing One',
                'description': 'This is thing one',
            },
        },
        {
            'type': 'split',
            'timestamp': 1548967022000,
            'root': {
                'things': [
                    {
                        'id': '2',
                        'name': 'Thing One',
                        'description': 'This is thing one',
                    },
                    {
                        'id': '3',
                        'name': 'Thing One',
                        'description': 'This is thing one',
                    }
                ],
            },
        }
    ])

    collected = []

    def _on_next(_, uow):
        collected.append(uow)

    @kinesis_source(
        RulesRegistry().registry(*PIPELINES),
        concurrency=False,
        on_next = _on_next,
    )
    def handler(_event, _context):
        return {"statusCode": 200}

    handler(event, None)
    print(collected)

    expect(len(collected)).to(equal(5))
    expect(collected[0]['pipeline']).to(equal('mv1'))
    expect(collected[0]['event']['type']).to(equal('m1'))
    expect(collected[0]['put_request']).to(equal({
        'Key': '1/thing',
        'Body': json.dumps({
            'id': '1',
            'name': 'Thing One',
            'description': 'This is thing one',
            'discriminator': 'thing',
            'ttl': 1549053422,
            'timestamp': 1548967022000,
        }),
    }))
    expect(collected[1]['put_request']['Key']).to(equal('2/thing'))
    expect(collected[2]['put_request']['Key']).to(equal('3/thing'))
    expect(collected[3]['put_request']['Key']).to(equal('2/thing'))
    expect(collected[4]['put_request']['Key']).to(equal('3/thing'))
