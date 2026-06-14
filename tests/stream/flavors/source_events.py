import base64
import json
from decimal import Decimal

from modmex_lambda.stream.utils.dynamodb import marshall
from modmex_lambda.stream.utils.json_encoder import JSONEncoder


def kinesis_event(events):
    return {
        'Records': [
            {
                'eventSource': 'aws:kinesis',
                'eventID': f"shardId-000000000000:{index}",
                'awsRegion': 'us-west-2',
                'kinesis': {
                    'sequenceNumber': f"{index}",
                    'data': base64.b64encode(
                        json.dumps(event, cls=JSONEncoder).encode('utf-8')
                    ).decode('utf-8')
                }
            }
            for index, event in enumerate(events)
        ]
    }


def dynamodb_stream_event(records):
    return {
        'Records': [
            {
                'eventID': str(index),
                'eventName': record.get('event_name', 'INSERT'),
                'eventSource': 'aws:dynamodb',
                'awsRegion': record.get('aws_region', 'us-west-2'),
                'dynamodb': {
                    'ApproximateCreationDateTime': record.get('timestamp', 1548967023),
                    'Keys': marshall(record.get('keys')),
                    'NewImage': _image(record.get('new_image'), record.get('keys')),
                    'OldImage': _image(record.get('old_image'), record.get('keys')),
                    'SequenceNumber': str(index),
                    'StreamViewType': 'NEW_AND_OLD_IMAGES',
                },
            }
            for index, record in enumerate(records)
        ]
    }


def _image(value, keys):
    if value is None:
        return None
    if keys and 'sk' in keys and 'sk' not in value and 'discriminator' not in value:
        value = {
            **value,
            'sk': keys['sk'],
        }
    return marshall(json.loads(json.dumps(value), parse_float=Decimal))
