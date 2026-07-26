from datetime import datetime, timezone
import json

from expects import equal, expect

from modmex_lambda.stream.flavors.schedule import Schedule
from modmex_lambda.stream.rules_registry import RulesRegistry
from modmex_lambda.stream.sources.dynamodb import dynamodb_source
from tests.stream.flavors.source_events import dynamodb_stream_event


class SchedulerConnector:
    def __init__(self):
        self.requests = []
        self.events = []

    def create_schedule(self, request):
        self.requests.append(request)
        return {"ScheduleArn": "arn:aws:scheduler:example"}

    def put_events(self, request):
        self.events.append(request)
        return {"FailedEntryCount": 0}


class Resolver:
    def __init__(self, connector):
        self.connector = connector

    def resolve(self, _dependency):
        return self.connector


def collected_event_record(event):
    return {
        "keys": {"pk": event["id"], "sk": "EVENT"},
        "new_image": {
            "pk": event["id"],
            "sk": "EVENT",
            "discriminator": "EVENT",
            "sequence_number": "1",
            "ttl": 1911063600,
            "event": event,
        },
    }


def test_schedule_creates_one_time_eventbridge_delivery():
    connector = SchedulerConnector()
    scheduled_at = datetime(2030, 7, 23, 18, 5, tzinfo=timezone.utc)
    flavor = Schedule(
        {
            "id": "schedule-result-deadline",
            "event_type": "communication-completed",
            "schedule_at": lambda _uow: scheduled_at,
            "schedule_name": lambda uow: (
                "script-run-result-deadline-{}".format(
                    uow["event"]["script_run"]["id"]
                )
            ),
            "client_token": lambda uow: "deadline-{}".format(
                uow["event"]["script_run"]["id"]
            ),
            "bus_arn": "arn:aws:events:us-east-1:123:event-bus/main",
            "role_arn": "arn:aws:iam::123:role/scheduler",
            "source": "communication-control-service",
            "to_event": lambda uow, _flavor, template: {
                **template,
                "type": "script_run-result_deadline_reached",
                "script_run": uow["event"]["script_run"],
            },
        },
        dependency_resolver=Resolver(connector),
    )
    collected = []

    @dynamodb_source(
        RulesRegistry().registry(flavor),
        concurrency=False,
        on_next=lambda _pipeline, uow: collected.append(uow),
    )
    def handler(_event, _context):
        return {"statusCode": 200}

    handler(dynamodb_stream_event([collected_event_record({
        "id": "communication-completed-1",
        "type": "communication-completed",
        "timestamp": 1911060000000,
        "partition_key": "communication#comm-1",
        "script_run": {"id": "sr-1", "workspace_id": "ws-1"},
    })]), None)

    expect(len(collected)).to(equal(1))
    request = connector.requests[0]
    expect(request["Name"]).to(equal("script-run-result-deadline-sr-1"))
    expect(request["ScheduleExpression"]).to(equal("at(2030-07-23T18:05:00)"))
    expect(request["ActionAfterCompletion"]).to(equal("DELETE"))
    expect(request["Target"]["EventBridgeParameters"]).to(equal({
        "Source": "communication-control-service",
        "DetailType": "script_run-result_deadline_reached",
    }))
    event = json.loads(request["Target"]["Input"])
    expect(event["id"]).to(equal("deadline-sr-1"))
    expect(event["partition_key"]).to(equal("communication#comm-1"))
    expect(event["triggers"]).to(equal([{
        "id": "communication-completed-1",
        "type": "communication-completed",
        "timestamp": 1911060000000,
    }]))
    expect(event["script_run"]).to(equal({"id": "sr-1", "workspace_id": "ws-1"}))


