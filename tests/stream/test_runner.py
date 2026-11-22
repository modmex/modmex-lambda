import pytest
from reactivex import operators as ops

import modmex_lambda.stream.runner as runner_module
from modmex_lambda.stream.rules_registry import RulesRegistry


class DummyFlavor:
    def __init__(self, flavor_id, multiplier):
        self._id = flavor_id
        self.multiplier = multiplier

    @property
    def id(self):
        return self._id

    def __call__(self, source):
        return source.pipe(
            ops.map(lambda uow: {
                **uow,
                'value': uow['event']['value'] * self.multiplier,
                'handled_by': self.id,
            })
        )


class ErrorFlavor:
    id = 'error'

    def __call__(self, source):
        def raise_error(_):
            raise RuntimeError('boom')

        return source.pipe(ops.map(raise_error))


def test_run_executes_registered_flavors(monkeypatch):
    flushed = []
    collected = []
    completed = []
    monkeypatch.setattr(
        runner_module,
        'flush_faults',
        lambda opt: flushed.append(opt),
    )
    registry = RulesRegistry().registry(
        DummyFlavor('first', 1)
    ).registry(
        DummyFlavor('second', 10)
    )

    runner_module.run(
        [
            {'event': {'value': 2}},
        ],
        registry,
        opt={'logger': None, 'publish': lambda _: (lambda source: source)},
        on_next=lambda pipeline_id, uow: collected.append((pipeline_id, uow)),
        on_completed=lambda pipeline_id: completed.append(pipeline_id),
        concurrency=False,
    )

    assert [(pipeline_id, uow['value']) for pipeline_id, uow in collected] == [
        ('first', 2),
        ('second', 20),
    ]
    assert [uow['pipeline'] for _, uow in collected] == ['first', 'second']
    assert completed == ['first', 'second']
    assert len(flushed) == 1
    assert 'bus_name' in flushed[0]


def test_run_calls_on_error_for_pipeline_errors(monkeypatch):
    flushed = []
    errors = []
    monkeypatch.setattr(
        runner_module,
        'flush_faults',
        lambda opt: flushed.append(opt),
    )

    with pytest.raises(Exception, match='boom'):
        runner_module.run(
            [{'event': {'value': 2}}],
            RulesRegistry().registry(ErrorFlavor()),
            opt={'logger': None, 'publish': lambda _: (lambda source: source)},
            on_error=lambda pipeline_id, err: errors.append((pipeline_id, err)),
            concurrency=False,
        )

    assert len(flushed) == 1  # faults are flushed before the error is re-raised
    assert errors[0][0] == 'error'
    assert str(errors[0][1]) == 'boom'


def test_run_handles_empty_registry(monkeypatch):
    flushed = []
    monkeypatch.setattr(
        runner_module,
        'flush_faults',
        lambda opt: flushed.append(opt),
    )

    runner_module.run(
        [{'event': {'value': 2}}],
        RulesRegistry(),
        opt={'logger': None, 'publish': lambda _: (lambda source: source)},
        concurrency=False,
    )

    assert len(flushed) == 1
    assert 'bus_name' in flushed[0]


def test_unexpected_pipeline_error_fails_the_invocation_instead_of_dropping_records(monkeypatch):
    from reactivex import operators as ops

    monkeypatch.setattr(runner_module, 'flush_faults', lambda opt: None)
    processed = []

    class BuggyFlavor:
        id = 'buggy'

        def __call__(self, source):
            def handle(uow):
                if uow['event']['id'] == 2:
                    raise KeyError('missing_field')  # a bug, not a handled fault
                return uow
            return source.pipe(ops.map(handle))

    class Registry:
        def build(self):
            return [BuggyFlavor()]

    with pytest.raises(KeyError):
        runner_module.run(
            [{'event': {'id': i}} for i in (1, 2, 3)],
            Registry(),
            opt={'logger': None, 'publish': lambda _: (lambda source: source)},
            on_next=lambda _pipeline, uow: processed.append(uow['event']['id']),
            concurrency=False,
        )
    assert processed == [1]  # 2 and 3 were not processed, so the batch must be retried


def test_raise_on_error_false_only_reports_through_on_error(monkeypatch):
    monkeypatch.setattr(runner_module, 'flush_faults', lambda opt: None)
    errors = []
    runner_module.run(
        [{'event': {'value': 2}}],
        RulesRegistry().registry(ErrorFlavor()),
        opt={'logger': None, 'publish': lambda _: (lambda source: source)},
        on_error=lambda pipeline_id, err: errors.append(err),
        concurrency=False,
        raise_on_error=False,
    )
    assert str(errors[0]) == 'boom'
