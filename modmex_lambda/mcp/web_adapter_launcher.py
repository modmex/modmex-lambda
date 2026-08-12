"""Launch a configured Modmex Lambda Web Adapter application."""

from __future__ import annotations

import importlib
import os

from modmex_lambda.mcp.web_adapter import LambdaWebAdapterHandler


def main() -> None:
    module_name = os.environ.get("MCP_HANDLER_MODULE")
    attribute_name = os.environ.get("MCP_HANDLER_ATTRIBUTE", "handler")
    if not module_name:
        raise RuntimeError("MCP_HANDLER_MODULE is required")

    module = importlib.import_module(module_name)
    try:
        handler = getattr(module, attribute_name)
    except AttributeError as exc:
        raise RuntimeError(
            f"MCP handler '{module_name}.{attribute_name}' was not found"
        ) from exc

    if not isinstance(handler, LambdaWebAdapterHandler):
        raise TypeError(
            f"MCP handler '{module_name}.{attribute_name}' must be a "
            "LambdaWebAdapterHandler for streaming deployments"
        )
    handler.run()


if __name__ == "__main__":
    main()
