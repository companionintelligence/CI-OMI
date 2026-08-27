"""
Tests for API authentication

Covers the three things the guard has to get right: /health stays open, every
other route is closed, and an unconfigured deployment fails closed rather than
open.
"""
import pytest
from fastapi.routing import APIRoute, APIWebSocketRoute

from utils import auth

# Paths FastAPI adds for itself, plus the deliberate liveness probe.
UNGUARDED_PATHS = {
    "/health",
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
}


def _all_routes(routes):
    """Flatten the routing table.

    Newer FastAPI wraps each `include_router()` call in a `_IncludedRouter` rather
    than splicing its routes into `app.routes`, so the table has to be walked
    rather than read. `requirements.txt` only pins `fastapi>=0.100.0`, so both
    shapes have to work.
    """
    for route in routes:
        if isinstance(route, (APIRoute, APIWebSocketRoute)):
            yield route
            continue

        nested = getattr(route, "original_router", route)
        if nested is not route or hasattr(nested, "routes"):
            yield from _all_routes(getattr(nested, "routes", []))


def _route_paths(app):
    return {route.path for route in _all_routes(app.routes)}


def _guarded_routes(app):
    """Every application route that is not on the documented open list"""
    return [
        route
        for route in _all_routes(app.routes)
        if route.path not in UNGUARDED_PATHS
    ]


class TestRouteRegistration:
    """The routing table itself"""

    def test_all_routes_register(self, app):
        paths = _route_paths(app)
        assert len(paths) == 29
        assert "/health" in paths
        assert "/api/status" in paths
        assert "/api/config" in paths
        assert "/ws/live" in paths

    def test_every_route_except_health_is_guarded(self, app):
        """A new route must not be able to ship unauthenticated by accident"""
        # Guard against the check going vacuous if route discovery ever breaks.
        # 28 HTTP routes plus /ws/live; /api/events has both a GET and a POST.
        assert len(_guarded_routes(app)) == 29
        unguarded = [
            route.path
            for route in _guarded_routes(app)
            if not any(
                dependency.call in (auth.require_api_key, auth.require_api_key_ws)
                for dependency in route.dependant.dependencies
            )
        ]
        assert unguarded == []

    def test_websocket_uses_the_websocket_guard(self, app):
        """An HTTPException cannot be rendered onto a WebSocket handshake"""
        route = next(r for r in _all_routes(app.routes) if r.path == "/ws/live")
        calls = [dependency.call for dependency in route.dependant.dependencies]
        assert auth.require_api_key_ws in calls
        assert auth.require_api_key not in calls


class TestHealthEndpoint:
    """/health is the one deliberate exception"""

    def test_open_without_a_key(self, client, api_key):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_open_even_when_unconfigured(self, client):
        assert client.get("/health").status_code == 200

    def test_leaks_no_configuration(self, client, api_key):
        assert set(client.get("/health").json()) == {"status"}


class TestGuardedRoutes:
    """The API key check on ordinary HTTP routes"""

    def test_config_update_rejected_without_a_key(self, client, api_key):
        response = client.put("/api/config", json={"video_fps": 30})
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or missing API key"

    def test_config_update_rejected_with_a_wrong_key(self, client, api_key):
        response = client.put(
            "/api/config",
            json={"video_fps": 30},
            headers={auth.API_KEY_HEADER_NAME: "not-the-key"},
        )
        assert response.status_code == 401

    def test_config_update_accepted_with_the_right_key(self, client, api_key):
        response = client.put(
            "/api/config",
            json={"video_fps": 30},
            headers={auth.API_KEY_HEADER_NAME: api_key},
        )
        assert response.status_code == 200
        assert response.json()["config"]["video_fps"] == 30

    @pytest.mark.parametrize(
        "method, path",
        [
            ("get", "/api/status"),
            ("get", "/api/devices"),
            ("get", "/api/events"),
            ("post", "/api/events"),
            ("post", "/api/start"),
            ("post", "/api/stop"),
            ("get", "/api/storage/audio"),
            ("delete", "/api/storage/audio/x.wav"),
            ("post", "/api/webhooks/conversation"),
            ("post", "/api/webhooks/transcript"),
            ("get", "/api/events/transcripts"),
        ],
    )
    def test_representative_routes_reject_anonymous_callers(
        self, client, api_key, method, path
    ):
        response = client.request(method, path, json={})
        assert response.status_code == 401

    def test_header_name_is_case_insensitive(self, client, api_key):
        response = client.get("/api/devices", headers={"x-api-key": api_key})
        assert response.status_code == 200


class TestFailsClosed:
    """With no key configured the service refuses, it does not wave requests through"""

    def test_mutating_route_refused_when_unconfigured(self, client):
        response = client.put("/api/config", json={"video_fps": 30})
        assert response.status_code == 503
        assert auth.API_KEY_ENV_VAR in response.json()["detail"]

    def test_reading_route_refused_when_unconfigured(self, client):
        assert client.get("/api/events").status_code == 503

    def test_no_key_is_accepted_when_unconfigured(self, client):
        """An empty configured key must not match an empty presented key"""
        for presented in ("", " ", "anything"):
            response = client.put(
                "/api/config",
                json={"video_fps": 30},
                headers={auth.API_KEY_HEADER_NAME: presented},
            )
            assert response.status_code == 503

    def test_whitespace_only_key_counts_as_unconfigured(self, client, monkeypatch):
        monkeypatch.setenv(auth.API_KEY_ENV_VAR, "   ")
        assert client.get("/api/events").status_code == 503


class TestWebSocket:
    """/ws/live broadcasts every transcription and config change"""

    def test_handshake_rejected_without_a_key(self, client, api_key):
        from starlette.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect) as excinfo:
            with client.websocket_connect("/ws/live"):
                pass
        assert excinfo.value.code == 1008

    def test_handshake_rejected_with_a_wrong_key(self, client, api_key):
        from starlette.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "/ws/live", headers={auth.API_KEY_HEADER_NAME: "not-the-key"}
            ):
                pass

    def test_handshake_accepted_with_the_header(self, client, api_key):
        with client.websocket_connect(
            "/ws/live", headers={auth.API_KEY_HEADER_NAME: api_key}
        ) as websocket:
            assert websocket.receive_json()["type"] == "status"

    def test_handshake_accepted_with_the_query_parameter(self, client, api_key):
        """Browsers cannot set headers on a WebSocket handshake"""
        with client.websocket_connect(
            f"/ws/live?{auth.API_KEY_QUERY_PARAM}={api_key}"
        ) as websocket:
            assert websocket.receive_json()["type"] == "status"


class TestKeyComparison:
    """The comparison itself"""

    def test_matching_key_accepted(self):
        assert auth._matches("s3cret", "s3cret") is True

    def test_differing_key_rejected(self):
        assert auth._matches("s3cret", "s3crey") is False

    def test_empty_and_none_rejected(self):
        assert auth._matches("", "s3cret") is False
        assert auth._matches(None, "s3cret") is False

    def test_non_ascii_key_does_not_raise(self):
        """secrets.compare_digest rejects non-ASCII str, so bytes are compared"""
        assert auth._matches("kéy", "kéy") is True
        assert auth._matches("kéy", "key") is False
