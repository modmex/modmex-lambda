from threading import current_thread
from expects import equal, expect
from reactivex import from_list, of
from modmex_lambda.stream.operators.dynamodb import DynamoDBOps
from modmex_lambda.stream.utils import faults as faults_module
from modmex_lambda.stream.utils.faults import faulty
from modmex_lambda.stream.utils.operators import try_filter, try_map, split_buffer, tap

def map_except(_except):
    def wrapper(i):
        if i['key'] == _except:
            raise Exception(f"The value {_except} is not allowed")
        return i
    return wrapper


def test_try_map():
    print("----test_try_map-----")
    source = of({'key': "Alpha"},
                {'key':"Beta"},
                {'key': "Gamma"},
                {'key': "Delta"},
                {'key': 'Epsilon'}
            )

    composed = source.pipe(
        try_map(lambda x: x),
        try_map(lambda x: x),
        try_map(faulty(map_except('Beta'))),
    )
    composed.subscribe(
        on_next=lambda i: print("PROCESS 2: {0} {1}".format(current_thread().name, i)),
        on_completed=lambda: print("Task 2 complete")
    )


def test_split_buffer():
    collected = []

    from_list([ # pylint: disable=E1102
        [1, 2],
        [3],
    ]).pipe(
        split_buffer(),
    ).subscribe(
        on_next=lambda value: collected.append(value)
    )

    expect(collected).to(equal([1, 2, 3]))


def test_tap_keeps_original_value():
    calls = []
    collected = []

    from_list([1]).pipe( # pylint: disable=E1102
        tap(lambda value: calls.append(value)),
    ).subscribe(
        on_next=lambda value: collected.append(value)
    )

    expect(calls).to(equal([1]))
    expect(collected).to(equal([1]))


def test_try_filter():
    collected = []

    from_list([1, 2, 3]).pipe( # pylint: disable=E1102
        try_filter(lambda value: value > 1),
    ).subscribe(
        on_next=lambda value: collected.append(value)
    )

    expect(collected).to(equal([2, 3]))


def test_try_map_and_filter_forward_faults(monkeypatch):
    errors = []
    monkeypatch.setattr(faults_module, 'the_faults', [])

    from_list([ # pylint: disable=E1102
        {
            'pipeline': 'test',
            'event': {
                'id': 'evt-1',
            },
        },
    ]).pipe(
        try_map(faulty(lambda _: (_ for _ in ()).throw(Exception('map failed')))),
        try_filter(lambda _: (_ for _ in ()).throw(Exception('filter failed'))),
    ).subscribe(
        on_error=lambda error: errors.append(error)
    )

    expect(errors).to(equal([]))
    expect(len(faults_module.the_faults)).to(equal(1))
    expect(faults_module.the_faults[0]['err']['message']).to(equal('map failed'))


class FakeDynamoConnector:
    def __init__(self):
        self.table_name = None
        self.scan_calls = []
        self.query_calls = []

    def scan(self, params):
        self.scan_calls.append(params)
        if len(self.scan_calls) == 1:
            return {
                'Items': [{'id': 'scan-1'}],
                'Count': 1,
                'LastEvaluatedKey': {'pk': 'scan-cursor'},
            }
        return {
            'Items': [{'id': 'scan-2'}],
            'Count': 1,
        }

    def query_page(self, params):
        self.query_calls.append(params)
        if len(self.query_calls) == 1:
            return {
                'Items': [{'id': 'query-1'}],
                'Count': 1,
                'LastEvaluatedKey': {'pk': 'query-cursor'},
            }
        return {
            'Items': [{'id': 'query-2'}],
            'Count': 1,
        }


def test_dynamodb_split_operators_paginate_and_emit_each_item():
    connector = FakeDynamoConnector()
    ops = DynamoDBOps(connector)
    collected = []

    from_list([ # pylint: disable=E1102
        {
            'scan_request': {
                'TableName': 'Things',
            },
            'query_split_request': {
                'TableName': 'Things',
                'KeyConditionExpression': '#pk = :pk',
            },
        },
    ]).pipe(
        ops.scan_split(table_name='Things'),
        ops.query_split(table_name='Things'),
    ).subscribe(
        on_next=lambda value: collected.append(value)
    )

    expect(connector.table_name).to(equal('Things'))
    expect(connector.scan_calls).to(equal([
        {'TableName': 'Things'},
        {'TableName': 'Things', 'ExclusiveStartKey': {'pk': 'scan-cursor'}},
    ]))
    expect(connector.query_calls).to(equal([
        {'TableName': 'Things', 'KeyConditionExpression': '#pk = :pk'},
        {'TableName': 'Things', 'KeyConditionExpression': '#pk = :pk', 'ExclusiveStartKey': {'pk': 'query-cursor'}},
        {'TableName': 'Things', 'KeyConditionExpression': '#pk = :pk'},
    ]))
    expect([item['scan_response']['Item']['id'] for item in collected]).to(equal([
        'scan-1',
        'scan-1',
        'scan-2',
    ]))
    expect([item['query_split_response']['Item']['id'] for item in collected]).to(equal([
        'query-1',
        'query-2',
        'query-2',
    ]))


def test_dynamodb_split_operators_pass_through_without_requests():
    connector = FakeDynamoConnector()
    collected = []

    from_list([{'id': 'uow-1'}]).pipe( # pylint: disable=E1102
        DynamoDBOps(connector).scan_split(),
        DynamoDBOps(connector).query_split(),
    ).subscribe(
        on_next=lambda value: collected.append(value)
    )

    expect(collected).to(equal([{'id': 'uow-1'}]))
    expect(connector.scan_calls).to(equal([]))
    expect(connector.query_calls).to(equal([]))
