from __future__ import annotations

from unittest.mock import MagicMock

import boto3
import pytest


@pytest.fixture(autouse=True)
def stream_test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STAGE", "test")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setattr(boto3, "resource", lambda *_args, **_kwargs: MagicMock())
    monkeypatch.setattr(boto3, "client", lambda *_args, **_kwargs: MagicMock())
