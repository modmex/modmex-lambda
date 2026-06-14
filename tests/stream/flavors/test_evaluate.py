from pydash import get, find
from expects import equal, expect
from modmex_lambda.connectors.dynamodb import Connector
from modmex_lambda.stream.flavors.evaluate import Evaluate
from modmex_lambda.stream.sources.dynamodb import dynamodb_source
from modmex_lambda.stream.rules_registry import RulesRegistry
from tests.stream.flavors.source_events import dynamodb_stream_event

PIPELINES = [
  Evaluate({
    'id': 'eval1-basic-emit',
    'event_type': 'e1',
    'emit': 'e111',
  }),
  Evaluate({
    'id': 'eval2-single-emit',
    'event_type': 'e2',
    'emit': lambda uow,_,template: {
        **template,
        'type':  'e222',
        'thing': get(uow, 'event.thing')
    }
  }),
  Evaluate({
    'id': 'eval3-multi-emit',
    'event_type': 'e3',
    'emit': lambda uow, _, template : [
      {
        **template,
        'id': f"{template['id']}.1",
        'type': 'e333.1',
        'thing': get(uow, 'event.thing'),
      },
      {
        **template,
        'id': f"{template['id']}.2",
        'type': 'e333.2',
        'thing': get(uow, 'event.thing'),
      }
    ]
  }),
  Evaluate({
    'id': 'eval4',
    'event_type': 'e4',
    'expression': lambda _: True,
    'emit': 'e444',
  }),
  Evaluate({
    'id': 'eval5',
    'event_type': 'e5',
    'expression': lambda _ : [{
      'id': '51',
      'type': 'e51',
      'timestamp': 1548967022000,
    },
    {
      'id': '52',
      'type': 'e52',
      'timestamp': 1548967022000,
    }],
    'emit': 'e555',
  }),
  Evaluate({
    'id': 'eval6',
    'event_type': 'e6',
    'expression': lambda uow: find(uow['correlated'], lambda e: e['type'] == 'e66'),
    'emit': 'e666',
  }),
  Evaluate({
    'id': 'eval7',
    'event_type': 'e7',
    'correlation_key_suffix': 'seven',
    'expression': lambda _ : True,
    'emit': 'e777',
  })
]

def collected_event_record(raw_event_id, event_type, partition_key, thing, data=None):
    return {
        'keys': {'pk': raw_event_id, 'sk': 'EVENT'},
        'new_image': {
            'pk': raw_event_id,
            'sk': 'EVENT',
            'discriminator': 'EVENT',
            'sequence_number': '0',
            'ttl': 1551818222,
            'data': data or partition_key,
            'event': {
                'id': raw_event_id,
                'type': event_type,
                'timestamp': 1548967022000,
                'partition_key': partition_key,
                'thing': thing,
            },
        },
    }

def correlation_record(pk, raw_event_id, event_type, partition_key, thing=None, suffix=None):
    raw_event = {
        'id': raw_event_id,
        'type': event_type,
        'timestamp': 1548967022000,
        'partition_key': partition_key,
    }
    if thing:
        raw_event['thing'] = thing

    return {
        'keys': {'pk': pk, 'sk': raw_event_id},
        'new_image': {
            'pk': pk,
            'sequence_number': '0',
            'ttl': 1551818222,
            'suffix': suffix,
            'discriminator': 'CORREL',
            'event': raw_event,
        },
    }

