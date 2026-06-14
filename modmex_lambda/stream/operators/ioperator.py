from typing import Generic, TypeVar
from abc import ABC, abstractmethod
from reactivex import Observable

T = TypeVar("T")

class IOperator(ABC, Generic[T]):
    
    @abstractmethod
    def __call__(self, source: Observable[T]) -> Observable:
        raise NotImplementedError()


    