def test_schedule_rejects_naive_datetime():
    flavor = Schedule({
        "id": "invalid-schedule",
        "event_type": "communication-completed",
        "schedule_at": lambda _uow: datetime(2026, 7, 23, 18, 5),
        "schedule_name": "invalid",
        "bus_arn": "bus",
        "role_arn": "role",
        "to_event": lambda _uow, _flavor, template: {
            **template,
            "type": "deadline",
        },
    })

    try:
        flavor._to_schedule_request({  # pylint: disable=protected-access
            "event": {"id": "event-1", "type": "communication-completed"},
        })
    except ValueError as error:
        expect(str(error)).to(equal(
            "schedule_at must return a timezone-aware datetime."
        ))
    else:
        raise AssertionError("Expected a naive schedule datetime to be rejected.")


def test_schedule_calculates_delay_minutes_from_event_timestamp():
    flavor = Schedule({
        "id": "relative-schedule",
        "event_type": "communication-completed",
        "delay_minutes": 5,
        "schedule_name": "relative",
        "bus_arn": "bus",
        "role_arn": "role",
        "to_event": lambda _uow, _flavor, template: {
            **template,
            "type": "deadline",
        },
    })

    request = flavor._to_schedule_request({  # pylint: disable=protected-access
        "event": {
            "id": "event-1",
            "type": "communication-completed",
            "timestamp": 1911060000000,
        },
    })

    expect(request["schedule_request"]["ScheduleExpression"]).to(equal(
        "at(2030-07-23T18:05:00)"
    ))


def test_schedule_requires_one_scheduling_strategy():
    flavor = Schedule({
        "id": "ambiguous-schedule",
        "event_type": "communication-completed",
        "schedule_at": lambda _uow: datetime.now(timezone.utc),
        "delay_minutes": 5,
        "schedule_name": "ambiguous",
        "bus_arn": "bus",
        "role_arn": "role",
        "to_event": lambda _uow, _flavor, template: {
            **template,
            "type": "deadline",
        },
    })

    try:
        flavor._to_schedule_request({  # pylint: disable=protected-access
            "event": {"id": "event-1", "type": "communication-completed"},
        })
    except ValueError as error:
        expect(str(error)).to(equal(
            "Schedule requires exactly one of schedule_at or delay_minutes."
        ))
    else:
        raise AssertionError("Expected conflicting scheduling strategies to fail.")


def test_schedule_immediately_emits_an_expired_deadline_without_creating_schedule():
    flavor = Schedule({
        "id": "expired-schedule",
        "event_type": "communication-completed",
        "schedule_at": lambda _uow: datetime(2000, 1, 1, tzinfo=timezone.utc),
        "schedule_name": "expired",
        "bus_arn": "bus",
        "role_arn": "role",
        "to_event": lambda _uow, _flavor, template: {
            **template,
            "type": "deadline",
        },
    })

    request = flavor._to_schedule_request({  # pylint: disable=protected-access
        "event": {
            "id": "event-1",
            "type": "communication-completed",
            "timestamp": 946684800000,
        },
    })

    expect("schedule_request" in request).to(equal(False))
    expect(request["emit"]["type"]).to(equal("deadline"))


def test_schedule_publishes_an_expired_deadline_without_creating_a_schedule():
    connector = SchedulerConnector()
    flavor = Schedule(
        {
            "id": "expired-schedule-pipeline",
            "event_type": "communication-completed",
            "schedule_at": lambda _uow: datetime(2000, 1, 1, tzinfo=timezone.utc),
            "schedule_name": "expired-pipeline",
            "bus_arn": "bus",
            "role_arn": "role",
            "to_event": lambda _uow, _flavor, template: {
                **template,
                "type": "deadline",
            },
        },
        dependency_resolver=Resolver(connector),
    )

    @dynamodb_source(RulesRegistry().registry(flavor), concurrency=False)
    def handler(_event, _context):
        return {"statusCode": 200}

    handler(dynamodb_stream_event([collected_event_record({
        "id": "communication-completed-1",
        "type": "communication-completed",
        "timestamp": 946684800000,
    })]), None)

    expect(connector.requests).to(equal([]))
    expect(len(connector.events)).to(equal(1))
    expect(connector.events[0]["Entries"][0]["DetailType"]).to(equal("deadline"))
