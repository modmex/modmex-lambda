from typing import Any, Dict, TypedDict


class DynamoDBStreamRecord(TypedDict, total=False):
    eventID: str
    eventName: str
    eventVersion: str
    eventSource: str
    awsRegion: str
    eventSourceARN: str
    dynamodb: Dict[str, Any]
    userIdentity: Dict[str, Any]
    


class DynamoDBStreamEvent(TypedDict):
    Records: list[DynamoDBStreamRecord]