def test_should_execute_simple_rules(monkeypatch):
    event = dynamodb_stream_event([
        collected_event_record('1', 'e1', '11', {
            "id": "11",
            "name": "Thing One",
            "description": "This is thing one"
        }),
        collected_event_record('2', 'e2', '22', {
            "id": "22",
            "name": "Thing Two",
            "description": "This is thing two"
        }),
        collected_event_record('3', 'e3', '33', {
            "id": "33",
            "name": "Thing Three",
            "description": "This is thing three"
        }),
    ])

    collected = []

    monkeypatch.setattr(Connector, "put", lambda *_: {'result': 'OK'})

    def _on_next(_, uow):
        collected.append(uow)

    @dynamodb_source(
        RulesRegistry().registry(*PIPELINES),
        concurrency=False,
        on_next = _on_next,
    )
    def handler(_event, _context):
        return {"statusCode": 200}

    handler(event, None)

    expect(len(collected)).to(equal(4))
    expect(get(collected, '[0].pipeline')).to(equal('eval1-basic-emit'))
    expect(get(collected, '[0].event.type')).to(equal('e1'))
    expect(get(collected, '[0].meta')).to(equal({
      'id': '0',
      'pk': '1',
      'data': '11',
      'sequence_number': '0',
      'ttl': 1551818222,
      'expire': None,
      'correlation_key': '11',
      'correlation': False,
      'suffix': None
    }))
    expect(get(collected, '[0].emit')).to(equal({
        "id": "0.eval1-basic-emit",
        "type": "e111",
        "timestamp": 1548967022000,
        "thing": {
            "id": "11",
            "name": "Thing One",
            "description": "This is thing one"
        },
        "partition_key": "11",
        "tags": {
            'app': 'undefined',
            "account": "undefined",
            "region": "undefined",
            "stage": "test",
            "source": "undefined",
            "functionname": "undefined",
            "pipeline": "eval1-basic-emit",
            "skip": True
        },
        "triggers": [
            {
                "id": "1",
                "type": "e1",
                "timestamp": 1548967022000
            }
        ]
    }))

    expect(len(collected)).to(equal(4))
    expect(get(collected, '[1].pipeline')).to(equal('eval2-single-emit'))
    expect(get(collected, '[1].event.type')).to(equal('e2'))
    expect(get(collected, '[1].emit')).to(equal({
      "id": "1.eval2-single-emit",
      "type": "e222",
      "timestamp": 1548967022000,
      "partition_key": "22",
      "thing": {
        "id": "22",
        "name": "Thing Two",
        "description": "This is thing two"
      },
      "tags": {
            "app": "undefined",
            "account": "undefined",
            "region": "undefined",
            "stage": "test",
            "source": "undefined",
            "functionname": "undefined",
            "pipeline": "eval2-single-emit",
            "skip": True
        },
        "triggers": [
            {
            "id": "2",
            "type": "e2",
            "timestamp": 1548967022000
            }
        ]
    }))

    expect(len(collected)).to(equal(4))
    expect(get(collected, '[2].pipeline')).to(equal('eval3-multi-emit'))
    expect(get(collected, '[2].event.type')).to(equal('e3'))
    expect(get(collected, '[2].emit')).to(equal({
      "id": "2.eval3-multi-emit.1",
      "type": "e333.1",
      "timestamp": 1548967022000,
      "partition_key": "33",
      "thing": {
        "id": "33",
        "name": "Thing Three",
        "description": "This is thing three"
      },
      "tags": {
          'app': 'undefined',
        "account": "undefined",
        "region": "undefined",
        "stage": "test",
        "source": "undefined",
        "functionname": "undefined",
        "pipeline": "eval3-multi-emit",
        "skip": True
      },
      "triggers": [
        {
          "id": "3",
          "type": "e3",
          "timestamp": 1548967022000
        }
      ]
    }))

    expect(get(collected, '[3].emit.id')).to(equal('2.eval3-multi-emit.2'))
    expect(get(collected, '[3].emit.type')).to(equal('e333.2'))

def test_should_execute_complex_rules(monkeypatch):
    print("test_should_execute_complex_rules")

    def _calls_fake(_, input_params):
        ck = get(input_params, 'ExpressionAttributeValues.:data')
        resp = {
            '44': [{'event': {'id': '4', 'type': 'e4', 'timestamp': 1548967022000}}],
            '55': [{'event': {'id': '5', 'type': 'e5', 'timestamp': 1548967022000}}]
        }
        return resp[ck]
    monkeypatch.setattr(Connector, 'query_all', _calls_fake)
    # pylint: disable=duplicate-code
    event = dynamodb_stream_event([
        collected_event_record('4', 'e4', '44', {
            "id": "44",
            "name": "Thing Four",
            "description": "This is thing four"
        }),
        collected_event_record('5', 'e5', '55', {
            "id": "55",
            "name": "Thing Five",
            "description": "This is thing five"
        }),
    ])

    collected = []

    def _on_next(_, uow):
        collected.append(uow)

    @dynamodb_source(
        RulesRegistry().registry(*PIPELINES),
        concurrency=False,
        on_next = _on_next,
    )
    def handler(_event, _context):
        return {"statusCode": 200}

    handler(event, None)

    expect(len(collected)).to(equal(2))
    expect(get(collected, '[0].pipeline')).to(equal('eval4'))
    expect(get(collected, '[0].event.type')).to(equal('e4'))
    expect(get(collected, '[0].meta')).to(equal({
        'id': '0',
        'pk': '4',
        'data': '44',
        'sequence_number': '0',
        'ttl': 1551818222,
        'expire': None,
        'correlation_key': '44',
        'correlation': False,
        'suffix': None
    }))
    expect(get(collected, '[0].query_request')).to(equal({
        "IndexName": "DataIndex",
        "KeyConditionExpression": "#data = :data",
        "ExpressionAttributeNames": {
            "#data": "data"
        },
        "ExpressionAttributeValues": {
            ":data": "44"
        }
    }))
    expect(get(collected, '[0].correlated')).to(equal([
        { 'id': '4', 'type': 'e4', 'timestamp': 1548967022000 },
    ]))
    expect(get(collected, '[0].emit')).to(equal({
        "id": "0.eval4",
        "type": "e444",
        "timestamp": 1548967022000,
        "partition_key": "44",
        "thing": {
            "id": "44",
            "name": "Thing Four",
            "description": "This is thing four"
        },
        "tags": {
            'app': 'undefined',
            "account": "undefined",
            "region": "undefined",
            "stage": "test",
            "source": "undefined",
            "functionname": "undefined",
            "pipeline": "eval4",
            "skip": True
        },
        "triggers": [
            {
                "id": "4",
                "type": "e4",
                "timestamp": 1548967022000
            }
        ]
    }))

    expect(get(collected, '[1].pipeline')).to(equal('eval5'))
    expect(get(collected, '[1].event.type')).to(equal('e5'))
    expect(get(collected, '[1].emit.triggers')).to(equal([
        {
            "id": "51",
            "type": "e51",
            "timestamp": 1548967022000
        },
        {
            "id": "52",
            "type": "e52",
            "timestamp": 1548967022000
        }
    ]))

