"""Lambda Web Adapter resolver for MCP streaming applications."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from typing import Any, Callable

from modmex_lambda.logging import Logger
from modmex_lambda.mcp.transport import MCPStreamingHttpTransport


class LambdaWebAdapterResolver:
    """Expose an MCP server through Lambda Web Adapter's HTTP port.

    Application code only registers capabilities and calls ``include_mcp``;
    HTTP parsing, streaming, and disconnect handling remain in the library.
    """

    def __init__(self, *, host: str = "0.0.0.0", port: int | None = None, health_path: str = "/health", max_body_bytes: int = 1_048_576, allowed_origins: list[str] | None = None, logger: Logger | None = None) -> None:
        if max_body_bytes <= 0:
            raise ValueError("max_body_bytes must be positive")
        self.host = host
        self.port = port or int(os.environ.get("PORT", "8080"))
        self.health_path = health_path
        self.max_body_bytes = max_body_bytes
        self.allowed_origins = allowed_origins
        self.logger = logger or Logger(service=os.getenv('SERVICE', 'lambda-web-adapter'))
        self._routes: dict[str, Any] = {}
        self._middlewares: list[Callable[..., Any]] = []

    def middleware(self, func: Callable[..., Any] | None = None) -> Any:
        """Register HTTP middleware with ``middleware(request, next)``."""
        if func is None:
            def decorator(middleware: Callable[..., Any]) -> Callable[..., Any]:
                self._middlewares.append(middleware)
                return middleware
            return decorator
        self._middlewares.append(func)
        return func

    def include_mcp(self, server: Any, *, path: str = "/mcp") -> None:
        self._routes[path] = MCPStreamingHttpTransport(server, allowed_origins=self.allowed_origins)

    @property
    def handler(self) -> "LambdaWebAdapterHandler":
        """Return the unified application entrypoint.

        The returned object is consumed by the generated Lambda Web Adapter
        launcher in streaming deployments.  Keeping the public value named
        ``handler`` makes the application contract identical to a regular
        Lambda application while the launcher remains an implementation
        detail of the deployment plugin.
        """
        return LambdaWebAdapterHandler(self)

    def run(self) -> None:
        resolver = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                resolver._handle(self)

            def do_GET(self) -> None:
                if self.path == resolver.health_path:
                    resolver._write_json(self, 200, {"status": "ok"})
                else:
                    self.send_error(404)

            def log_message(self, format: str, *args: object) -> None:
                resolver.logger.debug("http request", request=format % args)

        server = ThreadingHTTPServer((self.host, self.port), Handler)
        server.daemon_threads = True
        self.logger.info("Lambda Web Adapter server listening", host=self.host, port=self.port)
        try:
            server.serve_forever()
        finally:
            server.server_close()

    def _handle(self, handler: BaseHTTPRequestHandler) -> None:
        transport = self._routes.get(handler.path)
        if transport is None:
            handler.send_error(404)
            return
        try:
            length = int(handler.headers.get("Content-Length", "0"))
            if length < 0 or length > self.max_body_bytes:
                self._write_json(handler, 413, {"error": "Request body is too large"})
                return
            payload = json.loads(handler.rfile.read(length))
            request = SimpleNamespace(
                json_body=payload,
                headers={key.lower(): value for key, value in handler.headers.items()},
                context={},
            )
            response = self._run_middlewares(request, lambda: transport.handle(request))
            handler.send_response(response.status_code)
            handler.send_header("Content-Type", response.content_type)
            for name, value in response.headers.items():
                handler.send_header(name, value)
            handler.end_headers()
            for event in response.body:
                handler.wfile.write(event.encode())
                handler.wfile.flush()
            handler.close_connection = True
        except (BrokenPipeError, ConnectionResetError, OSError) as exc:
            if "response" in locals() and response.cancellation_token is not None:
                response.cancellation_token.cancel()
            self.logger.info("MCP stream cancelled", error=str(exc))
        except (ValueError, json.JSONDecodeError) as exc:
            self._write_json(handler, 400, {"error": str(exc)})

    def _run_middlewares(self, request: Any, endpoint: Callable[[], Any]) -> Any:
        def invoke(index: int) -> Any:
            if index == len(self._middlewares):
                return endpoint()
            middleware = self._middlewares[index]
            return middleware(request, lambda: invoke(index + 1))
        return invoke(0)

    @staticmethod
    def _write_json(handler: BaseHTTPRequestHandler, status: int, body: dict[str, str]) -> None:
        encoded = json.dumps(body).encode()
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(encoded)))
        handler.end_headers()
        handler.wfile.write(encoded)


class LambdaWebAdapterHandler:
    """Callable application entrypoint used by Lambda Web Adapter."""

    def __init__(self, resolver: LambdaWebAdapterResolver) -> None:
        self._resolver = resolver

    def run(self) -> None:
        """Start the HTTP application consumed by Lambda Web Adapter."""
        self._resolver.run()

    def __call__(self, event: dict[str, Any], context: object) -> Any:
        """Fail clearly when used as a normal Lambda handler.

        Lambda Web Adapter applications are HTTP processes, not API Gateway
        event handlers.  The callable shape is intentionally present so the
        same ``handler = app.handler`` contract can be shared with regular
        Modmex applications; the streaming launcher calls ``run()``.
        """
        raise RuntimeError(
            "LambdaWebAdapterResolver.handler must be started with handler.run(); "
            "it cannot process a Lambda event directly"
        )
