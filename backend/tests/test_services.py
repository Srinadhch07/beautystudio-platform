"""Service validation and CRUD."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.payloads import service_payload

ADMIN = "/api/v1/admin/services"
PUBLIC = "/api/v1/public/services"


def create_service(auth_client: TestClient, **overrides: object) -> dict:
    response = auth_client.post(ADMIN, json=service_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


# --- Validation -------------------------------------------------------------


def test_service_requires_name_and_price(auth_client: TestClient) -> None:
    assert auth_client.post(ADMIN, json={"description": "no name"}).status_code == 422
    assert auth_client.post(ADMIN, json={"name": "Cut"}).status_code == 422


def test_service_rejects_empty_name(auth_client: TestClient) -> None:
    assert auth_client.post(ADMIN, json=service_payload(name="   ")).status_code == 422


def test_service_rejects_negative_price(auth_client: TestClient) -> None:
    assert auth_client.post(ADMIN, json=service_payload(price="-1.00")).status_code == 422


def test_service_rejects_too_many_decimal_places(auth_client: TestClient) -> None:
    assert auth_client.post(ADMIN, json=service_payload(price="10.999")).status_code == 422


def test_service_rejects_non_numeric_price(auth_client: TestClient) -> None:
    assert auth_client.post(ADMIN, json=service_payload(price="free")).status_code == 422


def test_service_rejects_negative_display_order(auth_client: TestClient) -> None:
    assert auth_client.post(ADMIN, json=service_payload(display_order=-1)).status_code == 422


def test_service_rejects_out_of_range_duration(auth_client: TestClient) -> None:
    assert auth_client.post(ADMIN, json=service_payload(duration=0)).status_code == 422
    assert auth_client.post(ADMIN, json=service_payload(duration=5000)).status_code == 422


def test_service_rejects_overlong_name(auth_client: TestClient) -> None:
    assert auth_client.post(ADMIN, json=service_payload(name="x" * 121)).status_code == 422


def test_service_rejects_non_boolean_is_active(auth_client: TestClient) -> None:
    assert auth_client.post(ADMIN, json=service_payload(is_active="yes")).status_code == 422


# --- CRUD -------------------------------------------------------------------


def test_create_service_returns_201_with_string_id(auth_client: TestClient) -> None:
    body = create_service(auth_client)

    assert body["name"] == "Hair Spa"
    assert body["price"] == "49.99"
    assert isinstance(body["id"], str) and len(body["id"]) == 24
    assert body["is_active"] is True
    assert body["created_at"] and body["updated_at"]


def test_read_service(auth_client: TestClient) -> None:
    created = create_service(auth_client)

    response = auth_client.get(f"{ADMIN}/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_read_unknown_service_returns_404(auth_client: TestClient) -> None:
    assert auth_client.get(f"{ADMIN}/665f1b2c9e1d4a3f7c8b9a01").status_code == 404


def test_malformed_id_returns_400(auth_client: TestClient) -> None:
    response = auth_client.get(f"{ADMIN}/not-an-object-id")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"


def test_update_service_partially(auth_client: TestClient) -> None:
    created = create_service(auth_client)

    response = auth_client.patch(f"{ADMIN}/{created['id']}", json={"name": "Hair Ritual"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Hair Ritual"
    assert body["price"] == "49.99"  # untouched
    assert body["updated_at"] >= created["updated_at"]


def test_update_unknown_service_returns_404(auth_client: TestClient) -> None:
    assert (
        auth_client.patch(f"{ADMIN}/665f1b2c9e1d4a3f7c8b9a01", json={"name": "x"}).status_code
        == 404
    )


def test_delete_service_returns_204_then_404(auth_client: TestClient) -> None:
    created = create_service(auth_client)

    assert auth_client.delete(f"{ADMIN}/{created['id']}").status_code == 204
    assert auth_client.get(f"{ADMIN}/{created['id']}").status_code == 404


def test_delete_unknown_service_returns_404(auth_client: TestClient) -> None:
    assert auth_client.delete(f"{ADMIN}/665f1b2c9e1d4a3f7c8b9a01").status_code == 404


def test_activate_and_deactivate(auth_client: TestClient) -> None:
    created = create_service(auth_client)

    hidden = auth_client.patch(f"{ADMIN}/{created['id']}/active", params={"is_active": False})
    assert hidden.status_code == 200
    assert hidden.json()["is_active"] is False

    shown = auth_client.patch(f"{ADMIN}/{created['id']}/active", params={"is_active": True})
    assert shown.json()["is_active"] is True


def test_reorder_services(auth_client: TestClient) -> None:
    first = create_service(auth_client, name="A")
    second = create_service(auth_client, name="B")

    response = auth_client.put(
        f"{ADMIN}/order",
        json={
            "items": [
                {"id": second["id"], "display_order": 0},
                {"id": first["id"], "display_order": 1},
            ]
        },
    )

    assert response.status_code == 200
    assert response.json() == {"updated": 2}

    listing = auth_client.get(f"{ADMIN}").json()
    assert [item["name"] for item in listing["items"]] == ["B", "A"]


def test_reorder_requires_at_least_one_item(auth_client: TestClient) -> None:
    assert auth_client.put(f"{ADMIN}/order", json={"items": []}).status_code == 422


def test_reorder_rejects_invalid_id(auth_client: TestClient) -> None:
    response = auth_client.put(
        f"{ADMIN}/order", json={"items": [{"id": "nope", "display_order": 1}]}
    )

    assert response.status_code == 422


# --- Public visibility ------------------------------------------------------


def test_public_list_hides_inactive_services(auth_client: TestClient) -> None:
    create_service(auth_client, name="Visible")
    hidden = create_service(auth_client, name="Hidden")
    auth_client.patch(f"{ADMIN}/{hidden['id']}/active", params={"is_active": False})

    body = auth_client.get(PUBLIC).json()

    assert body["total"] == 1
    assert [item["name"] for item in body["items"]] == ["Visible"]


def test_public_detail_returns_404_for_inactive_service(auth_client: TestClient) -> None:
    created = create_service(auth_client)
    auth_client.patch(f"{ADMIN}/{created['id']}/active", params={"is_active": False})

    assert auth_client.get(f"{PUBLIC}/{created['id']}").status_code == 404


def test_public_list_is_sorted_by_display_order(auth_client: TestClient) -> None:
    create_service(auth_client, name="Third", display_order=2)
    create_service(auth_client, name="First", display_order=0)
    create_service(auth_client, name="Second", display_order=1)

    body = auth_client.get(PUBLIC).json()

    assert [item["name"] for item in body["items"]] == ["First", "Second", "Third"]


def test_public_pagination(auth_client: TestClient) -> None:
    for index in range(5):
        create_service(auth_client, name=f"Service {index}", display_order=index)

    page = auth_client.get(PUBLIC, params={"skip": 1, "limit": 2}).json()

    assert page["total"] == 5
    assert page["skip"] == 1
    assert page["limit"] == 2
    assert [item["name"] for item in page["items"]] == ["Service 1", "Service 2"]


def test_public_pagination_bounds_are_validated(auth_client: TestClient) -> None:
    assert auth_client.get(PUBLIC, params={"limit": 0}).status_code == 422
    assert auth_client.get(PUBLIC, params={"limit": 5000}).status_code == 422
    assert auth_client.get(PUBLIC, params={"skip": -1}).status_code == 422
