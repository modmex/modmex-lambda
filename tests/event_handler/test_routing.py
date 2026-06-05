from __future__ import annotations

from modmex_lambda.event_handler.routing import Router


def test_router_matches_static_routes_by_method() -> None:
    router = Router()

    def handler():
        return {"ok": True}

    router.route("/ping", method="GET")(handler)

    route, params, allowed_methods = router.match("GET", "/ping")

    assert route is not None
    assert route.handler is handler
    assert params == {}
    assert allowed_methods == set()


def test_router_matches_dynamic_routes_and_reports_allowed_methods() -> None:
    router = Router()

    def handler(user_id: str):
        return {"user_id": user_id}

    router.route("/users/<user_id>", method="GET")(handler)

    route, params, allowed_methods = router.match("GET", "/users/42")
    missing_method, missing_params, missing_allowed_methods = router.match("POST", "/users/42")

    assert route is not None
    assert params == {"user_id": "42"}
    assert allowed_methods == set()
    assert missing_method is None
    assert missing_params == {}
    assert missing_allowed_methods == {"GET"}


def test_router_matches_any_routes_for_static_paths() -> None:
    router = Router()

    def handler():
        return {"ok": True}

    router.route("/proxy", method="ANY")(handler)

    route, params, allowed_methods = router.match("PATCH", "/proxy")

    assert route is not None
    assert params == {}
    assert allowed_methods == set()


def test_router_include_router_preserves_route_metadata() -> None:
    child = Router()
    parent = Router()

    def handler():
        return {"ok": True}

    child.route("/health", method="GET", cache_control="max-age=60", compress=True)(handler)
    parent.include_router(child, prefix="/api")

    route, _, _ = parent.match("GET", "/api/health")

    assert route is not None
    assert route.handler is handler
    assert route.cache_control == "max-age=60"
    assert route.compress is True
