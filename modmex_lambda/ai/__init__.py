"""Optional serverless adapters for modmex-ai.

Install ``modmex-ai`` alongside ``modmex-lambda`` when using this namespace.
The dependency is imported only when an adapter is requested.
"""

from importlib import import_module
from typing import Any

__all__ = ["DynamoDbDurableSessionStore", "DynamoDbFlowStateStore"]


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module("modmex_lambda.ai.dynamodb"), name)
