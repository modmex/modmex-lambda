from expects import equal, expect
from reactivex import from_list

from modmex_lambda.stream.operators.scheduler import SchedulerOps


class Connector:
    def __init__(self):
        self.requests = []

    def create_schedule(self, request):
        self.requests.append(request)
        return {"ScheduleArn": "arn:aws:scheduler:example"}


def test_scheduler_ops_creates_schedule_from_request_field():
    connector = Connector()
    collected = []

    from_list([{"schedule_request": {"Name": "once"}}]).pipe(
        SchedulerOps(connector)
    ).subscribe(collected.append)

    expect(connector.requests).to(equal([{"Name": "once"}]))
    expect(collected[0]["schedule_response"]).to(equal({
        "ScheduleArn": "arn:aws:scheduler:example"
    }))


def test_scheduler_ops_keeps_uow_without_schedule_request():
    connector = Connector()
    collected = []

    from_list([{"event": {"id": "event-1"}}]).pipe(
        SchedulerOps(connector)
    ).subscribe(collected.append)

    expect(connector.requests).to(equal([]))
    expect(collected).to(equal([{"event": {"id": "event-1"}}]))
