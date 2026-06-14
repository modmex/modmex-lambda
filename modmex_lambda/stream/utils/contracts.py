from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union
from typing_extensions import TypedDict


class Event(TypedDict, total=False):
    id: str
    type: str
    timestamp: int
    partition_key: Optional[str]
    tags: Optional[Dict[str, Any]]


class DynamoDBRaw(TypedDict, total=False):
    new: Dict[str, Any]
    old: Optional[Dict[str, Any]]


class DynamoDBEvent(Event):
    raw: DynamoDBRaw


UowEvent = TypeVar('UowEvent', bound=Event)


class Uow(TypedDict, Generic[UowEvent], total=False):
    pipeline: str
    record: Dict[str, Any]
    event: UowEvent


class BatchUow(TypedDict, Generic[UowEvent], total=False):
    batch: List[Uow[UowEvent]]


GenericEventType = Union[
    str,
    List[str],
    Callable[[Uow[UowEvent]], bool],
]


class BaseRule(TypedDict, total=False):
    id: str
    event_type: GenericEventType
    filters: List[Callable[[Dict[str, Any], Dict[str, Any]], bool]]
