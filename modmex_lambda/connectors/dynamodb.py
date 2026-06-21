from functools import reduce
from typing import Iterable

from modmex_lambda.connectors.idynamodb import IDynamodbConnector
from modmex_lambda.stream.utils.retry import (
    assert_max_retries,
    DEFAULT_RETRY_CONFIG,
    wait,
    get_delay
)


class Connector(IDynamodbConnector):

    def __init__(self,# pylint: disable=W0102
                 table_name = 'undefined',
                 retry_config = DEFAULT_RETRY_CONFIG,
                 client = None) -> None:
        self.table_name = table_name
        self._client = client
        self.retry_config = retry_config
        self._serializer = None
        self._deserializer = None

    @property
    def client(self):
        if not self._client:
            import boto3
            self._client = boto3.client('dynamodb')
        return self._client

    def get(self, input_params):
        response = self.client.get_item(
            TableName=self.table_name,
            **self._marshall_request(input_params),
        )
        return self._unmarshall_response(response)

    def update(self, input_params):
        response = self.client.update_item(
            TableName=self.table_name,
            **self._marshall_request(input_params),
        )
        return self._unmarshall_response(response)

    def put(self, input_params):
        response = self.client.put_item(
            TableName=self.table_name,
            **self._marshall_request(input_params),
        )
        return self._unmarshall_response(response)

    def query(self, input_params):
        response = self.client.query(
            TableName=self.table_name,
            **self._marshall_request(input_params),
        )
        return self._unmarshall_response(response)

    def query_page(self, input_params):
        return self.query(input_params)

    def scan(self, input_params):
        response = self.client.scan(
            TableName=self.table_name,
            **self._marshall_request(input_params),
        )
        return self._unmarshall_response(response)

    def query_all(self, input_params):
        items = []
        while True:
            result = self.query(input_params)
            items.extend(result.get('Items', []))
            if result.get('LastEvaluatedKey'):
                input_params['ExclusiveStartKey'] = result['LastEvaluatedKey']
            else:
                break
        return items

    def batch_get(self, input_params):
        return self._batch_get(input_params, [])

    def _batch_get(self, params, attempts):
        assert_max_retries(attempts, self.retry_config['max_retries'])
        wait(get_delay(self.retry_config['retry_wait'], len(attempts)))
        response = self.client.batch_get_item(**self._marshall_batch_get_request(params))
        response = self._unmarshall_response(response)
        if response.get('UnprocessedKeys'):
            return self._batch_get(
                unprocessed(params, response),
                [*attempts, response]
            )
        return accumulate(attempts, response)

    def bulk_insert(self, items: Iterable):
        self._batch_write([
            {
                'PutRequest': {
                    'Item': item,
                },
            }
            for item in items
        ])

    def bulk_delete(self, items: Iterable):
        self._batch_write([
            {
                'DeleteRequest': {
                    'Key': key,
                },
            }
            for key in items
        ])

    def _marshall_request(self, params):
        return {
            key: self._marshall_value(key, value)
            for key, value in params.items()
        }

    def _marshall_batch_get_request(self, params):
        return {
            **params,
            'RequestItems': {
                table_name: {
                    **request,
                    'Keys': [
                        self._marshall_item(key)
                        for key in request.get('Keys', [])
                    ],
                }
                for table_name, request in params.get('RequestItems', {}).items()
            },
        }

    def _marshall_value(self, key, value):
        if key in {'Key', 'Item', 'LastEvaluatedKey', 'ExclusiveStartKey'}:
            return self._marshall_item(value)
        if key == 'ExpressionAttributeValues':
            return {
                attr: self.serializer.serialize(attr_value)
                for attr, attr_value in value.items()
            }
        return value

    def _marshall_item(self, item):
        return {
            key: self.serializer.serialize(value)
            for key, value in item.items()
        }

    def _unmarshall_response(self, response):
        return {
            key: self._unmarshall_value(key, value)
            for key, value in response.items()
        }

    def _unmarshall_value(self, key, value):
        if key in {'Item', 'LastEvaluatedKey'}:
            return self._unmarshall_item(value)
        if key == 'Items':
            return [self._unmarshall_item(item) for item in value]
        if key == 'Attributes':
            return self._unmarshall_item(value)
        if key == 'Responses':
            return {
                table_name: [self._unmarshall_item(item) for item in items]
                for table_name, items in value.items()
            }
        if key == 'UnprocessedKeys':
            return {
                table_name: {
                    **request,
                    'Keys': [self._unmarshall_item(item) for item in request.get('Keys', [])],
                }
                for table_name, request in value.items()
            }
        return value

    def _unmarshall_item(self, item):
        return {
            key: self.deserializer.deserialize(value)
            for key, value in item.items()
        }

    @property
    def serializer(self):
        if not self._serializer:
            self._load_dynamodb_types()
        return self._serializer

    @property
    def deserializer(self):
        if not self._deserializer:
            self._load_dynamodb_types()
        return self._deserializer

    def _load_dynamodb_types(self):
        from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
        self._serializer = TypeSerializer()
        self._deserializer = TypeDeserializer()

    def _batch_write(self, requests):
        for index in range(0, len(requests), 25):
            self._batch_write_chunk(requests[index:index + 25], [])

    def _batch_write_chunk(self, requests, attempts):
        if not requests:
            return
        assert_max_retries(attempts, self.retry_config['max_retries'])
        wait(get_delay(self.retry_config['retry_wait'], len(attempts)))
        response = self.client.batch_write_item(
            RequestItems={
                self.table_name: [
                    self._marshall_write_request(request)
                    for request in requests
                ],
            },
        )
        unprocessed_items = response.get('UnprocessedItems', {}).get(self.table_name, [])
        if unprocessed_items:
            self._batch_write_chunk(
                [
                    self._unmarshall_write_request(request)
                    for request in unprocessed_items
                ],
                [*attempts, response],
            )

    def _marshall_write_request(self, request):
        if 'PutRequest' in request:
            return {
                'PutRequest': {
                    'Item': self._marshall_item(request['PutRequest']['Item']),
                },
            }
        return {
            'DeleteRequest': {
                'Key': self._marshall_item(request['DeleteRequest']['Key']),
            },
        }

    def _unmarshall_write_request(self, request):
        if 'PutRequest' in request:
            return {
                'PutRequest': {
                    'Item': self._unmarshall_item(request['PutRequest']['Item']),
                },
            }
        return {
            'DeleteRequest': {
                'Key': self._unmarshall_item(request['DeleteRequest']['Key']),
            },
        }


def unprocessed(params, resp):
    return {
        **params,
        'RequestItems': resp['UnprocessedKeys']
    }

def accumulate(attempts, resp):
    def reducer(a, c):
        return {
            **a,
            'Responses': reduce(
                lambda a2, c2: {
                    **a2,
                    c2: [
                        *a2.get(c2, []),
                        *a['Responses'].get(c2, [])
                    ]
                },
                list(a['Responses']),
                {**c['Responses']}
            ),
            'attempts': [*attempts, resp]
        }

    return reduce(reducer, reversed(attempts), resp)
