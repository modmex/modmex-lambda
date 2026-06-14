import copy
import multiprocessing
import threading
from typing import Iterable, Optional

from reactivex import Observable, from_list, operators as ops
from reactivex.scheduler import ThreadPoolScheduler

from modmex_lambda.stream.irules_registry import IRulesRegistry
from modmex_lambda.stream.utils.faults import flush_faults
from modmex_lambda.stream.utils.opt import DEFAULT_OPTIONS
from modmex_lambda.logging import Logger
from modmex_lambda.stream.utils.operators import tap


def run(
    events: Iterable,
    registry: IRulesRegistry,
    opt: Optional[dict] = None,
    on_next=None,
    on_error=None,
    on_completed=None,
    concurrency=True,
):
    opt = {
        **DEFAULT_OPTIONS,
        **(opt or {}),
    }
    optimal_thread_count = multiprocessing.cpu_count()
    pool_scheduler = ThreadPoolScheduler(optimal_thread_count)
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
            if on_error:
                on_error(pipeline_id, err)
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
