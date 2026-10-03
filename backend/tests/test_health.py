"""Health endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app": "Beauty Parlour Test",
        "version": "0.0.0-test",
        "environment": "development",
    }


def test_root_exposes_health_path(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["health"] == "/api/health"


def test_unknown_route_returns_404(client: TestClient) -> None:
    assert client.get("/api/does-not-exist").status_code == 404


def test_cors_preflight_is_allowed_for_configured_origin(client: TestClient) -> None:
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_preflight_is_denied_for_unknown_origin(client: TestClient) -> None:
    response = client.options(
        "/api/health",
        headers={
            "Origin": "https://not-allowed.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers


def test_health_response_never_contains_credentials(client: TestClient) -> None:
    body = client.get("/api/health").text

    for secret in ("test-secret-value", "test-access-key-id", "mongodb://"):
        assert secret not in body
