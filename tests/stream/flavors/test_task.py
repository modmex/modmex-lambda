from expects import equal, expect
from pydash import get
from reactivex import Observable
from modmex_lambda.stream.flavors.task import Task
from modmex_lambda.stream.sources.kinesis import kinesis_source
from modmex_lambda.stream.utils.operators import try_map
from modmex_lambda.stream.rules_registry import RulesRegistry
from tests.stream.flavors.source_events import kinesis_event

def _execute_task(uow, task):
    uow['event']['thing'] = {
        'id': task.rule['id'],
        **uow['event']['thing']
    }
    return uow

def _execute_ops(_task):
    def wrapper(source: Observable):
        return source.pipe(
            try_map(lambda uow: {
                **uow,
                'ex_ops_result': 'OK'
            })
        )
    return wrapper

PIPELINES = [
    Task({
        'id': 'task1',
        'event_type': 'task1',
        'execute': _execute_task,
        'emit': lambda uow, _task, template: {
            **template,
            'type': 'task1-completed',
            'thing': uow['event']['thing']
        }
    }),
    Task({
        'id': 'task2',
        'event_type': 'task2',
        'execute': _execute_task,
        'emit': lambda uow, _task, template: [
            {
                **template,
                'type': 'task2-completed-1',
                'thing': uow['event']['thing'],
                'context': uow['event']['context']
            },
            {
                **template,
                'type': 'task2-completed-2',
                'thing': uow['event']['thing'],
                'context': uow['event']['context']
            },
        ]
    }),
    Task({
        'id': 'task3',
        'event_type': 'task1',
        'execute_operators': _execute_ops,
        'emit': lambda uow, _task, template: {
            **template,
            'type': 'task1-completed',
            'thing': uow['event']['thing']
        }
    }),
]

def test_execute_task():
    event = kinesis_event([
        {
            "type": "task1",
            "timestamp": 1548967022000,
            "partition_key": "task1",
            "thing": {
                "name": "Thing One",
                "description": "This is thing one"
            }
        },
        {
            "type": "task2",
            "timestamp": 1548967022000,
            "partition_key": "task2",
            "thing": {
                "name": "Thing Two",
                "description": "This is thing two"
            },
            "context": {
                "data1": "value",
                "data2": {
                    "key1": "value1"
                }
            }
        },
    ])

    collected  = []

    def _on_next(_, uow):
        collected.append(uow)

    @kinesis_source(
        RulesRegistry().registry(*PIPELINES),
        concurrency=False,
        on_next = _on_next
    )
    def handler(_event, _context):
        return {"statusCode": 200}

    handler(event, None)

    expect(len(collected)).to(equal(4))
    expect(get(collected, '[0].event.thing.id')).to(equal('task1'))
    expect(get(collected, '[0].emit.type')).to(equal('task1-completed'))
    expect(get(collected, '[1].event.thing.id')).to(equal('task2'))
    expect(get(collected, '[1].emit.type')).to(equal('task2-completed-1'))
    expect(get(collected, '[1].emit.context')).to(equal({
        "data1": "value",
        "data2": {
            "key1": "value1"
        }
    }))
    expect(get(collected, '[2].emit.type')).to(equal('task2-completed-2'))
    expect(get(collected, '[3].ex_ops_result')).to(equal('OK'))


class AnalyzerService:
    def analyze(self, thing):
        return {
            'analyzed_by': 'service',
            'thing': thing,
        }


class FakeDependencyResolver:
    def __init__(self):
        self.service = AnalyzerService()

    def resolve(self, dependency):
        if dependency is AnalyzerService:
            return self.service
        raise ValueError(dependency)


def test_execute_task_can_resolve_dependencies_from_task_flavor():
    def _execute(uow, task):
        analyzer = task.resolve(AnalyzerService)
        return analyzer.analyze(get(uow, 'event.thing'))

    event = kinesis_event([
        {
            "type": "task-with-dependency",
            "timestamp": 1548967022000,
            "partition_key": "task-with-dependency",
            "thing": {
                "name": "Thing One",
            }
        },
    ])

    collected = []

    @kinesis_source(
        RulesRegistry().registry(
            Task({
                'id': 'task-with-dependency',
                'event_type': 'task-with-dependency',
                'execute': _execute,
            })
        ),
        concurrency=False,
        dependency_resolver=FakeDependencyResolver(),
        on_next=lambda _, uow: collected.append(uow),
    )
    def handler(_event, _context):
        return {"statusCode": 200}

    handler(event, None)

    expect(get(collected, '[0].result')).to(equal({
        'analyzed_by': 'service',
        'thing': {
            'name': 'Thing One',
        },
    }))


def test_emit_task_can_read_rule_from_task_flavor():
    event = kinesis_event([
        {
            "type": "task-emit-rule",
            "timestamp": 1548967022000,
            "partition_key": "task-emit-rule",
            "thing": {
                "name": "Thing Two",
            }
        },
    ])

    collected = []

    @kinesis_source(
        RulesRegistry().registry(
            Task({
                'id': 'task-emit-rule',
                'event_type': 'task-emit-rule',
                'emit': lambda uow, task, template: {
                    **template,
                    'type': 'task-emit-rule-completed',
                    'rule_id': task.rule['id'],
                    'thing': uow['event']['thing'],
                }
            })
        ),
        concurrency=False,
        on_next=lambda _, uow: collected.append(uow),
    )
    def handler(_event, _context):
        return {"statusCode": 200}

    handler(event, None)

    expect(get(collected, '[0].emit.rule_id')).to(equal('task-emit-rule'))
