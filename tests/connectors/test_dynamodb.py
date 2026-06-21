from expects import equal, expect, raise_error

from modmex_lambda.connectors import dynamodb
from modmex_lambda.connectors.dynamodb import (
    Connector,
    accumulate,
    unprocessed,
)


class Client:
    def __init__(self):
        self.calls = []
        self.batch_get_responses = []

    def get_item(self, **kwargs):
        self.calls.append(('get_item', kwargs))
        return {
            'Item': {
                'pk': {'S': 'thing-1'},
                'count': {'N': '2'},
            },
        }

    def update_item(self, **kwargs):
        self.calls.append(('update_item', kwargs))
        return {
            'Attributes': {
                'pk': {'S': 'thing-1'},
                'name': {'S': 'Desk'},
            },
        }

    def put_item(self, **kwargs):
        self.calls.append(('put_item', kwargs))
        return {'ok': True}

    def query(self, **kwargs):
        self.calls.append(('query', kwargs))
        return {
            'Items': [
                {
                    'pk': {'S': 'thing-1'},
                    'name': {'S': 'Desk'},
                },
            ],
        }

    def scan(self, **kwargs):
        self.calls.append(('scan', kwargs))
        return {'Items': []}

    def batch_get_item(self, **kwargs):
        self.calls.append(('batch_get_item', kwargs))
        return self.batch_get_responses.pop(0)

    def delete_item(self, **kwargs):
        self.calls.append(('delete_item', kwargs))
        return {'ok': True}

    def batch_write_item(self, **kwargs):
        self.calls.append(('batch_write_item', kwargs))
        return {}


def test_dynamodb_connector_marshalls_get_and_unmarshalls_item():
    client = Client()
    connector = Connector('table', client=client)

    expect(connector.get({'Key': {'pk': 'thing-1', 'sk': 'thing'}})).to(equal({
        'Item': {
            'pk': 'thing-1',
            'count': 2,
        },
    }))
    expect(client.calls).to(equal([
        (
            'get_item',
            {
                'TableName': 'table',
                'Key': {
                    'pk': {'S': 'thing-1'},
                    'sk': {'S': 'thing'},
                },
            },
        ),
    ]))


def test_dynamodb_connector_marshalls_update_expression_values():
    client = Client()
    connector = Connector('table', client=client)

    expect(connector.update({
        'Key': {'pk': 'thing-1', 'sk': 'thing'},
        'ExpressionAttributeValues': {
            ':name': 'Desk',
            ':count': 2,
        },
        'UpdateExpression': 'SET #name = :name, #count = :count',
    })).to(equal({
        'Attributes': {
            'pk': 'thing-1',
            'name': 'Desk',
        },
    }))
    expect(client.calls[0]).to(equal((
        'update_item',
        {
            'TableName': 'table',
            'Key': {
                'pk': {'S': 'thing-1'},
                'sk': {'S': 'thing'},
            },
            'ExpressionAttributeValues': {
                ':name': {'S': 'Desk'},
                ':count': {'N': '2'},
            },
            'UpdateExpression': 'SET #name = :name, #count = :count',
        },
    )))


def test_query_all_pages_results():
    class PagedClient(Client):
        def __init__(self):
            super().__init__()
            self.pages = [
                {
                    'Items': [
                        {
                            'id': {'S': '1'},
                        },
                    ],
                    'LastEvaluatedKey': {
                        'pk': {'S': '1'},
                    },
                },
                {
                    'Items': [
                        {
                            'id': {'S': '2'},
                        },
                    ],
                },
            ]

        def query(self, **kwargs):
            self.calls.append(('query', kwargs))
            return self.pages.pop(0)

    client = PagedClient()
    connector = Connector('table', client=client)
    params = {'KeyConditionExpression': 'pk = :pk'}

    expect(connector.query_all(params)).to(equal([
        {
            'id': '1',
        },
        {
            'id': '2',
        },
    ]))
    expect(client.calls[1][1]['ExclusiveStartKey']).to(equal({
        'pk': {'S': '1'},
    }))


