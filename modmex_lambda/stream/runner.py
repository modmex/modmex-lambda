import copy
import multiprocessing
import os
import threading
from contextvars import Token
from typing import Any, Callable, Iterable, TypedDict

from reactivex import Observable, from_list, operators as ops

from modmex_lambda.stream.irules_registry import IRulesRegistry
from modmex_lambda.stream.schedulers import ContextThreadPoolScheduler
from modmex_lambda.stream.utils.eventbridge import publish_to_event_bridge
from modmex_lambda.stream.utils.faults import flush_faults
from modmex_lambda.logging import Logger
from modmex_lambda.stream.utils.operators import tap
from modmex_lambda.stream.utils.faults import FaultHandler, active_fault_handler


PublishFactory = Callable[[dict[str, Any]], Any]
BusName = str | Callable[[dict[str, Any]], str] | None


class RunOptions(TypedDict, total=False):
    bus_name: BusName
    publish: PublishFactory
    logger: Any


def _publish_to_event_bridge(params: dict[str, Any]) -> Any:
    return publish_to_event_bridge(**params)


def run(
    events: Iterable,
    registry: IRulesRegistry,
    opt: RunOptions | None = None,
    on_next=None,
    on_error=None,
    on_completed=None,
    concurrency=True,
    on_fault: FaultHandler | None = None,
    raise_on_error: bool = True,
):
    """Run every registered pipeline over ``events``.

    Handled failures (wrapped with ``faulty``) are published as fault events and
    do not fail the invocation. An unexpected error that ends a pipeline is
    re-raised once all pipelines finished and faults were flushed, so the Lambda
    invocation fails and AWS retries the batch instead of acknowledging records
    that were never processed. ``on_error`` is still called first (observability).
    Pass ``raise_on_error=False`` to only report such errors through ``on_error``.
    """
    pipeline_errors: list[BaseException] = []
    token: Token = active_fault_handler.set(on_fault)
    try:
        opt = {
            'bus_name': os.getenv('BUS_NAME'),
            'publish': _publish_to_event_bridge,
            **(opt or {}),
        }
        optimal_thread_count = multiprocessing.cpu_count()
        pool_scheduler = ContextThreadPoolScheduler(optimal_thread_count)
        pipeline_logger = opt.get('logger') or Logger()
        

        def make_lines(flavor):
            source = from_list( # pylint: disable=E1102
                copy.deepcopy(events)
            ).pipe(
                ops.map(lambda uow: {
                    'pipeline': flavor.id,
                    **uow,
                }),
                flavor,
            )
            source.id = flavor.id
            return source

        lines = list(map(make_lines, registry.build()))
        pending = len(lines)
        completed = threading.Event()
        completed_lock = threading.Lock()

        if pending == 0:
            completed.set()

        def mark_completed():
            nonlocal pending

            with completed_lock:
                pending -= 1
                if pending == 0:
                    completed.set()

        def _emit(source: Observable): #pylint: disable=no-self-use
            def _on_next(pipeline_id, uow):
                if on_next:
                    on_next(pipeline_id, uow)

            def _on_error(pipeline_id, err):
                pipeline_errors.append(err)
                try:
                    if on_error:
                        on_error(pipeline_id, err)
                finally:
                    mark_completed()

            def _on_completed(pipeline_id):
                if on_completed:
                    on_completed(pipeline_id)
                mark_completed()

            source.subscribe(
                on_next=lambda i: _on_next(source.id, i),
                on_error=lambda e: _on_error(source.id, e),
                on_completed=lambda *_: _on_completed(source.id),
                **({'scheduler': pool_scheduler} if concurrency else {})
            )

        from_list(lines).pipe( # pylint: disable=E1102
            tap(_emit)
        ).subscribe()

        completed.wait()
        pool_scheduler.executor.shutdown()
        flush_faults({
            **opt,
            'logger': pipeline_logger,
        })

    finally:
        active_fault_handler.reset(token)

    if pipeline_errors and raise_on_error:
        for extra in pipeline_errors[1:]:
            pipeline_logger.error(f"Additional pipeline error: {extra!r}")
        raise pipeline_errors[0]
