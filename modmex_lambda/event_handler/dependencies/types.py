import types
from enum import Enum
from modmex import BaseModel
from typing import Union, Any, Dict, Set, Type, Callable

UnionType = getattr(types, "UnionType", Union)

IncEx = Union[Set[int], Set[str], Dict[int, Any], Dict[str, Any]]

TypeModelOrEnum = Union[Type[BaseModel], Type[Enum]]

ModelNameMap = Dict[TypeModelOrEnum, str]

CacheKey = Union[Callable[..., Any], None]