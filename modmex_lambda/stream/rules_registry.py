from typing import List, Optional

from modmex_lambda.dependencies import DependencyResolver
from modmex_lambda.stream.flavors.iflavor import IFlavor
from modmex_lambda.stream.irules_registry import IRulesRegistry


class RulesRegistry(IRulesRegistry):
    def __init__(
        self,
        dependency_resolver: Optional[DependencyResolver] = None,
    ) -> None:
        self._dependency_resolver = dependency_resolver
        self._flavors: List[IFlavor] = []
        self._ids = set()

    def registry(self, *flavors: IFlavor) -> "RulesRegistry":
        for flavor in flavors:
            if flavor.id in self._ids:
                raise ValueError(f"Duplicated flavor id: {flavor.id}")

            self._ids.add(flavor.id)
            self._bind_flavor(flavor)
            self._flavors.append(flavor)
        return self

    def bind(self, dependency_resolver: DependencyResolver) -> "RulesRegistry":
        self._dependency_resolver = dependency_resolver
        for flavor in self._flavors:
            self._bind_flavor(flavor)
        return self

    def build(self) -> List[IFlavor]:
        return list(self._flavors)

    def _bind_flavor(self, flavor: IFlavor) -> None:
        if self._dependency_resolver is not None and hasattr(flavor, "bind"):
            flavor.bind(self._dependency_resolver)