def test_batch_get_retries_unprocessed_keys(monkeypatch):
    client = Client()
    client.batch_get_responses = [
        {
            'Responses': {
                'table': [
                    {
                        'id': {'S': '1'},
                    },
                ],
            },
            'UnprocessedKeys': {
                'table': {
                    'Keys': [
                        {
                            'pk': {'S': '2'},
                        },
                    ],
                },
            },
        },
        {
            'Responses': {
                'table': [
                    {
                        'id': {'S': '2'},
                    },
                ],
            },
        },
    ]
    monkeypatch.setattr(dynamodb, 'wait', lambda *_: None)
    monkeypatch.setattr(dynamodb, 'get_delay', lambda *_: 0)
    connector = Connector('table', retry_config={'max_retries': 2, 'retry_wait': 1}, client=client)

    expect(connector.batch_get({
        'RequestItems': {
            'table': {
                'Keys': [
                    {
                        'pk': '1',
                    },
                    {
                        'pk': '2',
                    },
                ],
            },
        },
    })).to(equal({
        'Responses': {
            'table': [
                {
                    'id': '1',
                },
                {
                    'id': '2',
                },
            ],
        },
        'attempts': [
            {
                'Responses': {
                    'table': [
                        {
                            'id': '1',
                        },
                    ],
                },
                'UnprocessedKeys': {
                    'table': {
                        'Keys': [
                            {
                                'pk': '2',
                            },
                        ],
                    },
                },
            },
            {
                'Responses': {
                    'table': [
                        {
                            'id': '2',
                        },
                    ],
                },
            },
        ],
    }))
    expect(client.calls[1]).to(equal((
        'batch_get_item',
        {
            'RequestItems': {
                'table': {
                    'Keys': [
                        {
                            'pk': {'S': '2'},
                        },
                    ],
                },
            },
        },
    )))


def test_batch_get_raises_after_max_retries(monkeypatch):
    client = Client()
    client.batch_get_responses = [
        {
            'Responses': {},
            'UnprocessedKeys': {
                'table': {
                    'Keys': [
                        {
                            'pk': {'S': '1'},
                        },
                    ],
                },
            },
        },
        {
            'Responses': {},
            'UnprocessedKeys': {
                'table': {
                    'Keys': [
                        {
                            'pk': {'S': '1'},
                        },
                    ],
                },
            },
        },
    ]
    monkeypatch.setattr(dynamodb, 'wait', lambda *_: None)
    monkeypatch.setattr(dynamodb, 'get_delay', lambda *_: 0)
    connector = Connector('table', retry_config={'max_retries': 1, 'retry_wait': 1}, client=client)

    expect(lambda: connector.batch_get({'RequestItems': {'table': {'Keys': []}}})).to(
        raise_error(Exception)
    )


def test_bulk_insert_and_delete():
    client = Client()
    connector = Connector('table', client=client)

    connector.bulk_insert([
        {
            'pk': '1',
        },
    ])
    connector.bulk_delete([
        {
            'pk': '1',
        },
    ])

    expect(client.calls).to(equal([
        (
            'batch_write_item',
            {
                'RequestItems': {
                    'table': [
                        {
                            'PutRequest': {
                                'Item': {
                                    'pk': {'S': '1'},
                                },
                            },
                        },
                    ],
                },
            },
        ),
        (
            'batch_write_item',
            {
                'RequestItems': {
                    'table': [
                        {
                            'DeleteRequest': {
                                'Key': {
                                    'pk': {'S': '1'},
                                },
                            },
                        },
                    ],
                },
            },
        ),
    ]))


def test_unprocessed_and_accumulate_helpers():
    expect(unprocessed({
        'RequestItems': {
            'table': {
                'Keys': [
                    {
                        'pk': '1',
                    },
                ],
            },
        },
    }, {
        'UnprocessedKeys': {
            'table': {
                'Keys': [
                    {
                        'pk': '2',
                    },
                ],
            },
        },
    })).to(equal({
        'RequestItems': {
            'table': {
                'Keys': [
                    {
                        'pk': '2',
                    },
                ],
            },
        },
    }))
    expect(accumulate([
        {
            'Responses': {
                'table': [
                    {
                        'id': '1',
                    },
                ],
            },
        },
    ], {
        'Responses': {
            'table': [
                {
                    'id': '2',
                },
            ],
        },
    })['Responses']['table']).to(equal([
        {
            'id': '1',
        },
        {
            'id': '2',
        },
    ]))