def test_should_execute_correlation_rules(monkeypatch):
    def _calls_fake(_, input_params):
        ck = get(input_params, 'ExpressionAttributeValues.:pk')
        resp = {
            "66": [
                {
                    "event": {
                        "id": "66",
                        "type": "e66",
                        "timestamp": 1548967022000
                    }
                }
            ],
            "77.seven": [
                {
                    "event": {
                        "id": "77",
                        "type": "e77",
                        "timestamp": 1548967022000
                    }
                }
            ]
        }
        return resp[ck]

    monkeypatch.setattr(Connector, 'query_all', _calls_fake)

    event = dynamodb_stream_event([
        correlation_record('66', '6', 'e6', '66', {
            "id": "66",
            "name": "Thing Six",
            "description": "This is thing six"
        }),
        correlation_record('77.seven', '7', 'e7', '77', {
            "id": "77",
            "name": "Thing Seven",
            "description": "This is thing seven"
        }, suffix='seven'),
        correlation_record('77', '7', 'e7', '77', suffix='undefined'),
        correlation_record('77.seventy', '7', 'e7', '77', suffix='seventy'),
    ])

    collected = []

    def _on_next(_, uow):
        collected.append(uow)

    @dynamodb_source(
        RulesRegistry().registry(*PIPELINES),
        concurrency=False,
        on_next = _on_next,
    )
    def handler(_event, _context):
        return {"statusCode": 200}

    handler(event, None)

    expect(len(collected)).to(equal(2))
    expect(get(collected, '[0].pipeline')).to(equal('eval6'))
    expect(get(collected, '[0].event.type')).to(equal('e6'))
    expect(get(collected, '[0].meta')).to(equal({
        "id": "0",
        "pk": "66",
        "data": None,
        "sequence_number": "0",
        "ttl": 1551818222,
        "expire": None,
        "correlation_key": "66",
        "correlation": True,
        "suffix": None
    }))
    expect(get(collected, '[0].query_request')).to(equal({
        "KeyConditionExpression": "#pk = :pk",
        "ExpressionAttributeNames": {
            "#pk": "pk"
        },
        "ExpressionAttributeValues": {
            ":pk": "66"
        },
        "ConsistentRead": True
    }))
    expect(get(collected, '[0].correlated')).to(equal([
        { 'id': '66', 'type': 'e66', 'timestamp': 1548967022000 },
    ]))
    expect(get(collected, '[0].emit')).to(equal({
        "id": "0.eval6",
        "type": "e666",
        "timestamp": 1548967022000,
        "partition_key": "66",
        "thing": {
            "id": "66",
            "name": "Thing Six",
            "description": "This is thing six"
        },
        "tags": {
            "app": "undefined",
            "account": "undefined",
            "region": "undefined",
            "stage": "test",
            "source": "undefined",
            "functionname": "undefined",
            "pipeline": "eval6",
            "skip": True
        },
        "triggers": [
            {
            "id": "66",
            "type": "e66",
            "timestamp": 1548967022000
            }
        ]
    }))

    expect(get(collected, '[1].pipeline')).to(equal('eval7'))
    expect(get(collected, '[1].event.type')).to(equal('e7'))
    expect(get(collected, '[1].meta')).to(equal({
        "id": "1",
        "pk": "77.seven",
        "data": None,
        "sequence_number": "0",
        "ttl": 1551818222,
        "expire": None,
        "correlation_key": "77.seven",
        "correlation": True,
        "suffix": "seven"
    }))
    expect(get(collected, '[1].query_request')).to(equal({
        "KeyConditionExpression": "#pk = :pk",
        "ExpressionAttributeNames": {
            "#pk": "pk"
        },
        "ExpressionAttributeValues": {
            ":pk": "77.seven"
        },
        "ConsistentRead": True
    }))
    expect(get(collected, '[1].correlated')).to(equal([
        { 'id': '77', 'type': 'e77', 'timestamp': 1548967022000 },
    ]))
    expect(get(collected, '[1].emit.triggers')).to(equal([
       {
            'id': '7',
            'type': 'e7',
            'timestamp': 1548967022000,
        }
    ]))
