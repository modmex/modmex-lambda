from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any, Annotated, Literal

from modmex import BaseModel
from modmex_lambda.validation import ModmexValidator, ValidationError


class Payload(BaseModel):
    name: str


class Status(Enum):
    ACTIVE = "active"


def test_modmex_validator_uses_modmex_for_primitives_and_models() -> None:
    validator = ModmexValidator()

    assert validator.validate("42", int) == 42
    assert validator.validate("true", bool) is True
    assert validator.validate({"name": "Ada"}, Payload).name == "Ada"


def test_modmex_validator_serializes_model_dump_objects() -> None:
    class Model:
        def model_dump(self):
            return {"ok": True}

        def model_dump_json(self):
            return '{"ok":true}'

    validator = ModmexValidator()
    model = Model()

    assert validator.serialize(model) == {"ok": True}
    assert validator.dumps(model) == '{"ok":true}'


def test_modmex_validator_handles_nested_typing_annotations() -> None:
    validator = ModmexValidator()

    assert validator.validate(["1", "2"], list[int]) == [1, 2]
    assert validator.validate({"1": "true"}, dict[int, bool]) == {1: True}
    assert validator.validate("42", int | str) == 42
    assert validator.validate("active", Literal["active", "inactive"]) == "active"


def test_modmex_validator_reports_locations_for_nested_errors() -> None:
    validator = ModmexValidator()

    try:
        validator.validate(["1", "bad"], list[int], ["query", "ids"])
    except ValidationError as exc:
        errors = exc.errors
    else:
        raise AssertionError("Expected validation error")

    assert errors[0]["loc"] == ["query", "ids", 1]


def test_modmex_validator_handles_any_none_tuple_enum_and_plain_objects() -> None:
    validator = ModmexValidator()

    class PlainPayload:
        def __init__(self, name: str) -> None:
            self.name = name

    assert validator.validate("raw", Any) == "raw"
    assert validator.validate("raw", Annotated[str, "meta"]) == "raw"
    assert validator.validate(None, str | None) is None
    assert validator.validate(("1", "true"), tuple[int, bool]) == (1, True)
    assert validator.validate(("1", "2"), tuple[int, ...]) == (1, 2)
    assert validator.validate("active", Status) is Status.ACTIVE
    assert validator.validate({"name": "Ada"}, PlainPayload).name == "Ada"
    assert validator.validate(date(2026, 1, 2), date) == date(2026, 1, 2)
    assert validator.validate("10.5", Decimal) == Decimal("10.5")


def test_modmex_validator_serializes_to_dict_and_json_fallback() -> None:
    class ToDictModel:
        def to_dict(self):
            return {"ok": True}

    validator = ModmexValidator()

    assert validator.serialize(ToDictModel()) == {"ok": True}
    assert validator.dumps({"model": ToDictModel()}) == '{"model":{"ok":true}}'


def test_modmex_validator_reports_tuple_dict_literal_none_and_object_errors() -> None:
    validator = ModmexValidator()

    cases = [
        lambda: validator.validate(None, str, ["body", "name"]),
        lambda: validator.validate(["1"], tuple[int], ["query", "pair"]),
        lambda: validator.validate(("1", "2"), tuple[int], ["query", "pair"]),
        lambda: validator.validate([], dict[str, int], ["body"]),
        lambda: validator.validate("paused", Literal["active"], ["status"]),
        lambda: validator.validate("x", int | bool, ["query", "value"]),
        lambda: validator.validate("x", Payload, ["body"]),
    ]

    for validate in cases:
        try:
            validate()
        except ValidationError as exc:
            assert exc.errors
        else:
            raise AssertionError("Expected validation error")
