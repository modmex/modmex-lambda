import json
from decimal import Decimal
from typing import Optional

from reactivex import Observable, create

from modmex_lambda.connectors.idynamodb import IDynamodbConnector
from modmex_lambda.stream.operators.ioperator import IOperator
from modmex_lambda.stream.utils.faults import faulty
from modmex_lambda.stream.utils.json_encoder import JSONEncoder
from modmex_lambda.stream.utils.operators import try_map
from modmex_lambda.stream.utils.retry import DEFAULT_RETRY_CONFIG


class UpdateDynamoDB(IOperator):
    def __init__(
        self,
        connector: IDynamodbConnector,
        *,
        table_name: Optional[str] = None,
        update_request_field='update_request',
        update_response_field='update_response',
        fallback_update_request_field='fallback_update_request',
    ) -> None:
        self.connector = connector
        if table_name:
            self.connector.table_name = table_name
        self.update_request_field = update_request_field
        self.update_response_field = update_response_field
        self.fallback_update_request_field = fallback_update_request_field

    def __call__(self, source: Observable) -> Observable:
        return source.pipe(try_map(faulty(self.invoke)))

    def invoke(self, uow):
        if not uow.get(self.update_request_field):
            return uow
        update_response = self.connector.update(
            self._to_dynamodb_request(uow[self.update_request_field])
        )
        if update_response == {} and uow.get(self.fallback_update_request_field):
            update_response = self.connector.update(
                self._to_dynamodb_request(uow[self.fallback_update_request_field])
            )
        return {
            **uow,
            self.update_response_field: update_response
        }

    @staticmethod
    def _to_dynamodb_request(request):
        return json.loads(
            json.dumps(request, cls=JSONEncoder),
            parse_float=Decimal
        )


class PutDynamoDB(IOperator):
    def __init__(
        self,
        connector: IDynamodbConnector,
        *,
        table_name: Optional[str] = None,
        put_request_field='put_request',
    ) -> None:
        self.connector = connector
        if table_name:
            self.connector.table_name = table_name
        self.put_request_field = put_request_field

    def __call__(self, source: Observable) -> Observable:
        return source.pipe(try_map(faulty(self.invoke)))

    def invoke(self, uow):
        return {
            **uow,
            'put_response': self.connector.put(
                UpdateDynamoDB._to_dynamodb_request(uow[self.put_request_field])
            )
        }


class BatchGetDynamoDB(IOperator):
    def __init__(
        self,
        connector: IDynamodbConnector,
        *,
        table_name: Optional[str] = None,
        batch_get_request_field='batch_get_request',
        batch_get_response_field='batch_get_response',
        retry_config=DEFAULT_RETRY_CONFIG,
    ) -> None:
        self.connector = connector
        if table_name:
            self.connector.table_name = table_name
        self.connector.retry_config = retry_config
        self.batch_get_request_field = batch_get_request_field
        self.batch_get_response_field = batch_get_response_field

    def __call__(self, source: Observable) -> Observable:
        return source.pipe(try_map(faulty(self.invoke)))

    def invoke(self, uow):
        if not uow.get(self.batch_get_request_field):
            return uow
        return {
            **uow,
            self.batch_get_response_field: self.connector.batch_get(
                uow[self.batch_get_request_field]
            )
        }


class QueryDynamoDB(IOperator):
    def __init__(
        self,
        connector: IDynamodbConnector,
        *,
        table_name: Optional[str] = None,
        query_request_field='query_request',
        query_response_field='query_response',
    ) -> None:
        self.connector = connector
        if table_name:
            self.connector.table_name = table_name
        self.query_request_field = query_request_field
        self.query_response_field = query_response_field

    def __call__(self, source: Observable) -> Observable:
        return source.pipe(try_map(faulty(self.invoke)))

    def invoke(self, uow):
        if not uow.get(self.query_request_field):
            return uow
        return {
            **uow,
            self.query_response_field: self.connector.query_all(
                uow.get(self.query_request_field)
            )
        }


class ScanSplitDynamoDB(IOperator):
    def __init__(
        self,
        connector: IDynamodbConnector,
        *,
        table_name: Optional[str] = None,
        scan_request_field='scan_request',
        scan_response_field='scan_response',
    ) -> None:
        self.connector = connector
        if table_name:
            self.connector.table_name = table_name
        self.scan_request_field = scan_request_field
        self.scan_response_field = scan_response_field

    def __call__(self, source: Observable) -> Observable:
        def subscribe(observer, scheduler=None):
            def on_next(uow):
                try:
                    if not uow.get(self.scan_request_field):
                        observer.on_next(uow)
                        return

                    self._scan(uow, observer)
                except Exception as err:  # pylint: disable=broad-except
                    observer.on_error(err)

            return source.subscribe(
                on_next,
                observer.on_error,
                observer.on_completed,
                scheduler=scheduler,
            )

        return create(subscribe)

    def _scan(self, uow, observer):
        request = uow[self.scan_request_field]
        cursor = request.get('ExclusiveStartKey')
        items_count = 0

        while True:
            params = {
                **request,
                'ExclusiveStartKey': cursor,
            }
            response = self.connector.scan(
                omit_none(params)
            )
            items = response.get('Items', [])
            items_count += len(items)
            last_evaluated_key = response.get('LastEvaluatedKey')

            for item in items:
                observer.on_next({
                    **uow,
                    self.scan_request_field: omit_none(params),
                    self.scan_response_field: {
                        **{
                            key: value
                            for key, value in response.items()
                            if key not in ['Items']
                        },
                        'LastEvaluatedKey': last_evaluated_key,
                        'Item': item,
                    },
                })

            if last_evaluated_key and (
                not params.get('Limit') or items_count < params.get('Limit')
            ):
                cursor = last_evaluated_key
                continue
            break


