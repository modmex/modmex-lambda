import os
from typing import Any, Callable, Optional

from pydash import get, pick
from reactivex import Observable, create, operators as ops

from modmex_lambda.connectors.ieventbridge import IEventBridgeConnector
from modmex_lambda.dependencies import DependencyResolver
from modmex_lambda.stream.flavors.base_flavor import BaseFlavor
from modmex_lambda.stream.operators.publisher import PublisherOptions
from modmex_lambda.stream.utils.contracts import BaseRule, Uow
from modmex_lambda.stream.utils.faults import faulty
from modmex_lambda.stream.utils.filters import on_content, on_event_type
from modmex_lambda.stream.utils.operators import split_buffer, try_filter, try_map
from modmex_lambda.stream.utils.print import print_end, print_start
from modmex_lambda.stream.utils.split import split_object


class JobRule(BaseRule, total=False):
    job_filters: list[Callable[[Uow, dict], bool]]
    to_scan_request: Callable[[Uow, dict], dict]
    to_query_split_request: Callable[[Uow, dict], dict]
    to_query_related_request: Callable[[Uow, dict], dict]
    to_query_request: Callable[[Uow, dict], dict]
    to_get_request: Callable[[Uow, dict], dict]
    to_update_request: Callable[[Uow, dict], dict]
    to_event: Callable[[Uow, dict], dict]
    to_cursor_update_request: Callable[[Uow, dict], dict]
    cursor_key_fn: Callable[[Uow], str]
    table_name: str
    scan_request_field: str
    scan_response_field: str
    query_split_request_field: str
    query_split_response_field: str
    query_request_field: str
    query_response_field: str
    batch_get_request_field: str
    batch_get_response_field: str
    update_request_field: str
    update_response_field: str
    cursor_update_request_field: str
    cursor_update_response_field: str
    split_on: Any
    split_target_field: str


