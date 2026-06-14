import pytest

from modmex_lambda.stream.rules_registry import RulesRegistry


class DummyFlavor:
    def __init__(self, flavor_id):
        self._id = flavor_id

    @property
    def id(self):
        return self._id

    def __call__(self, source):
        return source


class BindableFlavor(DummyFlavor):
    def __init__(self, flavor_id):
        super().__init__(flavor_id)
        self.dependency_resolver = None

    def bind(self, dependency_resolver):
        self.dependency_resolver = dependency_resolver
        return self


def test_rules_registry_collects_flavors_in_registration_order():
    first = DummyFlavor('first')
    second = DummyFlavor('second')

    registry = RulesRegistry().registry(first).registry(second)

    assert registry.build() == [first, second]


def test_rules_registry_collects_multiple_flavors_in_one_call():
    first = DummyFlavor('first')
    second = DummyFlavor('second')

    registry = RulesRegistry().registry(first, second)

    assert registry.build() == [first, second]


def test_rules_registry_rejects_duplicated_flavor_ids():
    first = DummyFlavor('first')
    duplicated = DummyFlavor('first')

    registry = RulesRegistry().registry(first)

    with pytest.raises(ValueError, match="Duplicated flavor id: first"):
        registry.registry(duplicated)


def test_rules_registry_rejects_duplicated_flavor_ids_in_same_call():
    first = DummyFlavor('first')
    duplicated = DummyFlavor('first')

    with pytest.raises(ValueError, match="Duplicated flavor id: first"):
        RulesRegistry().registry(first, duplicated)


def test_rules_registry_build_returns_copy():
    first = DummyFlavor('first')
    registry = RulesRegistry().registry(first)

    built = registry.build()
    built.append(DummyFlavor('second'))

    assert registry.build() == [first]


def test_rules_registry_binds_registered_flavors():
    dependency_resolver = object()
    first = BindableFlavor('first')
    second = BindableFlavor('second')

    registry = RulesRegistry(dependency_resolver)
    registry.registry(first).registry(second)

    assert first.dependency_resolver is dependency_resolver
    assert second.dependency_resolver is dependency_resolver


def test_rules_registry_binds_existing_flavors_when_resolver_is_added_later():
    dependency_resolver = object()
    first = BindableFlavor('first')
    registry = RulesRegistry().registry(first)

    registry.bind(dependency_resolver)

    assert first.dependency_resolver is dependency_resolver
