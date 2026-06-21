import os
from typing import Union
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from modmex_lambda.connectors.dynamodb import Connector
from modmex_lambda.persistence.dynamodb.expressions import (
    pk_condition,
    timestamp_condition,
    update_expression,
)
from modmex_lambda.stream.operators.dynamodb import (
    BatchGetDynamoDB,
    PutDynamoDB,
    QueryDynamoDB,
    UpdateDynamoDB,
)
from modmex_lambda.stream.utils.retry import DEFAULT_RETRY_CONFIG


def serialize_number(number: str) -> Union[float, int]:
    if '.' in number:
        return float(number)
    return int(number)


setattr(TypeDeserializer, '_deserialize_n', lambda _, number: serialize_number(number))

def update_dynamodb(
    table_name=os.getenv('ENTITY_TABLE_NAME') or os.getenv('EVENT_TABLE_NAME'),
    update_request_field='update_request',
    update_response_field='update_response',
    fallback_update_request_field='fallback_update_request',
):
    return UpdateDynamoDB(
        Connector(table_name),
        update_request_field=update_request_field,
        update_response_field=update_response_field,
        fallback_update_request_field=fallback_update_request_field,
    ).invoke


def put_dynamodb(
    table_name= os.getenv('EVENT_TABLE_NAME') or os.getenv('ENTITY_TABLE_NAME'),
    put_request_field= 'put_request'
    ):
    return PutDynamoDB(
        Connector(table_name),
        put_request_field=put_request_field,
    ).invoke


def batch_get_dynamodb( # pylint: disable=W0102
    table_name= os.getenv('EVENT_TABLE_NAME') or os.getenv('ENTITY_TABLE_NAME'),
    batch_get_request_field='batch_get_request',
    batch_get_response_field='batch_get_response',
    retry_config=DEFAULT_RETRY_CONFIG
    ):
    return BatchGetDynamoDB(
        Connector(table_name, retry_config),
        batch_get_request_field=batch_get_request_field,
        batch_get_response_field=batch_get_response_field,
        retry_config=retry_config,
    )


def query_dynamodb(
        table_name= os.getenv('EVENT_TABLE_NAME') or os.getenv('ENTITY_TABLE_NAME'),
        query_request_field = 'query_request',
        query_response_field = 'query_response'
    ):
    connector = Connector(table_name)
    return QueryDynamoDB(
        connector,
        query_request_field=query_request_field,
        query_response_field=query_response_field,
    )


def unmarshall(image):
    # To go from low-level format to python
    deserializer = TypeDeserializer()
    return {k: deserializer.deserialize(v) for k,v in image.items()}

def marshall(obj: dict):
    serializer = TypeSerializer()
    return { k: serializer.serialize(v) for k, v in obj.items()}
