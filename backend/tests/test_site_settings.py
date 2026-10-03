"""Singleton site settings: seeding, replacement, patching and public exposure."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.payloads import settings_payload

ADMIN = "/api/v1/admin/site-settings"
PUBLIC = "/api/v1/public/site-settings"


# --- Seeding ----------------------------------------------------------------


def test_public_read_seeds_settings_from_app_name(auth_client: TestClient) -> None:
    response = auth_client.get(PUBLIC)

    assert response.status_code == 200
    body = response.json()
    assert body["business_name"] == "Beauty Parlour Test"
    assert body["active_theme"] == "rose-elegance"
    assert body["active_font"] == "playfair-lora"
    assert body["opening_hours"] == []


def test_seeding_is_idempotent(auth_client: TestClient) -> None:
    first = auth_client.get(PUBLIC).json()

    assert auth_client.get(PUBLIC).json()["id"] == first["id"]
    assert auth_client.get(ADMIN).json()["id"] == first["id"]


def test_public_settings_never_expose_internal_fields(auth_client: TestClient) -> None:
    body = auth_client.get(PUBLIC).json()

    assert "singleton_key" not in body


# --- Upsert -----------------------------------------------------------------


def test_upsert_replaces_settings(auth_client: TestClient) -> None:
    response = auth_client.put(ADMIN, json=settings_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["business_name"] == "Glow Studio"
    assert body["tagline"] == "Look and feel beautiful"
    assert body["address"]["city"] == "Chennai"
    assert body["email"] == "hello@glowstudio.com"
    assert len(body["opening_hours"]) == 2


def test_upsert_requires_business_name(auth_client: TestClient) -> None:
    payload = settings_payload()
    payload.pop("business_name")

    assert auth_client.put(ADMIN, json=payload).status_code == 422


def test_upsert_rejects_blank_business_name(auth_client: TestClient) -> None:
    assert auth_client.put(ADMIN, json=settings_payload(business_name="   ")).status_code == 422


def test_upsert_rejects_invalid_email(auth_client: TestClient) -> None:
    assert auth_client.put(ADMIN, json=settings_payload(email="not-an-email")).status_code == 422


def test_upsert_rejects_open_day_without_times(auth_client: TestClient) -> None:
    payload = settings_payload(
        opening_hours=[{"day": "monday", "is_closed": False, "open_time": "10:00"}]
    )

    assert auth_client.put(ADMIN, json=payload).status_code == 422


def test_upsert_rejects_close_before_open(auth_client: TestClient) -> None:
    payload = settings_payload(
        opening_hours=[
            {"day": "monday", "is_closed": False, "open_time": "19:00", "close_time": "10:00"}
        ]
    )

    assert auth_client.put(ADMIN, json=payload).status_code == 422


def test_upsert_rejects_non_http_social_link(auth_client: TestClient) -> None:
    assert (
        auth_client.put(ADMIN, json=settings_payload(social_links={"facebook": "nope"})).status_code
        == 422
    )


def test_upsert_is_idempotent_and_keeps_one_document(auth_client: TestClient) -> None:
    auth_client.put(ADMIN, json=settings_payload())

    auth_client.put(ADMIN, json=settings_payload(business_name="Glow Studio 2"))

    assert auth_client.get(ADMIN).json()["business_name"] == "Glow Studio 2"
    assert auth_client.get(PUBLIC).json()["business_name"] == "Glow Studio 2"


# --- Patch ------------------------------------------------------------------


def test_patch_updates_single_field(auth_client: TestClient) -> None:
    auth_client.put(ADMIN, json=settings_payload())

    response = auth_client.patch(ADMIN, json={"tagline": "New tagline"})

    assert response.status_code == 200
    body = response.json()
    assert body["tagline"] == "New tagline"
    assert body["business_name"] == "Glow Studio"  # untouched
    assert body["address"]["city"] == "Chennai"  # untouched


def test_patch_does_not_require_business_name(auth_client: TestClient) -> None:
    auth_client.put(ADMIN, json=settings_payload())

    assert auth_client.patch(ADMIN, json={"phone": "+91 90000 00000"}).status_code == 200


def test_patch_creates_settings_when_absent(auth_client: TestClient) -> None:
    response = auth_client.patch(ADMIN, json={"business_name": "Fresh Parlour"})

    assert response.status_code == 200
    body = response.json()
    assert body["business_name"] == "Fresh Parlour"
    # Defaults must be present, not missing from the stored document.
    assert body["active_theme"] == "rose-elegance"
    assert body["active_font"] == "playfair-lora"


def test_patch_with_empty_body_returns_current_settings(auth_client: TestClient) -> None:
    auth_client.put(ADMIN, json=settings_payload())

    body = auth_client.patch(ADMIN, json={}).json()

    assert body["business_name"] == "Glow Studio"


def test_patch_rejects_blank_business_name(auth_client: TestClient) -> None:
    auth_client.put(ADMIN, json=settings_payload())

    assert auth_client.patch(ADMIN, json={"business_name": "  "}).status_code == 422


def test_patch_rejects_clearing_required_business_name(auth_client: TestClient) -> None:
    auth_client.put(ADMIN, json=settings_payload())

    assert auth_client.patch(ADMIN, json={"business_name": None}).status_code == 422


def test_patch_rejects_breaking_opening_hours(auth_client: TestClient) -> None:
    auth_client.put(ADMIN, json=settings_payload())

    response = auth_client.patch(
        ADMIN,
        json={"opening_hours": [{"day": "monday", "is_closed": False, "open_time": "10:00"}]},
    )

    assert response.status_code == 422


def test_patch_can_clear_optional_field(auth_client: TestClient) -> None:
    auth_client.put(ADMIN, json=settings_payload())

    body = auth_client.patch(ADMIN, json={"tagline": None}).json()

    assert body["tagline"] is None
    assert body["business_name"] == "Glow Studio"


def test_patch_preserves_created_at(auth_client: TestClient) -> None:
    original = auth_client.put(ADMIN, json=settings_payload()).json()

    patched = auth_client.patch(ADMIN, json={"tagline": "Changed"}).json()

    assert patched["created_at"] == original["created_at"]
    assert patched["updated_at"] >= original["updated_at"]


def test_patch_preserves_id(auth_client: TestClient) -> None:
    original = auth_client.put(ADMIN, json=settings_payload()).json()

    assert auth_client.patch(ADMIN, json={"hero_title": "Hi"}).json()["id"] == original["id"]


# --- Consistency between admin and public views -----------------------------


def test_admin_writes_are_reflected_in_public_view(auth_client: TestClient) -> None:
    auth_client.put(ADMIN, json=settings_payload(business_name="Public Name Check"))

    assert auth_client.get(PUBLIC).json()["business_name"] == "Public Name Check"


def test_public_read_after_patch(auth_client: TestClient) -> None:
    auth_client.patch(ADMIN, json={"business_name": "Patched Visible"})

    assert auth_client.get(PUBLIC).json()["business_name"] == "Patched Visible"
