from abc import ABC, abstractmethod
from typing import List
from modmex_lambda.dependencies import DependencyResolver
from modmex_lambda.stream.flavors.iflavor import IFlavor


class IRulesRegistry(ABC):
    @abstractmethod
    def registry(self, *flavors: IFlavor) -> "IRulesRegistry":
        ...

    @abstractmethod
    def bind(self, dependency_resolver: DependencyResolver) -> "IRulesRegistry":
        ...

    @abstractmethod
    def build(self) -> List[IFlavor]:
        ...
