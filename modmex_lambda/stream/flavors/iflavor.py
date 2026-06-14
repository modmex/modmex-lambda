from abc import ABC, abstractmethod
from typing import Any

from reactivex import Observable



class IFlavor(ABC):
    @property
    @abstractmethod
    def id(self) -> str:
        ...

    def bind(self, dependency_resolver: Any) -> "IFlavor":
        return self

    @abstractmethod
    def __call__(self, source: Observable) -> Observable:
        ...