class QuerySplitDynamoDB(IOperator):
    def __init__(
        self,
        connector: IDynamodbConnector,
        *,
        table_name: Optional[str] = None,
        query_split_request_field='query_split_request',
        query_split_response_field='query_split_response',
    ) -> None:
        self.connector = connector
        if table_name:
            self.connector.table_name = table_name
        self.query_split_request_field = query_split_request_field
        self.query_split_response_field = query_split_response_field

    def __call__(self, source: Observable) -> Observable:
        def subscribe(observer, scheduler=None):
            def on_next(uow):
                try:
                    if not uow.get(self.query_split_request_field):
                        observer.on_next(uow)
                        return

                    self._query(uow, observer)
                except Exception as err:  # pylint: disable=broad-except
                    observer.on_error(err)

            return source.subscribe(
                on_next,
                observer.on_error,
                observer.on_completed,
                scheduler=scheduler,
            )

        return create(subscribe)

    def _query(self, uow, observer):
        request = uow[self.query_split_request_field]
        cursor = request.get('ExclusiveStartKey')
        items_count = 0

        while True:
            params = {
                **request,
                'ExclusiveStartKey': cursor,
            }
            response = self.connector.query_page(
                omit_none(params)
            )
            items = response.get('Items', [])
            items_count += len(items)
            last_evaluated_key = response.get('LastEvaluatedKey')

            for item in items:
                observer.on_next({
                    **uow,
                    self.query_split_request_field: omit_none(params),
                    self.query_split_response_field: {
                        **{
                            key: value
                            for key, value in response.items()
                            if key not in ['Items']
                        },
                        'LastEvaluatedKey': last_evaluated_key,
                        'Item': item,
                    },
                })

            if last_evaluated_key and (
                not params.get('Limit') or items_count < params.get('Limit')
            ):
                cursor = last_evaluated_key
                continue
            break


class DynamoDBOps:
    def __init__(self, connector: IDynamodbConnector) -> None:
        self.connector = connector

    def update(
        self,
        *,
        table_name: Optional[str] = None,
        update_request_field='update_request',
        update_response_field='update_response',
        fallback_update_request_field='fallback_update_request',
    ) -> UpdateDynamoDB:
        return UpdateDynamoDB(
            self.connector,
            table_name=table_name,
            update_request_field=update_request_field,
            update_response_field=update_response_field,
            fallback_update_request_field=fallback_update_request_field,
        )

    def put(
        self,
        *,
        table_name: Optional[str] = None,
        put_request_field='put_request',
    ) -> PutDynamoDB:
        return PutDynamoDB(
            self.connector,
            table_name=table_name,
            put_request_field=put_request_field,
        )

    def batch_get(
        self,
        *,
        table_name: Optional[str] = None,
        batch_get_request_field='batch_get_request',
        batch_get_response_field='batch_get_response',
        retry_config=DEFAULT_RETRY_CONFIG,
    ) -> BatchGetDynamoDB:
        return BatchGetDynamoDB(
            self.connector,
            table_name=table_name,
            batch_get_request_field=batch_get_request_field,
            batch_get_response_field=batch_get_response_field,
            retry_config=retry_config,
        )

    def query(
        self,
        *,
        table_name: Optional[str] = None,
        query_request_field='query_request',
        query_response_field='query_response',
    ) -> QueryDynamoDB:
        return QueryDynamoDB(
            self.connector,
            table_name=table_name,
            query_request_field=query_request_field,
            query_response_field=query_response_field,
        )

    def scan_split(
        self,
        *,
        table_name: Optional[str] = None,
        scan_request_field='scan_request',
        scan_response_field='scan_response',
    ) -> ScanSplitDynamoDB:
        return ScanSplitDynamoDB(
            self.connector,
            table_name=table_name,
            scan_request_field=scan_request_field,
            scan_response_field=scan_response_field,
        )

    def query_split(
        self,
        *,
        table_name: Optional[str] = None,
        query_split_request_field='query_split_request',
        query_split_response_field='query_split_response',
    ) -> QuerySplitDynamoDB:
        return QuerySplitDynamoDB(
            self.connector,
            table_name=table_name,
            query_split_request_field=query_split_request_field,
            query_split_response_field=query_split_response_field,
        )


def omit_none(values):
    return {
        key: value
        for key, value in values.items()
        if value is not None
    }
