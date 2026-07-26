from expects import equal, expect
import json

from modmex_lambda.stream.events.s3 import from_s3, from_sqs_sns_s3, to_s3_records


def test_from_s3_created_events():
    records = to_s3_records([
        {
            'bucket': {
                'name': 'bucket',
            },
            'object': {
                'key': 'thing.json',
            },
        },
    ])

    uows = from_s3(records)

    expect(len(uows)).to(equal(1))
    expect(uows[0]['event']).to(equal({
        'id': 'thing.json',
        'type': 'object-created',
        's3': records['Records'][0]['s3'],
    }))


def test_from_s3_deleted_events():
    records = to_s3_records([
        {
            'bucket': {
                'name': 'bucket',
            },
            'object': {
                'key': 'thing.json',
            },
        },
    ])
    records['Records'][0]['eventName'] = 'ObjectCreated:Delete'

    expect(from_s3(records)[0]['event']['type']).to(equal('object-deleted'))


def test_from_s3_unknown_events():
    records = to_s3_records([
        {
            'bucket': {},
            'object': {
                'key': 'thing.json',
            },
        },
    ])
    records['Records'][0]['eventName'] = 'ObjectRestore:Completed'

    expect(from_s3(records)[0]['event']['type']).to(equal(None))


def test_from_sqs_sns_s3_normalizes_s3_event_and_keeps_envelopes():
    s3_event = to_s3_records([
        {
            'bucket': {'name': 'bucket'},
            'object': {'key': 'thing.json'},
        },
    ])
    sns_record = {
        'Type': 'Notification',
        'MessageId': 'message-id',
        'Message': json.dumps(s3_event),
    }
    sqs_record = {
        'messageId': 'sqs-message-id',
        'body': json.dumps(sns_record),
    }

    uows = from_sqs_sns_s3({'Records': [sqs_record]})

    expect(len(uows)).to(equal(1))
    expect(uows[0]['event']).to(equal({
        'id': 'thing.json',
        'type': 'object-created',
        's3': s3_event['Records'][0]['s3'],
    }))
    expect(uows[0]['record']).to(equal({
        'sqs': sqs_record,
        'sns': sns_record,
        's3': s3_event['Records'][0],
    }))


def test_from_sqs_sns_s3_expands_all_s3_records_from_each_message():
    s3_event = to_s3_records([
        {'bucket': {'name': 'bucket'}, 'object': {'key': 'one.json'}},
        {'bucket': {'name': 'bucket'}, 'object': {'key': 'two.json'}},
    ])
    message = {'Message': json.dumps(s3_event)}
    event = {'Records': [
        {'messageId': 'one', 'body': json.dumps(message)},
        {'messageId': 'two', 'body': json.dumps(message)},
    ]}

    uows = from_sqs_sns_s3(event)

    expect([uow['event']['id'] for uow in uows]).to(
        equal(['one.json', 'two.json', 'one.json', 'two.json'])
    )
