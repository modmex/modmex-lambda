from uuid import uuid1
from typing import Any, Callable, Optional

from reactivex import Observable, operators as ops
from pydash import get, set_
from modmex_lambda.connectors.ieventbridge import IEventBridgeConnector
from modmex_lambda.dependencies import DependencyResolver
from modmex_lambda.stream.flavors.base_flavor import BaseFlavor
from modmex_lambda.stream.operators.publisher import PublisherOptions
from modmex_lambda.stream.utils.contracts import BaseRule
from modmex_lambda.stream.utils.faults import faulty
from modmex_lambda.stream.utils.filters import on_event_type, on_content
from modmex_lambda.stream.utils.operators import try_filter, try_map, split_buffer
from modmex_lambda.stream.utils.print import print_end, print_start
from modmex_lambda.stream.utils.time import now



class TaskRule(BaseRule, total=False):
    execute: Callable[[dict, "Task"], Any]
    execute_operators: Callable[["Task"], Callable]
    emit: Any
    result_key: str


class Task(BaseFlavor):
    #pylint: disable=line-too-long
    """
    used to execute task and optionally emit result
    {
        'id': str
        'event_type': str | List[str] | Callable,
        'execute': Callable # execute task
        'emit': Optional[str | Callable]
    }
    """

    def __init__(
        self,
        rule: TaskRule,
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
            publisher_options={
                **(publisher_options or {}),
                'event_field': 'emit',
            },
        )
        self.rule = rule

    @property
    def id(self):
        return self.rule['id']

    def __call__(self, source: Observable):
        return source.pipe(
            try_filter(on_event_type(self.rule)),
            ops.do_action(print_start(self.logger)),
            try_filter(on_content(self.rule)),
            self._execute(),
            self._execute_operators(),
            self._to_event(),
            ops.do_action(print_end(self.logger)),
        )

    def _execute(self):
        def _call(uow):
            result_key = self.rule.get('result_key', 'result')
            return set_(
                uow,
                result_key,
                self.rule['execute'](uow, self)
            )

        def wrapper(source: Observable):
            execute = get(self.rule, 'execute')
            if execute:
                return source.pipe(
                    try_map(faulty(_call)),
                )
            return source.pipe()
        return wrapper

    def _execute_operators(self):
        def wrapper(source: Observable):
            extra_operators = get(self.rule, 'execute_operators')
            if extra_operators:
                return source.pipe(
                    extra_operators(self)
                )
            return source.pipe()
        return wrapper

    def _to_event(self):
        def wrapper(source: Observable):
            if get(self.rule, 'emit'):
                return source.pipe(
                    try_map(self._to_emit()),
                    split_buffer(),
                    self.publisher,
                )
            return source.pipe()
        return wrapper

    def _to_emit(self):
        def wrapper(uow):
            basic = isinstance(self.rule['emit'], str)
            template = {
                'id': str(uuid1()),
                'type': self.rule['emit'] if basic else None,
                'timestamp': now(),
                'partition_key': uow['event']['partition_key'],
            }
            result = template if basic else self.rule['emit'](uow, self, template)
            return [
                {
                    **uow,
                    'emit': emit
                }
                for emit in self._cast_array(result)
            ]
        return faulty(wrapper)

    @staticmethod
    def _cast_array(value):
        if isinstance(value, list):
            return value
        return [value]
