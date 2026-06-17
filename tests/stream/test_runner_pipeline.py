import json
import logging

from expects import contain, equal, expect
from reactivex import Observable, from_list
from reactivex import operators as ops

from modmex_lambda.stream.rules_registry import RulesRegistry
from modmex_lambda.stream.runner import run
from modmex_lambda.stream.utils.faults import faulty
from modmex_lambda.stream.utils.operators import try_filter, try_map
from modmex_lambda.stream.utils.print import print_end, print_start


class Pipeline:
    def __init__(self, pipeline_id, operator):
        self.id = pipeline_id
        self.operator = operator

    def __call__(self, source: Observable):
        return self.operator(source)


def test_runner_executes_registered_pipelines():
    collected = []
    errors = []

    def raise_exception(uow):
        if uow['event']['id'] == 3:
            raise Exception('My exception')
        return uow

    pipelines = [
        Pipeline(
            'test1',
            lambda source: source.pipe(
                try_map(lambda uow: {**uow, 'map1': True}),
                try_map(lambda uow: {**uow, 'map2': True}),
                try_filter(lambda uow: uow['event']['id'] > 1),
            ),
        ),
        Pipeline(
            'test2',
            lambda source: source.pipe(
                try_map(faulty(raise_exception)),
                try_map(lambda uow: {**uow, 'map1': True}),
                try_map(lambda uow: {**uow, 'map2': True}),
            ),
        ),
    ]

    run(
        [
            {'event': {'id': 1, 'number': 1}},
            {'event': {'id': 2, 'number': 2}},
            {'event': {'id': 3, 'number': 3}},
        ],
        RulesRegistry().registry(*pipelines),
        concurrency=False,
        on_next=lambda _, uow: collected.append(uow),
        on_error=lambda _, error: errors.append(error),
    )

    expect(errors).to(equal([]))
    expect(len(collected)).to(equal(4))
    expect(collected[0]['pipeline']).to(equal('test1'))
    expect(collected[0]['event']['id']).to(equal(2))
    expect(collected[0]['map1']).to(equal(True))
    expect(collected[1]['event']['id']).to(equal(3))
    expect(collected[2]['pipeline']).to(equal('test2'))
    expect(collected[2]['event']['id']).to(equal(1))
    expect(collected[2]['map1']).to(equal(True))
    expect(collected[3]['event']['id']).to(equal(2))


def test_runner_with_concurrency_and_flat_map():
    collected = []
    completed = []

    def operator(multiplier):
        return lambda source: source.pipe(
            ops.flat_map(lambda uow: from_list([
                {**uow, 'copy': multiplier},
                {**uow, 'copy': multiplier * 2},
            ]))
        )

    run(
        [
            {'event': {'id': 1}},
            {'event': {'id': 2}},
        ],
        RulesRegistry().registry(
            Pipeline('test1', operator(1)),
            Pipeline('test2', operator(10)),
        ),
        on_next=lambda _, uow: collected.append(uow),
        on_completed=lambda pipeline: completed.append(pipeline),
    )

    expect(len(collected)).to(equal(8))
    expect(sorted(completed)).to(equal(['test1', 'test2']))
    expect(sorted([uow['copy'] for uow in collected])).to(equal([
        1, 1, 2, 2, 10, 10, 20, 20
    ]))


def test_runner_with_concurrency_flat_map_and_failed_item():
    collected = []
    completed = []
    errors = []

    def fail_second_event(uow):
        if uow['event']['id'] == 2:
            raise Exception('bad item')
        return uow

    def operator(multiplier):
        return lambda source: source.pipe(
            ops.flat_map(lambda uow: from_list([
                {**uow, 'copy': multiplier},
                {**uow, 'copy': multiplier * 2},
            ])),
            try_map(faulty(fail_second_event)),
        )

    run(
        [
            {'event': {'id': 1}},
            {'event': {'id': 2}},
            {'event': {'id': 3}},
        ],
        RulesRegistry().registry(
            Pipeline('test1', operator(1)),
            Pipeline('test2', operator(10)),
        ),
        on_next=lambda _, uow: collected.append(uow),
        on_error=lambda _, error: errors.append(error),
        on_completed=lambda pipeline: completed.append(pipeline),
    )

    expect(len(errors)).to(equal(0))
    expect(len(collected)).to(equal(8))
    expect(sorted(completed)).to(equal(['test1', 'test2']))
    expect(sorted([uow['event']['id'] for uow in collected])).to(equal([
        1, 1, 1, 1, 3, 3, 3, 3
    ]))


def test_runner_uses_default_structured_logger(monkeypatch, capsys):
    collected = []
    monkeypatch.setenv('LOG_LEVEL', 'DEBUG')

    run(
        [{'event': {'id': 1}}],
        RulesRegistry().registry(
            Pipeline('test', lambda source: source.pipe(try_map(lambda uow: uow))),
        ),
        opt={'logger': None},
        concurrency=False,
        on_next=lambda _, uow: collected.append(uow),
    )

    expect(len(collected)).to(equal(1))
    lines = [
        json.loads(line)
        for line in capsys.readouterr().out.splitlines()
        if line.strip()
    ]
    expect([line['message'] for line in lines]).to(equal(['flush faults', []]))
    expect([line['service'] for line in lines]).to(equal(['service', 'service']))


def test_runner_pipeline_can_log_with_explicit_logger(capsys, monkeypatch):
    monkeypatch.setenv('LOG_LEVEL', 'DEBUG')
    logger = logging.getLogger('test')
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    handler = logging.StreamHandler()
    logger.addHandler(handler)

    run(
        [
            {
                'event': {
                    'id': 'evt-1',
                    'type': 'thing-created',
                },
            },
        ],
        RulesRegistry().registry(
            Pipeline(
                'test',
                lambda source: source.pipe(
                    ops.do_action(print_start(logger)),
                    ops.do_action(print_end(logger)),
                ),
            ),
        ),
        concurrency=False,
    )

    output = capsys.readouterr()

    expect(output.err).to(contain('start type: thing-created, eid: evt-1'))
    expect(output.err).to(contain('end type: thing-created, eid: evt-1'))
