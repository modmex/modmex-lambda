from expects import equal, expect
from pydash import get
from reactivex import Observable
from modmex_lambda.stream.flavors.task import Task
from modmex_lambda.stream.sources.kinesis import kinesis_source
from modmex_lambda.stream.utils.operators import try_map
from modmex_lambda.stream.rules_registry import RulesRegistry
from tests.stream.flavors.source_events import kinesis_event

def _execute_task(uow, task):
    raise Exception("This is a test exception")


PIPELINES = [
    Task({
        'id': 'task1',
        'event_type': 'task1',
        'execute': _execute_task,
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
            "type": "task1",
            "timestamp": 1548967022000,
            "partition_key": "task3",
            "thing": {
                "name": "Thing Two",
                "description": "This is thing two"
            }
        },
    ])

    collected  = []
    faults = []
    def _on_next(_, uow):
        collected.append(uow)
    
    def on_fault(err):
        faults.append(err)

    @kinesis_source(
        RulesRegistry().registry(*PIPELINES),
        concurrency=False,
        on_next = _on_next,
        on_fault = on_fault
    )
    def handler(_event, _context):
        return {"statusCode": 200}

    handler(event, None)
    
    assert len(collected) == 0
    assert len(faults) == 2