class Job(BaseFlavor):
    def __init__(
        self,
        rule: JobRule,
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
        table_name = self.rule.get(
            'table_name',
            os.getenv('EVENT_TABLE_NAME') or
            os.getenv('ENTITY_TABLE_NAME') or
            os.getenv('TABLE_NAME')
        )

        return source.pipe(
            try_filter(on_event_type(self.rule)),
            ops.do_action(print_start(self.logger)),
            try_filter(on_content({
                **self.rule,
                'filters': self.rule.get('job_filters', []),
            })),
            try_map(faulty(self._to_scan_request)),
            self.dynamodb_ops.scan_split(
                **pick({
                    **self.rule,
                    'table_name': table_name,
                }, [
                    'table_name',
                    'scan_request_field',
                    'scan_response_field',
                ])
            ),
            try_map(faulty(self._to_query_split_request)),
            self.dynamodb_ops.query_split(
                **pick({
                    **self.rule,
                    'table_name': table_name,
                }, [
                    'table_name',
                    'query_split_request_field',
                    'query_split_response_field',
                ])
            ),
            try_filter(on_content(self.rule)),
            try_map(faulty(self._to_query_related_request)),
            self.dynamodb_ops.query(
                **pick({
                    **self.rule,
                    'table_name': table_name,
                }, [
                    'table_name',
                    'query_request_field',
                    'query_response_field',
                ])
            ),
            split_object({
                **self.rule,
                'split_on': self.rule.get(
                    'split_on',
                    self.rule.get('query_response_field', 'query_response')
                ),
                'split_target_field': self.rule.get(
                    'split_target_field',
                    self.rule.get('query_response_field', 'query_response')
                ),
            }) if self.rule.get('split_on') or self._has_query_related_request()
            else _identity,
            try_map(faulty(self._to_get_request)),
            self.dynamodb_ops.batch_get(
                **pick({
                    **self.rule,
                    'table_name': table_name,
                }, [
                    'table_name',
                    'batch_get_request_field',
                    'batch_get_response_field',
                ])
            ),
            try_map(faulty(self._to_update_request)),
            self.dynamodb_ops.update(
                **pick({
                    **self.rule,
                    'table_name': table_name,
                }, [
                    'table_name',
                    'update_request_field',
                    'update_response_field',
                ])
            ),
            try_map(faulty(self._to_event)),
            split_buffer(),
            self.publisher,
            self._flush_cursor(table_name),
            ops.do_action(print_end(self.logger)),
        )

    def _to_scan_request(self, uow):
        return {
            **uow,
            self.rule.get('scan_request_field', 'scan_request'):
                self.rule['to_scan_request'](uow, self.rule)
                if 'to_scan_request' in self.rule
                else None
        }

    def _to_query_split_request(self, uow):
        return {
            **uow,
            self.rule.get('query_split_request_field', 'query_split_request'):
                self.rule['to_query_split_request'](uow, self.rule)
                if 'to_query_split_request' in self.rule
                else None
        }

    def _to_query_related_request(self, uow):
        to_request = self.rule.get('to_query_related_request') or \
            self.rule.get('to_query_request')
        return {
            **uow,
            self.rule.get('query_request_field', 'query_request'):
                to_request(uow, self.rule)
                if to_request
                else None
        }

    def _to_get_request(self, uow):
        return {
            **uow,
            self.rule.get('batch_get_request_field', 'batch_get_request'):
                self.rule['to_get_request'](uow, self.rule)
                if 'to_get_request' in self.rule
                else None
        }

    def _to_update_request(self, uow):
        return {
            **uow,
            self.rule.get('update_request_field', 'update_request'):
                self.rule['to_update_request'](uow, self.rule)
                if 'to_update_request' in self.rule
                else None
        }

    def _to_event(self, uow):
        if 'to_event' not in self.rule:
            return [uow]

        event_values = self.rule['to_event'](uow, self.rule)
        events = event_values if isinstance(event_values, list) else [event_values]
        return [
            {
                **uow,
                'emit': event,
            }
            for event in events
        ]

    def _flush_cursor(self, table_name):
        if 'to_cursor_update_request' not in self.rule:
            return _identity

        cursor_update_request_field = self.rule.get(
            'cursor_update_request_field',
            'cursor_update_request',
        )
        cursor_update_response_field = self.rule.get(
            'cursor_update_response_field',
            'cursor_update_response',
        )
        update = self.dynamodb_ops.update(
            table_name=table_name,
            update_request_field=cursor_update_request_field,
            update_response_field=cursor_update_response_field,
        )

        def operator(source: Observable):
            def subscribe(observer, scheduler=None):
                groups = {}

                def on_next(uow):
                    key = self._cursor_key(uow)
                    groups.setdefault(key, []).append(uow)

                def on_completed():
                    try:
                        for batch in groups.values():
                            for uow in batch:
                                observer.on_next(uow)

                            cursor_uow = {
                                **batch[-1],
                                cursor_update_request_field:
                                    self.rule['to_cursor_update_request'](
                                        batch[-1],
                                        self.rule,
                                    ),
                            }
                            observer.on_next(update.invoke(cursor_uow))
                        observer.on_completed()
                    except Exception as err:  # pylint: disable=broad-except
                        observer.on_error(err)

                return source.subscribe(
                    on_next,
                    observer.on_error,
                    on_completed,
                    scheduler=scheduler,
                )

            return create(subscribe)

        return operator

    def _cursor_key(self, uow):
        cursor_key_fn = self.rule.get('cursor_key_fn')
        if cursor_key_fn:
            return cursor_key_fn(uow)
        return "pk:{}|sk:{}".format(
            get(uow, 'event.raw.new.pk'),
            get(uow, 'event.raw.new.sk'),
        )

    def _has_query_related_request(self):
        return 'to_query_related_request' in self.rule or \
            'to_query_request' in self.rule


def _identity(source: Observable):
    return source
