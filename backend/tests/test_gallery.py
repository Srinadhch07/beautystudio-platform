"""Gallery CRUD and the rule that hides internal ``s3_key`` from the public API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.media import build_object_key
from tests.conftest import IMAGE_BYTES, FakeS3Client
from tests.payloads import gallery_payload

ADMIN = "/api/v1/admin/gallery"
PUBLIC = "/api/v1/public/gallery"
MEDIA = "/api/v1/admin/media"


def create_item(auth_client: TestClient, **overrides: object) -> dict:
    response = auth_client.post(ADMIN, json=gallery_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


# --- Validation -------------------------------------------------------------


def test_gallery_requires_title_and_image_url(auth_client: TestClient) -> None:
    assert auth_client.post(ADMIN, json={"title": "No image"}).status_code == 422
    assert (
        auth_client.post(ADMIN, json={"image_url": "https://cdn.example.com/a.jpg"}).status_code
        == 422
    )


def test_gallery_rejects_blank_title(auth_client: TestClient) -> None:
    assert auth_client.post(ADMIN, json=gallery_payload(title="  ")).status_code == 422


def test_gallery_rejects_non_http_image_url(auth_client: TestClient) -> None:
    assert auth_client.post(ADMIN, json=gallery_payload(image_url="not-a-url")).status_code == 422
    assert (
        auth_client.post(
            ADMIN, json=gallery_payload(image_url="ftp://cdn.example.com/a.jpg")
        ).status_code
        == 422
    )


def test_gallery_allows_missing_s3_key(auth_client: TestClient) -> None:
    payload = gallery_payload()
    payload.pop("s3_key")

    assert auth_client.post(ADMIN, json=payload).status_code == 201


@pytest.mark.parametrize(
    "s3_key",
    [
        "gallery/bridal.jpg",  # missing the media/ prefix
        "media/bridal.jpg",  # missing the category segment
        "media/gallery/bridal.jpg",  # token is not 32 hex characters
        "media/gallery/0123456789abcdef0123456789abcdeg.jpg",  # non-hex character
        "media/gallery/0123456789ABCDEF0123456789abcdef.jpg",  # uppercase
        "media/unknown/0123456789abcdef0123456789abcdef.jpg",  # unknown category
        "media/gallery/0123456789abcdef0123456789abcdef.exe",  # unsupported extension
        "media/gallery/0123456789abcdef0123456789abcdef.jpg/../../etc",  # traversal
        "s3://bucket/media/gallery/0123456789abcdef0123456789abcdef.jpg",
    ],
)
def test_gallery_rejects_an_s3_key_it_could_not_have_produced(
    auth_client: TestClient, s3_key: str
) -> None:
    """A stored key must be one the upload endpoint could have generated.

    Otherwise a hand-edited document could aim a later delete at an arbitrary
    object in the bucket.
    """
    response = auth_client.post(ADMIN, json=gallery_payload(s3_key=s3_key))

    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "validation_error"


def test_gallery_rejects_a_bad_s3_key_on_update(auth_client: TestClient) -> None:
    created = create_item(auth_client)

    response = auth_client.patch(f"{ADMIN}/{created['id']}", json={"s3_key": "gallery/bridal.jpg"})

    assert response.status_code == 422
    assert created["s3_key"] == gallery_payload()["s3_key"]


def test_gallery_s3_key_can_be_cleared(auth_client: TestClient) -> None:
    """Detaching an item from its object is a legitimate edit."""
    created = create_item(auth_client)

    assert auth_client.patch(f"{ADMIN}/{created['id']}", json={"s3_key": None}).status_code == 200
    assert auth_client.get(f"{ADMIN}/{created['id']}").json()["s3_key"] is None


# --- Media association -------------------------------------------------------
#
# An item may either be created by uploading a file (Step 4) or point at an
# object that was uploaded earlier. Both paths converge on the same record.


def test_gallery_item_can_reference_an_existing_upload(
    auth_client: TestClient, fake_s3: FakeS3Client
) -> None:
    key = build_object_key("gallery", "jpg", token="a" * 32)
    fake_s3.objects[key] = IMAGE_BYTES["png"]
    created = create_item(
        auth_client,
        s3_key=key,
        image_url=f"https://cdn.example.com/{key}",
    )

    assert created["s3_key"] == key
    assert auth_client.get(f"{ADMIN}/{created['id']}").json()["s3_key"] == key


def test_upload_creates_a_gallery_item_that_is_immediately_public(
    auth_client: TestClient, fake_s3: FakeS3Client
) -> None:
    """The upload endpoint and the gallery share one collection."""
    response = auth_client.post(
        MEDIA,
        files={"file": ("look.png", IMAGE_BYTES["png"], "image/png")},
        data={"title": "Evening Look", "category": "gallery"},
    )

    assert response.status_code == 201, response.text
    created = response.json()
    assert created["title"] == "Evening Look"
    assert created["s3_key"] in fake_s3.keys

    public = auth_client.get(f"/api/v1/public/gallery/{created['id']}")
    assert public.status_code == 200
    assert public.json()["title"] == "Evening Look"
    assert "s3_key" not in public.json()


# --- CRUD -------------------------------------------------------------------


def test_create_and_read_gallery_item(auth_client: TestClient) -> None:
    created = create_item(auth_client)

    assert created["title"] == "Bridal Makeup"
    assert created["s3_key"] == gallery_payload()["s3_key"]  # admin sees it

    response = auth_client.get(f"{ADMIN}/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_read_unknown_gallery_item_returns_404(auth_client: TestClient) -> None:
    assert auth_client.get(f"{ADMIN}/665f1b2c9e1d4a3f7c8b9a01").status_code == 404


def test_malformed_gallery_id_returns_400(auth_client: TestClient) -> None:
    assert auth_client.get(f"{ADMIN}/123").status_code == 400


def test_update_gallery_item(auth_client: TestClient) -> None:
    created = create_item(auth_client)

    response = auth_client.patch(f"{ADMIN}/{created['id']}", json={"title": "Party Look"})

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Party Look"
    assert body["image_url"] == created["image_url"]


def test_delete_gallery_item(auth_client: TestClient) -> None:
    created = create_item(auth_client)

    assert auth_client.delete(f"{ADMIN}/{created['id']}").status_code == 204
    assert auth_client.get(f"{ADMIN}/{created['id']}").status_code == 404


def test_reorder_gallery_items(auth_client: TestClient) -> None:
    first = create_item(auth_client, title="A")
    second = create_item(auth_client, title="B")

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


# --- Public visibility and field filtering ----------------------------------


def test_public_list_never_exposes_s3_key(auth_client: TestClient) -> None:
    create_item(auth_client)

    response = auth_client.get(PUBLIC)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert "s3_key" not in body["items"][0]
    assert body["items"][0]["title"] == "Bridal Makeup"


def test_public_detail_never_exposes_s3_key(auth_client: TestClient) -> None:
    created = create_item(auth_client)

    body = auth_client.get(f"{PUBLIC}/{created['id']}").json()

    assert "s3_key" not in body
    assert body["id"] == created["id"]


def test_public_list_hides_inactive_items(auth_client: TestClient) -> None:
    visible = create_item(auth_client, title="Visible")
    hidden = create_item(auth_client, title="Hidden")
    auth_client.patch(f"{ADMIN}/{hidden['id']}/active", params={"is_active": False})

    body = auth_client.get(PUBLIC).json()

    assert body["total"] == 1
    assert body["items"][0]["id"] == visible["id"]


def test_public_detail_returns_404_for_inactive_item(auth_client: TestClient) -> None:
    created = create_item(auth_client)
    auth_client.patch(f"{ADMIN}/{created['id']}/active", params={"is_active": False})

    assert auth_client.get(f"{PUBLIC}/{created['id']}").status_code == 404


def test_admin_list_ignores_is_active(auth_client: TestClient) -> None:
    create_item(auth_client, title="Visible")
    hidden = create_item(auth_client, title="Hidden")
    auth_client.patch(f"{ADMIN}/{hidden['id']}/active", params={"is_active": False})

    assert auth_client.get(ADMIN).json()["total"] == 2
