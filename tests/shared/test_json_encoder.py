from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum

import pytest

from modmex_lambda.shared.json_encoder import JSONEncoder


class Status(Enum):
    ACTIVE = "active"


@dataclass
class Item:
    name: str
    count: int


class DumpJsonModel:
    def model_dump_json(self) -> str:
        return '{"ok":true}'


def test_json_encoder_handles_supported_custom_values() -> None:
    payload = {
        "dataclass": Item("Ada", 1),
        "enum": Status.ACTIVE,
        "datetime": datetime(2026, 1, 2, 3, 4, 5),
        "date": date(2026, 1, 2),
        "time": time(3, 4, 5),
        "timedelta": timedelta(seconds=90),
        "decimal": Decimal("10.5"),
        "model": DumpJsonModel(),
    }

    assert json.loads(json.dumps(payload, cls=JSONEncoder)) == {
        "dataclass": {"name": "Ada", "count": 1},
        "enum": "active",
        "datetime": "2026-01-02T03:04:05",
        "date": "2026-01-02",
        "time": "03:04:05",
        "timedelta": 90.0,
        "decimal": 10.5,
        "model": '{"ok":true}',
    }


def test_json_encoder_delegates_unsupported_values_to_base_encoder() -> None:
    with pytest.raises(TypeError):
        json.dumps({"value": object()}, cls=JSONEncoder)
