from modmex_lambda.connectors.cloudwatch import Connector
from modmex_lambda.stream.operators.cloudwatch import PutMetrics


def put_metrics(
        put_field = 'put_request',
    ):
    return PutMetrics(
        Connector(),
        put_field=put_field,
    )
