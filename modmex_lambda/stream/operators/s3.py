from reactivex import Observable, create, empty, just, operators as ops
from pydash import get, omit_by, set_

from modmex_lambda.connectors.is3 import IS3Connector
from modmex_lambda.stream.operators.ioperator import IOperator
from modmex_lambda.stream.utils.faults import faulty
from modmex_lambda.stream.utils.operators import try_map


class PutObjectToS3(IOperator):
    def __init__(self, connector: IS3Connector, *, bucket_name=None, put_request_field='put_request') -> None:
        self.connector = connector
        if bucket_name:
            self.connector.bucket_name = bucket_name
        self.put_request_field = put_request_field

    def __call__(self, source: Observable) -> Observable:
        return source.pipe(ops.map(self.invoke))

    def invoke(self, uow):
        uow['put_response'] = self.connector.put_object(uow[self.put_request_field])
        return uow


class GetObjectFromS3(IOperator):
    def __init__(self, connector: IS3Connector, *, bucket_name=None, get_request_field='get_request', get_response_field='get_response') -> None:
        self.connector = connector
        if bucket_name:
            self.connector.bucket_name = bucket_name
        self.get_request_field = get_request_field
        self.get_response_field = get_response_field

    def __call__(self, source: Observable) -> Observable:
        return source.pipe(try_map(faulty(self.invoke)))

    def invoke(self, uow):
        key = self.connector.get_object(uow[self.get_request_field])
        uow[self.get_response_field] = key['Body'].read()
        return uow


class PageObjectsFromS3(IOperator):
    def __init__(self, connector: IS3Connector, *, bucket_name=None, list_request_field='list_request') -> None:
        self.connector = connector
        if bucket_name:
            self.connector.bucket_name = bucket_name
        self.list_request_field = list_request_field

    def __call__(self, source: Observable) -> Observable:
        def subscribe(observer, _):
            def list_objects(uow):
                params = omit_by(
                    {
                        **uow[self.list_request_field],
                        'ContinuationToken': get(
                            uow,
                            f"{self.list_request_field}.ContinuationToken"
                        )
                    },
                    lambda value: value is None
                )

                res = self.connector.list_objects(params)

                for obj in res.get('Contents', []):
                    observer.on_next({
                        **uow,
                        self.list_request_field: params,
                        'list_response': {
                            'Content': obj
                        }
                    })

                if res['IsTruncated']:
                    return just(set_(
                        uow,
                        f"{self.list_request_field}.ContinuationToken",
                        res['NextContinuationToken']
                    ))
                return empty()

            source.pipe(
                ops.expand(list_objects),
            ).subscribe(
                on_error=observer.on_error
            )

        return create(subscribe)


class S3Ops:
    def __init__(self, connector: IS3Connector) -> None:
        self.connector = connector

    def put_object(
        self,
        *,
        bucket_name=None,
        put_request_field='put_request',
    ) -> PutObjectToS3:
        return PutObjectToS3(
            self.connector,
            bucket_name=bucket_name,
            put_request_field=put_request_field,
        )

    def get_object(
        self,
        *,
        bucket_name=None,
        get_request_field='get_request',
        get_response_field='get_response',
    ) -> GetObjectFromS3:
        return GetObjectFromS3(
            self.connector,
            bucket_name=bucket_name,
            get_request_field=get_request_field,
            get_response_field=get_response_field,
        )

    def page_objects(
        self,
        *,
        bucket_name=None,
        list_request_field='list_request',
    ) -> PageObjectsFromS3:
        return PageObjectsFromS3(
            self.connector,
            bucket_name=bucket_name,
            list_request_field=list_request_field,
        )
