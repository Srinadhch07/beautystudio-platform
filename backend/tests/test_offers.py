"""Offer CRUD, price handling and the validity window rules."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.payloads import offer_payload

ADMIN = "/api/v1/admin/offers"
PUBLIC = "/api/v1/public/offers"


def create_offer(auth_client: TestClient, **overrides: object) -> dict:
    response = auth_client.post(ADMIN, json=offer_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


# --- Validation -------------------------------------------------------------


def test_offer_requires_title_and_price(auth_client: TestClient) -> None:
    assert auth_client.post(ADMIN, json={"price": "10.00"}).status_code == 422
    assert auth_client.post(ADMIN, json={"title": "Deal"}).status_code == 422


def test_offer_rejects_negative_price(auth_client: TestClient) -> None:
    assert auth_client.post(ADMIN, json=offer_payload(price="-5.00")).status_code == 422


def test_offer_rejects_non_numeric_price(auth_client: TestClient) -> None:
    assert auth_client.post(ADMIN, json=offer_payload(price="call for price")).status_code == 422


def test_offer_rejects_too_many_decimals(auth_client: TestClient) -> None:
    assert auth_client.post(ADMIN, json=offer_payload(price="10.001")).status_code == 422


def test_offer_rejects_blank_title(auth_client: TestClient) -> None:
    assert auth_client.post(ADMIN, json=offer_payload(title="  ")).status_code == 422


def test_offer_rejects_inverted_validity_window(auth_client: TestClient) -> None:
    response = auth_client.post(
        ADMIN,
        json=offer_payload(valid_from="2026-06-01T00:00:00Z", valid_until="2026-01-01T00:00:00Z"),
    )

    assert response.status_code == 422


def test_offer_accepts_equal_validity_bounds(auth_client: TestClient) -> None:
    stamp = "2026-06-01T00:00:00Z"
    response = auth_client.post(ADMIN, json=offer_payload(valid_from=stamp, valid_until=stamp))

    assert response.status_code == 201


# --- CRUD -------------------------------------------------------------------


def test_create_offer_serialises_prices_as_strings(auth_client: TestClient) -> None:
    created = create_offer(auth_client)

    assert created["price"] == "499.00"
    assert created["original_price"] == "650.00"


def test_create_offer_without_original_price(auth_client: TestClient) -> None:
    created = create_offer(auth_client, original_price=None)

    assert created["original_price"] is None


def test_read_offer(auth_client: TestClient) -> None:
    created = create_offer(auth_client)

    assert auth_client.get(f"{ADMIN}/{created['id']}").json()["id"] == created["id"]


def test_read_unknown_offer_returns_404(auth_client: TestClient) -> None:
    assert auth_client.get(f"{ADMIN}/665f1b2c9e1d4a3f7c8b9a01").status_code == 404


def test_update_offer(auth_client: TestClient) -> None:
    created = create_offer(auth_client)

    response = auth_client.patch(f"{ADMIN}/{created['id']}", json={"title": "Autumn Deal"})

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Autumn Deal"
    assert body["price"] == "499.00"


def test_update_offer_rejects_negative_price(auth_client: TestClient) -> None:
    created = create_offer(auth_client)

    assert auth_client.patch(f"{ADMIN}/{created['id']}", json={"price": "-1.00"}).status_code == 422


def test_update_rejects_window_contradicting_stored_value(auth_client: TestClient) -> None:
    """A single field patch can still break a two-field rule."""
    created = create_offer(auth_client, valid_from="2026-01-01T00:00:00Z")

    response = auth_client.patch(
        f"{ADMIN}/{created['id']}", json={"valid_until": "2025-12-01T00:00:00Z"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_update_rejects_window_contradiction_inside_one_patch(auth_client: TestClient) -> None:
    created = create_offer(auth_client)

    response = auth_client.patch(
        f"{ADMIN}/{created['id']}",
        json={"valid_from": "2026-06-01T00:00:00Z", "valid_until": "2026-01-01T00:00:00Z"},
    )

    assert response.status_code == 422


def test_update_offer_with_consistent_window_succeeds(auth_client: TestClient) -> None:
    created = create_offer(auth_client, valid_from="2026-01-01T00:00:00Z")

    response = auth_client.patch(
        f"{ADMIN}/{created['id']}", json={"valid_until": "2026-03-01T00:00:00Z"}
    )

    assert response.status_code == 200
    assert response.json()["valid_until"].startswith("2026-03-01")


def test_update_unknown_offer_returns_404(auth_client: TestClient) -> None:
    response = auth_client.patch(
        f"{ADMIN}/665f1b2c9e1d4a3f7c8b9a01",
        json={"valid_until": "2020-01-01T00:00:00Z"},
        headers={"X-Test": "1"},
    )

    assert response.status_code == 404


def test_delete_offer(auth_client: TestClient) -> None:
    created = create_offer(auth_client)

    assert auth_client.delete(f"{ADMIN}/{created['id']}").status_code == 204
    assert auth_client.get(f"{ADMIN}/{created['id']}").status_code == 404


def test_reorder_offers(auth_client: TestClient) -> None:
    first = create_offer(auth_client, title="A")
    second = create_offer(auth_client, title="B")

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
    assert [item["title"] for item in auth_client.get(ADMIN).json()["items"]] == ["B", "A"]


# --- Public visibility ------------------------------------------------------


def test_public_list_hides_inactive_offers(auth_client: TestClient) -> None:
    create_offer(auth_client, title="Live")
    hidden = create_offer(auth_client, title="Expired")
    auth_client.patch(f"{ADMIN}/{hidden['id']}/active", params={"is_active": False})

    body = auth_client.get(PUBLIC).json()

    assert body["total"] == 1
    assert body["items"][0]["title"] == "Live"


def test_public_detail_returns_404_for_inactive_offer(auth_client: TestClient) -> None:
    created = create_offer(auth_client)
    auth_client.patch(f"{ADMIN}/{created['id']}/active", params={"is_active": False})

    assert auth_client.get(f"{PUBLIC}/{created['id']}").status_code == 404


# --- Validity window ---------------------------------------------------------
#
# The public API serves only *current* offers. An offer whose window has closed
# disappears on its own, so nobody has to remember to deactivate it on the last
# day. Deactivating stays available as the explicit "hide this now" override.


def test_public_list_hides_an_offer_whose_window_has_not_opened(auth_client: TestClient) -> None:
    create_offer(auth_client, title="Live")
    create_offer(
        auth_client,
        title="Future",
        valid_from="2099-01-01T00:00:00Z",
        valid_until="2099-12-31T00:00:00Z",
    )

    body = auth_client.get(PUBLIC).json()

    assert [item["title"] for item in body["items"]] == ["Live"]
    assert body["total"] == 1


def test_public_list_hides_an_offer_whose_window_has_closed(auth_client: TestClient) -> None:
    create_offer(auth_client, title="Live")
    create_offer(
        auth_client,
        title="Past",
        valid_from="2020-01-01T00:00:00Z",
        valid_until="2020-12-31T00:00:00Z",
    )

    body = auth_client.get(PUBLIC).json()

    assert [item["title"] for item in body["items"]] == ["Live"]
    assert body["total"] == 1


@pytest.mark.parametrize(
    ("valid_from", "valid_until"),
    [
        (None, None),  # open ended
        ("2020-01-01T00:00:00Z", None),  # started, no end
        (None, "2099-12-31T00:00:00Z"),  # no start, still running
        ("2020-01-01T00:00:00Z", "2099-12-31T00:00:00Z"),  # currently running
    ],
)
def test_public_list_serves_every_current_window(
    auth_client: TestClient, valid_from: str | None, valid_until: str | None
) -> None:
    """A missing bound means "unbounded on that side", not "excluded"."""
    create_offer(auth_client, title="Current", valid_from=valid_from, valid_until=valid_until)

    body = auth_client.get(PUBLIC).json()

    assert [item["title"] for item in body["items"]] == ["Current"]


def test_public_detail_returns_404_for_an_expired_offer(auth_client: TestClient) -> None:
    """A closed offer must not be distinguishable from a missing one."""
    created = create_offer(
        auth_client,
        valid_from="2020-01-01T00:00:00Z",
        valid_until="2020-12-31T00:00:00Z",
    )

    assert auth_client.get(f"{PUBLIC}/{created['id']}").status_code == 404


def test_admin_list_still_shows_expired_offers(auth_client: TestClient) -> None:
    """Expiry hides an offer from the public site, not from its own admin."""
    create_offer(auth_client, valid_from="2020-01-01T00:00:00Z", valid_until="2020-12-31T00:00:00Z")

    assert auth_client.get(ADMIN).json()["total"] == 1


def test_public_list_ignores_inactive_even_when_current(auth_client: TestClient) -> None:
    """Deactivation wins over the validity window in both directions."""
    created = create_offer(auth_client, title="Paused")
    auth_client.patch(f"{ADMIN}/{created['id']}/active", params={"is_active": False})

    assert auth_client.get(PUBLIC).json()["total"] == 0
