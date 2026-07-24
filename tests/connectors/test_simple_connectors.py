from expects import equal, expect
from modmex_lambda.connectors.cloudwatch import Connector as CloudwatchConnector
from modmex_lambda.connectors.eventbridge import Connector as EventbridgeConnector
from modmex_lambda.connectors.eventbridge_scheduler import (
    Connector as EventbridgeSchedulerConnector,
)
from modmex_lambda.connectors.lambda_ import Connector as LambdaConnector


class Client:
    def __init__(self):
        self.calls = []

    def put_metric_data(self, **kwargs):
        self.calls.append(('put_metric_data', kwargs))
        return {
            'metric': True,
        }

    def put_events(self, **kwargs):
        self.calls.append(('put_events', kwargs))
        return {
            'events': True,
        }

    def create_schedule(self, **kwargs):
        self.calls.append(('create_schedule', kwargs))
        return {
            'schedule': True,
        }

    def delete_schedule(self, **kwargs):
        self.calls.append(('delete_schedule', kwargs))
        return {}

    def invoke(self, **kwargs):
        self.calls.append(('invoke', kwargs))
        return {
            'lambda': True,
        }


def test_cloudwatch_put():
    client = Client()

    result = CloudwatchConnector(client).put({
        'Namespace': 'App',
        'MetricData': [],
    })

    expect(client.calls).to(equal([
        ('put_metric_data', {
            'Namespace': 'App',
            'MetricData': [],
        }),
    ]))
    expect(result).to(equal({'metric': True}))


def test_eventbridge_put_events():
    client = Client()

    result = EventbridgeConnector(client).put_events({
        'Entries': [],
    })

    expect(client.calls).to(equal([
        ('put_events', {
            'Entries': [],
        }),
    ]))
    expect(result).to(equal({'events': True}))


def test_eventbridge_scheduler_creates_and_deletes_schedule():
    client = Client()
    connector = EventbridgeSchedulerConnector(client)

    created = connector.create_schedule({'Name': 'once'})
    deleted = connector.delete_schedule({'Name': 'once'})

    expect(client.calls).to(equal([
        ('create_schedule', {'Name': 'once'}),
        ('delete_schedule', {'Name': 'once'}),
    ]))
    expect(created).to(equal({'schedule': True}))
    expect(deleted).to(equal({}))


def test_lambda_invoke():
    client = Client()

    result = LambdaConnector(client).invoke({
        'FunctionName': 'fn',
    })

    expect(client.calls).to(equal([
        ('invoke', {
            'FunctionName': 'fn',
        }),
    ]))
    expect(result).to(equal({'lambda': True}))
