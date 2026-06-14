import os
from modmex_lambda.connectors.s3 import Connector
from modmex_lambda.stream.operators.s3 import (
    GetObjectFromS3,
    PageObjectsFromS3,
    PutObjectToS3,
)



def put_object_to_s3(
    connector: Connector,
    put_request_field='put_request'
):
    return PutObjectToS3(
        connector,
        put_request_field=put_request_field,
    )


def to_get_object_request(uow):
    return {
        **uow,
        'get_request': {
            'Bucket': uow['record']['s3']['bucket']['name'],
            'Key': uow['record']['s3']['object']['key']
        }
    }


def get_object_from_s3(
    bucket_name = os.getenv('BUCKET_NAME'),
    get_request_field='get_request',
    get_response_field='get_response'
    ):
    return GetObjectFromS3(
        Connector(bucket_name),
        bucket_name=bucket_name,
        get_request_field=get_request_field,
        get_response_field=get_response_field,
    )


def page_objects_from_s3(
    bucket_name = os.getenv('BUCKET_NAME'),
    list_request_field = 'list_request',
):
    return PageObjectsFromS3(
        Connector(bucket_name),
        bucket_name=bucket_name,
        list_request_field=list_request_field,
    )
