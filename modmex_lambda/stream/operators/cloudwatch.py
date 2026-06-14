from reactivex import Observable

from modmex_lambda.connectors.icloudwatch import ICloudWatchConnector
from modmex_lambda.stream.operators.ioperator import IOperator
from modmex_lambda.stream.utils.faults import faulty
from modmex_lambda.stream.utils.operators import try_map


class PutMetrics(IOperator):
    def __init__(self, connector: ICloudWatchConnector, *, put_field='put_request') -> None:
        self.connector = connector
        self.put_field = put_field

    def __call__(self, source: Observable) -> Observable:
        return source.pipe(try_map(faulty(self.invoke)))

    def invoke(self, uow):
        return {
            **uow,
            'put_response': self.connector.put(uow[self.put_field])
        }


class CloudWatchOps:
    def __init__(self, connector: ICloudWatchConnector) -> None:
        self.connector = connector

    def put_metrics(self, *, put_field='put_request') -> PutMetrics:
        return PutMetrics(self.connector, put_field=put_field)
