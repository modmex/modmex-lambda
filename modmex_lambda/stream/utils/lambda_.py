from modmex_lambda.connectors.lambda_ import Connector
from modmex_lambda.stream.operators.lambda_ import InvokeLambda


def invoke_lambda(
        invoke_field = 'invoke_request',
    ):
    return InvokeLambda(
        Connector(),
        invoke_field=invoke_field,
    )
