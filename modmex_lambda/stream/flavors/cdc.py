from typing import Any, Callable, Generic, Optional, TypeVar, Union

from reactivex import Observable, operators as ops

from modmex_lambda.connectors.ieventbridge import IEventBridgeConnector
from modmex_lambda.dependencies import DependencyResolver
from modmex_lambda.stream.filters.latch import out_latched
from modmex_lambda.stream.flavors.base_flavor import BaseFlavor
from modmex_lambda.stream.operators.publisher import PublisherOptions
from modmex_lambda.stream.utils.contracts import BaseRule, Event, Uow
from modmex_lambda.stream.utils.faults import faulty
from modmex_lambda.stream.utils.filters import on_event_type, on_content
from modmex_lambda.stream.utils.operators import try_filter, try_map, split_buffer
from modmex_lambda.stream.utils.print import print_end, print_start


TEvent = TypeVar('TEvent', bound=Event)


class CdcRule(BaseRule, Generic[TEvent]):
    to_event: Callable[[Uow[TEvent]], Union[TEvent, list[TEvent]]]


class ChangeDataCapture(Generic[TEvent], BaseFlavor[TEvent]):
    def __init__(
        self,
        rule: CdcRule[TEvent],
        *,
        logger: Optional[Any] = None,
        connector: Optional[IEventBridgeConnector] = None,
        dependency_resolver: Optional[DependencyResolver] = None,
        publisher_options: Optional[PublisherOptions] = None,
    ) -> None:
        super().__init__(
            logger=logger,
            connector=connector,
            dependency_resolver=dependency_resolver,
            publisher_options=publisher_options,
        )
        self.rule = rule

    @property
    def id(self):
        return self.rule['id']

    def __call__(self, source: Observable[Uow[TEvent]]) -> Observable:
        return source.pipe(
            try_filter(out_latched),
            try_filter(on_event_type(self.rule)),
            ops.do_action(print_start(self.logger)),
            try_filter(on_content(self.rule)),
            try_map(faulty(self._to_event)),
            split_buffer(),
            self.publisher,
            ops.do_action(print_end(self.logger)),
        )

    def _to_event(self, uow: Uow[TEvent]) -> list[Uow[TEvent]]:
        event_values = self.rule['to_event'](uow)
        events = event_values if isinstance(event_values, list) else [event_values]
        return [
            {
                **uow,
                'event': {
                    **uow['event'],
                    **event,
                }
            }
            for event in events
        ]
