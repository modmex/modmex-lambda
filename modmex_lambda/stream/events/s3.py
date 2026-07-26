import json
import pydash
from pydash import get


__all__ = [
    'from_s3',
    'from_sqs_eventbridge_s3',
    'from_sqs_sns_s3',
    'to_s3_records',
]


def from_s3(event):
    return pydash.map_(
        event['Records'],
        lambda record: {
            'record': record,
            'event':{
                'id': record['s3']['object']['key'],
                'type': _calculate_event_type_prefix(record),
                's3': record['s3'],
            },
        }
    )

def from_sqs_sns_s3(event):
    """Normalize an S3 notification delivered through SNS and SQS.

    An SNS message can contain more than one S3 record, so this function
    returns one UOW per S3 record.  The event contract is the same as
    :func:`from_s3`; the transport envelopes are retained in ``record``.
    """
    return pydash._(event['Records']).map(
        lambda sqs_record: _from_sqs_record(sqs_record)
    ).flatten().value()


def from_sqs_eventbridge_s3(event):
    """Normalize an S3 EventBridge notification delivered through SQS."""
    return pydash._(event['Records']).map(
        lambda sqs_record: _from_sqs_eventbridge_record(sqs_record)
    ).flatten().value()


def _from_sqs_eventbridge_record(sqs_record):
    eventbridge_record = json.loads(sqs_record['body'])
    detail = eventbridge_record['detail']
    s3_record = {
        **eventbridge_record,
        'eventName': _eventbridge_s3_event_name(eventbridge_record),
        's3': detail,
    }

    return pydash.map_(from_s3({'Records': [s3_record]}), lambda uow: {
        **uow,
        'record': {
            'sqs': sqs_record,
            'eventbridge': eventbridge_record,
            's3': uow['record'],
        },
    })


def _eventbridge_s3_event_name(eventbridge_record):
    detail_type = eventbridge_record.get('detail-type', '')
    if detail_type.startswith('Object Created'):
        return 'ObjectCreated:Put'
    if detail_type.startswith('Object Deleted'):
        return 'ObjectCreated:Delete'
    return detail_type


def _from_sqs_record(sqs_record):
    sns_record = json.loads(sqs_record['body'])
    s3_event = json.loads(sns_record['Message'])

    return pydash.map_(
        from_s3(s3_event),
        lambda uow: {
            **uow,
            'record': {
                'sqs': sqs_record,
                'sns': sns_record,
                's3': uow['record'],
            },
        },
    )

def _calculate_event_type_prefix(record):
    if record['eventName'] in ['ObjectCreated:Post','ObjectCreated:Put']:
        return 'object-created'
    if record['eventName'] == 'ObjectCreated:Delete':
        return 'object-deleted'
    return None


# test helper
def to_s3_records(notifications):
    return {
        'Records': [
            {
                # 'eventVersion': '2.1',
                'eventSource': 'aws:s3',
                'awsRegion': 'us-west-2',
                # 'eventTime': '2019-09-03T19:37:27.192Z',
                'eventName': 'ObjectCreated:Put',
                # 'userIdentity': {
                #   'principalId': 'AWS:AIDAINPONIXQXHT3IKHL2',
                # },
                # 'requestParameters': {
                #   'sourceIPAddress': '205.255.255.255',
                # },
                'responseElements': {
                    'x-amz-request-id': f"000000000000000{i}",
                #   'x-amz-id-2': 'vlR7PnpV2Ce81l0PRw6jlUpck7Jo5ZsQjryTjKlc5aLWGVHPZLj5NeC6qMa0emYBDXOo6QBU0Wo=',
                },
                's3': {
                # s3SchemaVersion: '1.0',
                # configurationId: '828aa6fc-f7b5-4305-8584-487c791949c1',
                    'bucket': get(n, 'bucket'), # {
                    # name: 'lambda-artifacts-deafc19498e3f2df',
                    # ownerIdentity: {
                    #   principalId: 'A3I5XTEXAMAI3E',
                    # },
                    # arn: 'arn:aws:s3:::lambda-artifacts-deafc19498e3f2df',
                    # },
                    'object': get(n, 'object'), # {
                # key: 'b21b84d653bb07b05b1e6b33684dc11b',
                # size: 1305107,
                # eTag: 'b21b84d653bb07b05b1e6b33684dc11b',
                # sequencer: '0C0F6F405D6ED209E1',
                # },
                },
            }
            for i,n in enumerate(notifications)
        ]
    }


__all__ = [
    'from_s3',
    'from_sqs_sns_s3',
    'from_sqs_eventbridge_s3',
    'to_s3_records',
]
