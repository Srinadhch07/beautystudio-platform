"""The public error contract.

Every failure must be a JSON body of the form
``{"error": {"code": ..., "message": ..., "details": ...}}`` and must never leak
driver internals, stack traces or configuration values.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.payloads import service_payload

ADMIN_SERVICES = "/api/v1/admin/services"
ADMIN_OFFERS = "/api/v1/admin/offers"
ADMIN_GALLERY = "/api/v1/admin/gallery"
ADMIN_TESTIMONIALS = "/api/v1/admin/testimonials"


def create_service(auth_client: TestClient) -> dict:
    return auth_client.post(ADMIN_SERVICES, json=service_payload()).json()


def test_health_endpoint_still_works(auth_client: TestClient) -> None:
    response = auth_client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_404_body_follows_error_contract(auth_client: TestClient) -> None:
    response = auth_client.get(f"{ADMIN_SERVICES}/665f1b2c9e1d4a3f7c8b9a01")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert "message" in body["error"]
    assert "Traceback" not in response.text


def test_malformed_id_is_400_not_500(auth_client: TestClient) -> None:
    for path in (
        f"{ADMIN_SERVICES}/abc",
        f"{ADMIN_GALLERY}/abc",
        f"{ADMIN_OFFERS}/abc",
        f"{ADMIN_TESTIMONIALS}/abc",
    ):
        response = auth_client.get(path)
        assert response.status_code == 400, path
        assert response.json()["error"]["code"] == "bad_request", path


def test_unknown_route_returns_json_error(auth_client: TestClient) -> None:
    response = auth_client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_method_not_allowed_returns_json_error(auth_client: TestClient) -> None:
    response = auth_client.delete("/api/v1/public/services")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


def test_validation_error_lists_fields_without_values(auth_client: TestClient) -> None:
    response = auth_client.post(ADMIN_SERVICES, json={"name": "X", "price": "secret-ish-value"})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"

    details = body["error"]["details"]
    assert details and all({"location", "message", "type"} <= set(item) for item in details)

    # The rejected input must not be echoed back.
    assert "secret-ish-value" not in response.text


def test_domain_validation_error_uses_same_contract(auth_client: TestClient) -> None:
    created = auth_client.post(
        ADMIN_OFFERS,
        json={
            "title": "Deal",
            "price": "10.00",
            "valid_from": "2026-01-01T00:00:00Z",
        },
    ).json()

    response = auth_client.patch(
        f"{ADMIN_OFFERS}/{created['id']}", json={"valid_until": "2025-01-01T00:00:00Z"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_error_responses_are_json_content_type(auth_client: TestClient) -> None:
    response = auth_client.get(f"{ADMIN_SERVICES}/abc")

    assert response.headers["content-type"].startswith("application/json")


def test_openapi_schema_is_generated(auth_client: TestClient) -> None:
    schema = auth_client.get("/openapi.json").json()

    assert "paths" in schema
    assert "/api/v1/public/services" in schema["paths"]
    assert "/api/v1/admin/services" in schema["paths"]
    assert "/api/v1/admin/site-settings" in schema["paths"]
