from reactivex import Observable

from modmex_lambda.connectors.ilambda import ILambdaConnector
from modmex_lambda.stream.operators.ioperator import IOperator
from modmex_lambda.stream.utils.faults import faulty
from modmex_lambda.stream.utils.operators import try_map


class InvokeLambda(IOperator):
    def __init__(self, connector: ILambdaConnector, *, invoke_field='invoke_request') -> None:
        self.connector = connector
        self.invoke_field = invoke_field

    def __call__(self, source: Observable) -> Observable:
        return source.pipe(try_map(faulty(self.invoke)))

    def invoke(self, uow):
        return {
            **uow,
            'invoke_response': self.connector.invoke(uow[self.invoke_field])
        }


class LambdaOps:
    def __init__(self, connector: ILambdaConnector) -> None:
        self.connector = connector

    def invoke(self, *, invoke_field='invoke_request') -> InvokeLambda:
        return InvokeLambda(self.connector, invoke_field=invoke_field)
