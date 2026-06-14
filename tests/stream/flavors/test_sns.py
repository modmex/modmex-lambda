from expects import equal, expect

from modmex_lambda.connectors.sns import Connector
from modmex_lambda.stream.flavors.sns import Sns
from modmex_lambda.stream.rules_registry import RulesRegistry
from modmex_lambda.stream.sources.kinesis import kinesis_source
from tests.stream.flavors.source_events import kinesis_event


def to_sns(uow):
    return [
        {
            "Message": uow["event"]["message"],
            "Subject": uow["event"]["subject"],
        }
    ]


def test_publish_to_sns(monkeypatch):
    event = kinesis_event([
        {
            "type": "notification-requested",
            "timestamp": 1548967022000,
            "subject": "Hello",
            "message": "Welcome",
        },
        {
            "type": "ignored",
            "timestamp": 1548967022000,
            "subject": "Nope",
            "message": "Skip me",
        },
    ])
    publish_calls = []

    def _publish_batch(connector, params):
        publish_calls.append({
            "topic_arn": connector.topic_arn,
            "params": params,
        })
        return {"Successful": [{"Id": "entry-1"}]}

    monkeypatch.setattr(Connector, "publish_batch", _publish_batch)
    collected = []

    def _on_next(_, uow):
        collected.append(uow)

    @kinesis_source(
        RulesRegistry().registry(
            Sns({
                "id": "sns1",
                "event_type": "notification-requested",
                "topic_arn": "arn:aws:sns:us-east-1:123:notifications",
                "to_sns": to_sns,
            })
        ),
        concurrency=False,
        on_next=_on_next,
    )
    def handler(_event, _context):
        return {"statusCode": 200}

    handler(event, None)

    expect(len(collected)).to(equal(1))
    expect(collected[0]["pipeline"]).to(equal("sns1"))
    expect(collected[0]["sns_payload"]).to(equal([
        {
            "Message": "Welcome",
            "Subject": "Hello",
        }
    ]))
    expect(collected[0]["publish_response"]).to(equal({"Successful": [{"Id": "entry-1"}]}))
    expect(publish_calls[0]["topic_arn"]).to(equal("arn:aws:sns:us-east-1:123:notifications"))
    entries = publish_calls[0]["params"]["PublishBatchRequestEntries"]
    expect(len(entries)).to(equal(1))
    assert "Id" in entries[0]
    expect(entries[0]["Message"]).to(equal("Welcome"))
    expect(entries[0]["Subject"]).to(equal("Hello"))
