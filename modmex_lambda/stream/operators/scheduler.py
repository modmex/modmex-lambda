from reactivex import Observable

from modmex_lambda.connectors.ieventbridge_scheduler import (
    IEventBridgeSchedulerConnector,
)
from modmex_lambda.stream.operators.ioperator import IOperator
from modmex_lambda.stream.utils.faults import faulty
from modmex_lambda.stream.utils.operators import try_map


class SchedulerOps(IOperator):
    """Reactive operator that submits prepared EventBridge schedules."""

    def __init__(
        self,
        connector: IEventBridgeSchedulerConnector,
        *,
        request_field="schedule_request",
        response_field="schedule_response",
    ) -> None:
        self.connector = connector
        self.request_field = request_field
        self.response_field = response_field

    def __call__(self, source: Observable) -> Observable:
        return source.pipe(try_map(faulty(self.invoke)))

    def invoke(self, uow):
        if not uow.get(self.request_field):
            return uow
        return {
            **uow,
            self.response_field: self.connector.create_schedule(
                uow[self.request_field]
            ),
        }
