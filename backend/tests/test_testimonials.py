"""Testimonial submission, moderation workflow and public visibility rules."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.payloads import review_payload

ADMIN = "/api/v1/admin/testimonials"
PUBLIC = "/api/v1/public/testimonials"


def submit(auth_client: TestClient, **overrides: object) -> dict:
    response = auth_client.post(PUBLIC, json=review_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def moderate(auth_client: TestClient, testimonial_id: str, **body: object) -> dict:
    response = auth_client.patch(f"{ADMIN}/{testimonial_id}/moderate", json=body)
    assert response.status_code == 200, response.text
    return response.json()


# --- Validation -------------------------------------------------------------


def test_testimonial_requires_name_content_and_rating(auth_client: TestClient) -> None:
    assert (
        auth_client.post(PUBLIC, json={"customer_name": "A", "content": "Nice"}).status_code == 422
    )
    assert auth_client.post(PUBLIC, json={"customer_name": "A", "rating": 5}).status_code == 422
    assert auth_client.post(PUBLIC, json={"content": "Nice", "rating": 5}).status_code == 422


def test_testimonial_rejects_out_of_range_rating(auth_client: TestClient) -> None:
    assert auth_client.post(PUBLIC, json=review_payload(rating=0)).status_code == 422
    assert auth_client.post(PUBLIC, json=review_payload(rating=6)).status_code == 422


def test_testimonial_rejects_non_integer_rating(auth_client: TestClient) -> None:
    assert auth_client.post(PUBLIC, json=review_payload(rating=4.5)).status_code == 422
    assert auth_client.post(PUBLIC, json=review_payload(rating="five")).status_code == 422


def test_testimonial_rejects_blank_content(auth_client: TestClient) -> None:
    assert auth_client.post(PUBLIC, json=review_payload(content="   ")).status_code == 422


def test_testimonial_rejects_overlong_name(auth_client: TestClient) -> None:
    assert auth_client.post(PUBLIC, json=review_payload(customer_name="x" * 121)).status_code == 422


# --- Submission defaults ----------------------------------------------------


def test_submitted_testimonial_is_pending_and_hidden(auth_client: TestClient) -> None:
    created = submit(auth_client)

    # Public response deliberately omits moderation state.
    assert "status" not in created
    assert "is_visible" not in created

    stored = auth_client.get(f"{ADMIN}/{created['id']}").json()
    assert stored["status"] == "pending"
    assert stored["is_visible"] is False


def test_submitted_testimonial_is_absent_from_public_list(auth_client: TestClient) -> None:
    submit(auth_client)

    assert auth_client.get(PUBLIC).json()["total"] == 0


def test_submitted_testimonial_detail_is_not_publicly_readable(auth_client: TestClient) -> None:
    created = submit(auth_client)

    assert auth_client.get(f"{PUBLIC}/{created['id']}").status_code == 404


# --- Moderation -------------------------------------------------------------


def test_approve_and_publish_makes_testimonial_public(auth_client: TestClient) -> None:
    created = submit(auth_client)

    moderate(auth_client, created["id"], status="approved", is_visible=True)

    body = auth_client.get(PUBLIC).json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == created["id"]
    assert "status" not in body["items"][0]


def test_approved_but_not_visible_stays_hidden(auth_client: TestClient) -> None:
    created = submit(auth_client)

    moderate(auth_client, created["id"], status="approved", is_visible=False)

    assert auth_client.get(PUBLIC).json()["total"] == 0
    assert auth_client.get(f"{PUBLIC}/{created['id']}").status_code == 404


def test_visible_but_pending_stays_hidden(auth_client: TestClient) -> None:
    """ "Visible but not approved" is a contradictory state and is rejected."""
    created = submit(auth_client)

    response = auth_client.patch(
        f"{ADMIN}/{created['id']}/moderate", json={"status": "pending", "is_visible": True}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
    # Nothing was published.
    assert auth_client.get(PUBLIC).json()["total"] == 0


def test_moderation_rejects_unknown_status(auth_client: TestClient) -> None:
    created = submit(auth_client)

    response = auth_client.patch(f"{ADMIN}/{created['id']}/moderate", json={"status": "spam"})

    assert response.status_code == 422


def test_moderation_rejects_invalid_rating(auth_client: TestClient) -> None:
    created = submit(auth_client)

    response = auth_client.patch(f"{ADMIN}/{created['id']}/moderate", json={"rating": 9})

    assert response.status_code == 422


def test_moderation_requires_at_least_one_field(auth_client: TestClient) -> None:
    created = submit(auth_client)

    assert auth_client.patch(f"{ADMIN}/{created['id']}/moderate", json={}).status_code == 422


def test_moderation_of_unknown_testimonial_returns_404(auth_client: TestClient) -> None:
    response = auth_client.patch(
        f"{ADMIN}/665f1b2c9e1d4a3f7c8b9a01/moderate", json={"status": "approved"}
    )

    assert response.status_code == 404


def test_moderation_can_reject_published_testimonial(auth_client: TestClient) -> None:
    created = submit(auth_client)
    moderate(auth_client, created["id"], status="approved", is_visible=True)

    moderate(auth_client, created["id"], status="rejected", is_visible=False)

    assert auth_client.get(PUBLIC).json()["total"] == 0


# --- Admin listing ----------------------------------------------------------


def test_admin_list_can_filter_by_status(auth_client: TestClient) -> None:
    first = submit(auth_client, customer_name="Pending One")
    second = submit(auth_client, customer_name="Pending Two")
    approved = submit(auth_client, customer_name="Approved One")
    moderate(auth_client, approved["id"], status="approved", is_visible=True)

    pending = auth_client.get(ADMIN, params={"status": "pending"}).json()
    assert pending["total"] == 2
    assert {item["id"] for item in pending["items"]} == {first["id"], second["id"]}

    approved_page = auth_client.get(ADMIN, params={"status": "approved"}).json()
    assert approved_page["total"] == 1
    assert approved_page["items"][0]["id"] == approved["id"]


def test_admin_list_rejects_invalid_status_filter(auth_client: TestClient) -> None:
    assert auth_client.get(ADMIN, params={"status": "bogus"}).status_code == 422


def test_admin_list_shows_moderation_fields(auth_client: TestClient) -> None:
    submit(auth_client)

    item = auth_client.get(ADMIN).json()["items"][0]

    assert item["status"] == "pending"
    assert item["is_visible"] is False


def test_admin_create_can_publish_immediately(auth_client: TestClient) -> None:
    response = auth_client.post(
        ADMIN, json=review_payload(customer_name="Featured", status="approved", is_visible=True)
    )

    assert response.status_code == 201
    assert response.json()["status"] == "approved"
    assert auth_client.get(PUBLIC).json()["total"] == 1


def test_public_list_supports_pagination(auth_client: TestClient) -> None:
    created = [submit(auth_client, customer_name=f"Guest {index}") for index in range(3)]
    for item in created:
        moderate(auth_client, item["id"], status="approved", is_visible=True)

    page = auth_client.get(PUBLIC, params={"skip": 1, "limit": 1}).json()

    assert page["total"] == 3
    assert page["skip"] == 1
    assert page["limit"] == 1
    assert len(page["items"]) == 1


def test_delete_testimonial(auth_client: TestClient) -> None:
    created = submit(auth_client)

    assert auth_client.delete(f"{ADMIN}/{created['id']}").status_code == 204
    assert auth_client.get(f"{ADMIN}/{created['id']}").status_code == 404


# --- Editing ----------------------------------------------------------------


def test_admin_can_edit_testimonial_content(auth_client: TestClient) -> None:
    created = submit(auth_client, content="Worth it.", rating=3)

    response = auth_client.patch(
        f"{ADMIN}/{created['id']}",
        json={"content": "Corrected wording.", "rating": 5},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["content"] == "Corrected wording."
    assert body["rating"] == 5


def test_edit_preserves_moderation_state(auth_client: TestClient) -> None:
    """Editing copy must not silently publish or unpublish a testimonial."""
    created = submit(auth_client)
    moderate(auth_client, created["id"], status="approved", is_visible=True)

    body = auth_client.patch(f"{ADMIN}/{created['id']}", json={"content": "Edited."}).json()

    assert body["content"] == "Edited."
    assert body["status"] == "approved"
    assert body["is_visible"] is True


def test_edit_rejects_invalid_rating(auth_client: TestClient) -> None:
    created = submit(auth_client)

    assert auth_client.patch(f"{ADMIN}/{created['id']}", json={"rating": 9}).status_code == 422
    assert auth_client.patch(f"{ADMIN}/{created['id']}", json={"rating": 0}).status_code == 422


def test_edit_rejects_blank_content(auth_client: TestClient) -> None:
    created = submit(auth_client)

    assert auth_client.patch(f"{ADMIN}/{created['id']}", json={"content": "  "}).status_code == 422


def test_edit_unknown_testimonial_returns_404(auth_client: TestClient) -> None:
    assert auth_client.patch(f"{ADMIN}/{'0' * 24}", json={"content": "x"}).status_code == 404


# --- A customer cannot approve themselves ------------------------------------


def test_submission_cannot_self_approve(auth_client: TestClient) -> None:
    """Moderation fields sent by a customer must never reach the document.

    The submission payload has no moderation fields, and unknown keys are dropped
    rather than stored, so there is no way to smuggle ``status`` or
    ``is_visible`` through the public endpoint.
    """
    response = auth_client.post(
        PUBLIC,
        json={
            **review_payload(),
            "status": "approved",
            "is_visible": True,
            "moderator_notes": "trust me",
        },
    )

    assert response.status_code == 201, response.text

    stored = auth_client.get(ADMIN).json()["items"][0]
    assert stored["status"] == "pending"
    assert stored["is_visible"] is False
    assert auth_client.get(PUBLIC).json()["total"] == 0


def test_customer_cannot_call_the_moderation_endpoint(anonymous_client: TestClient) -> None:
    """Approving requires an admin session, not merely knowing the id."""
    created = submit(anonymous_client)

    response = anonymous_client.patch(
        f"{ADMIN}/{created['id']}/moderate", json={"status": "approved", "is_visible": True}
    )

    assert response.status_code == 401
    assert anonymous_client.get(PUBLIC).json()["total"] == 0


def test_customer_cannot_edit_a_published_testimonial(anonymous_client: TestClient) -> None:
    created = submit(anonymous_client)

    assert anonymous_client.patch(f"{ADMIN}/{created['id']}", json={"rating": 5}).status_code == 401
    assert anonymous_client.delete(f"{ADMIN}/{created['id']}").status_code == 401


def test_public_response_never_exposes_moderation_fields(auth_client: TestClient) -> None:
    created = submit(auth_client)
    moderate(auth_client, created["id"], status="approved", is_visible=True)

    body = auth_client.get(f"{PUBLIC}/{created['id']}").json()

    for internal in ("status", "is_visible", "moderator_notes", "moderated_at", "moderated_by"):
        assert internal not in body
    assert set(body) == {"id", "customer_name", "content", "rating", "created_at"}
