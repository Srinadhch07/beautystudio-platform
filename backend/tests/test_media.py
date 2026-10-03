"""Media upload, deletion and metadata management.

Two guarantees hold for every test in this module:

1. **No real AWS call is possible.** The S3 service dependency is overridden with
   a :class:`FakeS3Client` for every test by an autouse fixture, so the boto3
   client is never built and no request can leave the process.
2. **No real database is touched.** Records live in the same in-memory
   ``mongomock_motor`` database the rest of the suite uses.

The upload tests deliberately send byte strings that only carry a file *header*.
Validation classifies by signature, so that is sufficient - and it is exactly
what is needed to prove the sniffer is doing the deciding rather than the
filename.
"""

from __future__ import annotations

import re

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from pymongo.errors import PyMongoError

from app.core.errors import InvalidMediaError
from app.core.media import (
    MEDIA_CATEGORIES,
    build_object_key,
    is_safe_object_key,
    sanitise_original_filename,
    validate_image_bytes,
    validate_media_category,
)
from app.repositories.gallery import GalleryRepository
from tests.conftest import IMAGE_BYTES, FakeS3Client, run

MEDIA = "/api/v1/admin/media"
PUBLIC_GALLERY = "/api/v1/public/gallery"

#: ``media/{category}/{32 hex chars}.{ext}``
KEY_PATTERN = re.compile(
    r"^media/(logo|gallery|service|offer|general)/[0-9a-f]{32}\.(jpg|png|webp)$"
)


def upload(
    client: TestClient,
    *,
    filename: str = "bridal.png",
    data: bytes | None = None,
    content_type: str = "image/png",
    title: str = "Bridal Look",
    **extra: object,
):
    """POST a multipart upload. ``data``/``content_type`` default to a real PNG."""
    return client.post(
        MEDIA,
        files={"file": (filename, IMAGE_BYTES["png"] if data is None else data, content_type)},
        data={"title": title, **extra},
    )


def assert_error(response, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code, response.text


# --- 1, 7, 8, 17: a valid authenticated upload --------------------------------


def test_authenticated_admin_can_upload_an_image(
    auth_client: TestClient, fake_s3: FakeS3Client
) -> None:
    """The happy path: 201, object in S3, record in MongoDB."""
    response = upload(auth_client)

    assert response.status_code == 201, response.text
    body = response.json()

    # 7 - the object really was sent to S3, with the sniffed content type.
    assert len(fake_s3.put_calls) == 1
    call = fake_s3.put_calls[0]
    assert call["ContentType"] == "image/png"
    assert call["Body"] == IMAGE_BYTES["png"]
    assert call["Bucket"] == "test-bucket"

    # 8 - metadata persisted, including provenance.
    assert body["title"] == "Bridal Look"
    assert body["content_type"] == "image/png"
    assert body["file_size"] == len(IMAGE_BYTES["png"])
    assert body["original_filename"] == "bridal.png"
    assert body["category"] == "general"
    assert body["is_active"] is True

    # The stored URL is the bucket's own HTTPS address for that exact key.
    assert body["image_url"] == f"https://test-bucket.s3.eu-west-1.amazonaws.com/{body['s3_key']}"
    assert body["image_url"].startswith("https://test-bucket.s3.eu-west-1.amazonaws.com/media/")

    # The record survives in the database, not just in the response.
    stored = run(GalleryRepository(_memory_db(auth_client)).find_by_id(_object_id(body["id"])))
    assert stored is not None
    assert stored.s3_key == body["s3_key"]


def test_upload_response_never_exposes_credentials(
    auth_client: TestClient, fake_s3: FakeS3Client
) -> None:
    """A media record must not leak any credential material."""
    body = upload(auth_client).text

    assert "test-secret-access-key" not in body
    assert "test-access-key-id" not in body
    assert "aws_secret" not in body.lower()
    assert fake_s3.put_calls, "the upload should have reached the fake bucket"


def test_upload_accepts_every_supported_image_format(
    auth_client: TestClient, fake_s3: FakeS3Client
) -> None:
    """JPEG, PNG and WebP are each recognised by signature, not by extension."""
    for kind, content_type, extension in (
        ("jpeg", "image/jpeg", "jpg"),
        ("png", "image/png", "png"),
        ("webp", "image/webp", "webp"),
    ):
        response = upload(
            auth_client,
            filename=f"photo.{extension}",
            data=IMAGE_BYTES[kind],
            content_type=content_type,
            title=f"{kind} title",
        )
        assert response.status_code == 201, response.text
        assert response.json()["content_type"] == content_type
        assert response.json()["s3_key"].endswith(f".{extension}")


def test_upload_honours_category_title_and_order(
    auth_client: TestClient, fake_s3: FakeS3Client
) -> None:
    """Form metadata is validated, stored and reflected in the object key."""
    response = upload(
        auth_client,
        title="Signature Service",
        category="service",
        description="Long description",
        display_order="7",
        is_active="false",
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["category"] == "service"
    assert body["display_order"] == 7
    assert body["is_active"] is False
    assert body["description"] == "Long description"
    assert body["s3_key"].startswith("media/service/")


def test_upload_rejects_an_unknown_category(auth_client: TestClient, fake_s3: FakeS3Client) -> None:
    """A bad category is refused rather than silently bucketed as 'general'."""
    assert_error(upload(auth_client, category="not-a-category"), 400, "invalid_media")
    assert fake_s3.put_calls == [], "nothing should have been uploaded"


def test_every_allowed_category_produces_a_valid_key(
    auth_client: TestClient, fake_s3: FakeS3Client
) -> None:
    for category in MEDIA_CATEGORIES:
        response = upload(auth_client, category=category, title=f"{category} item")
        assert response.status_code == 201, response.text
        assert KEY_PATTERN.match(response.json()["s3_key"]), response.json()["s3_key"]


# --- 2, 5: rejected file types -----------------------------------------------


def test_unsupported_file_type_is_rejected(auth_client: TestClient, fake_s3: FakeS3Client) -> None:
    """A GIF has no entry in the allowlist, so it never reaches S3."""
    assert_error(
        upload(auth_client, filename="x.gif", data=IMAGE_BYTES["gif"], content_type="image/gif"),
        415,
        "unsupported_media_type",
    )
    assert fake_s3.put_calls == []


def test_plain_text_is_rejected(auth_client: TestClient, fake_s3: FakeS3Client) -> None:
    assert_error(
        upload(auth_client, filename="x.png", data=IMAGE_BYTES["text"], content_type="image/png"),
        415,
        "unsupported_media_type",
    )
    assert fake_s3.put_calls == []


@pytest.mark.parametrize(
    ("filename", "kind", "content_type"),
    [
        ("x.png", "html", "image/png"),
        ("x.png", "svg", "image/png"),
        ("x.png", "xml", "image/png"),
    ],
)
def test_html_svg_and_xml_cannot_pose_as_images(
    auth_client: TestClient, fake_s3: FakeS3Client, filename: str, kind: str, content_type: str
) -> None:
    """Scriptable formats are refused even when labelled as a PNG.

    This is the case that makes signature validation load-bearing: without it a
    caller could store HTML under the site's own origin and serve stored XSS.
    """
    assert_error(
        upload(auth_client, filename=filename, data=IMAGE_BYTES[kind], content_type=content_type),
        415,
        "unsupported_media_type",
    )
    assert fake_s3.put_calls == []


@pytest.mark.parametrize(
    ("filename", "kind", "content_type"),
    [
        ("x.png", "exe", "image/png"),
        ("x.png", "elf", "image/png"),
        ("x.sh", "shebang", "application/x-sh"),
        ("x.png", "pdf", "application/pdf"),
        ("x.zip", "zip", "application/zip"),
    ],
)
def test_executables_documents_and_archives_are_rejected(
    auth_client: TestClient, fake_s3: FakeS3Client, filename: str, kind: str, content_type: str
) -> None:
    assert_error(
        upload(auth_client, filename=filename, data=IMAGE_BYTES[kind], content_type=content_type),
        415,
        "unsupported_media_type",
    )
    assert fake_s3.put_calls == []


def test_declared_content_type_must_match_the_bytes(
    auth_client: TestClient, fake_s3: FakeS3Client
) -> None:
    """Real PNG bytes declared as JPEG is a contradiction, not a JPEG upload."""
    response = upload(auth_client, data=IMAGE_BYTES["png"], content_type="image/jpeg")
    assert_error(response, 415, "unsupported_media_type")
    assert "does not match" in response.json()["error"]["message"]
    assert fake_s3.put_calls == []


def test_spoofed_extension_cannot_change_the_stored_type(
    auth_client: TestClient, fake_s3: FakeS3Client
) -> None:
    """A ``.svg`` filename with PNG bytes is stored as a PNG, not as an SVG."""
    response = upload(
        auth_client, filename="malicious.svg", data=IMAGE_BYTES["png"], content_type="image/png"
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["s3_key"].endswith(".png")
    assert body["content_type"] == "image/png"
    # The name is kept for display only and never reaches the key.
    assert body["original_filename"] == "malicious.svg"
    assert "malicious" not in body["s3_key"]


# --- 3, oversized file --------------------------------------------------------


def test_oversized_file_is_rejected(
    auth_client: TestClient, fake_s3: FakeS3Client, settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The limit comes from PRODUCT_IMAGE_MAX_BYTES and is applied while reading."""
    monkeypatch.setattr(settings, "product_image_max_bytes", 64)

    oversized = IMAGE_BYTES["png"] + b"\x00" * 256
    assert_error(
        upload(auth_client, data=oversized, content_type="image/png"), 413, "payload_too_large"
    )
    assert fake_s3.put_calls == [], "an oversized body must not be uploaded"


def test_file_at_the_limit_is_accepted(
    auth_client: TestClient, fake_s3: FakeS3Client, settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The boundary is inclusive, so the check is not off by one."""
    monkeypatch.setattr(settings, "product_image_max_bytes", len(IMAGE_BYTES["png"]))
    assert upload(auth_client).status_code == 201
    assert len(fake_s3.put_calls) == 1


# --- 4: missing file ----------------------------------------------------------


def test_upload_without_a_file_is_rejected(auth_client: TestClient, fake_s3: FakeS3Client) -> None:
    response = auth_client.post(MEDIA, data={"title": "No file here"})

    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "validation_error"
    assert fake_s3.put_calls == []


def test_upload_without_a_title_is_rejected(auth_client: TestClient, fake_s3: FakeS3Client) -> None:
    response = auth_client.post(
        MEDIA, files={"file": ("a.png", IMAGE_BYTES["png"], "image/png")}, data={}
    )
    assert response.status_code == 422, response.text
    assert fake_s3.put_calls == []


def test_empty_file_is_rejected(auth_client: TestClient, fake_s3: FakeS3Client) -> None:
    """Zero bytes is not a valid image even though it is under the size limit."""
    assert_error(upload(auth_client, data=b"", content_type="image/png"), 400, "invalid_media")
    assert fake_s3.put_calls == []


# --- 6: safe object keys ------------------------------------------------------


def test_object_key_uses_the_documented_shape() -> None:
    key = build_object_key("gallery", "png", token="a" * 32)
    assert key == f"media/gallery/{'a' * 32}.png"
    assert is_safe_object_key(key)


def test_object_key_is_collision_safe(auth_client: TestClient, fake_s3: FakeS3Client) -> None:
    """Two uploads of the same file get different keys."""
    first = upload(auth_client).json()["s3_key"]
    second = upload(auth_client).json()["s3_key"]
    assert first != second


def test_hostile_filename_never_reaches_the_key(
    auth_client: TestClient, fake_s3: FakeS3Client
) -> None:
    """Path traversal and unicode homoglyphs in the name are irrelevant."""
    response = upload(
        auth_client,
        filename="../../../../etc/passwd.png",
        data=IMAGE_BYTES["png"],
        content_type="image/png",
    )

    assert response.status_code == 201, response.text
    key = response.json()["s3_key"]
    assert KEY_PATTERN.match(key), key
    assert ".." not in key
    assert "passwd" not in key


def test_sanitised_filename_keeps_only_a_bare_basename() -> None:
    assert sanitise_original_filename("../../etc/passwd", max_length=255) == "passwd"
    assert sanitise_original_filename("C:\\Windows\\evil.exe", max_length=255) == "evil.exe"
    assert sanitise_original_filename("a\x00b.png", max_length=255) == "ab.png"
    assert sanitise_original_filename("x" * 400, max_length=255) == "x" * 255
    assert sanitise_original_filename("", max_length=255) is None


@pytest.mark.parametrize(
    "key",
    [
        "",
        "passwd",
        "media/../../etc/passwd",
        "media/gallery/../logo",
        "other/gallery/" + "a" * 32 + ".png",  # wrong namespace
        "media/unknown/" + "a" * 32 + ".png",  # wrong category
        "media/gallery/" + "a" * 32 + ".svg",  # unsupported extension
        "media/gallery/" + "A" * 32 + ".PNG",  # wrong case
        "media/gallery/" + "a" * 31 + ".png",  # token too short to be a uuid4 hex
    ],
)
def test_unsafe_object_keys_are_rejected(key: str) -> None:
    assert not is_safe_object_key(key)


def test_storage_refuses_to_touch_a_key_outside_the_media_namespace(
    settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tampered key cannot be turned into a delete against another object."""
    from app.core.errors import StorageError
    from app.storage.s3 import S3StorageService

    fake = FakeS3Client()
    service = S3StorageService(settings, client=fake)

    with pytest.raises(StorageError):
        run(service.delete("some/other/prefix.png"))
    with pytest.raises(StorageError):
        run(service.delete("media/gallery/../logo"))

    assert fake.delete_calls == [], "no request should have been made"


# --- 9: S3 succeeded but MongoDB failed --------------------------------------


def test_upload_removes_the_object_when_the_record_cannot_be_saved(
    auth_client: TestClient, fake_s3: FakeS3Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Compensating delete: a failed insert must not leave an orphan object."""

    async def explode(self, document):  # noqa: ANN001, ARG001
        raise PyMongoError("insert failed")

    monkeypatch.setattr(GalleryRepository, "create", explode)

    response = upload(auth_client)

    assert_error(response, 500, "database_error")
    # The upload did happen, so the cleanup had to happen too.
    assert len(fake_s3.put_calls) == 1
    uploaded_key = fake_s3.put_calls[0]["Key"]
    assert [call["Key"] for call in fake_s3.delete_calls] == [uploaded_key]
    assert fake_s3.objects == {}, "no orphan object should remain"


def test_upload_reports_the_database_failure_when_cleanup_also_fails(
    auth_client: TestClient, fake_s3: FakeS3Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cleanup that cannot succeed must not mask the original failure.

    The client is told the database write failed - that is the actionable
    error - while the stranded object is recorded in the logs for an operator to
    reconcile. Swallowing the cleanup error here would report a misleading
    success.
    """
    from app.core.errors import StorageAccessDeniedError
    from app.storage.s3 import S3StorageService

    async def explode(self, document):  # noqa: ANN001, ARG001
        raise PyMongoError("insert failed")

    async def undeletable(self, key: str) -> None:  # noqa: ANN001, ARG001
        raise StorageAccessDeniedError()

    monkeypatch.setattr(GalleryRepository, "create", explode)
    monkeypatch.setattr(S3StorageService, "delete", undeletable)

    response = upload(auth_client)

    assert_error(response, 500, "database_error")
    assert len(fake_s3.put_calls) == 1


# --- 10, 11, 18: deletion -----------------------------------------------------


def test_authenticated_admin_can_delete_media(
    auth_client: TestClient, fake_s3: FakeS3Client
) -> None:
    """Object then record; 204 only when both succeeded."""
    created = upload(auth_client).json()
    media_id, key = created["id"], created["s3_key"]
    assert key in fake_s3.objects

    response = auth_client.delete(f"{MEDIA}/{media_id}")

    assert response.status_code == 204, response.text
    assert [call["Key"] for call in fake_s3.delete_calls] == [key]
    assert fake_s3.objects == {}
    assert run(GalleryRepository(_memory_db(auth_client)).find_by_id(_object_id(media_id))) is None


def test_delete_removes_the_object_before_the_record(
    auth_client: TestClient, fake_s3: FakeS3Client
) -> None:
    """The record still exists at the moment the object is deleted.

    Reverse order would drop the only reference to the key and strand the
    object, so the ordering is asserted rather than assumed.
    """
    media_id = upload(auth_client).json()["id"]

    seen: list[bool] = []
    original_delete = type(fake_s3).delete_object

    def recording_delete(self, **kwargs):  # noqa: ANN001
        seen.append(
            run(GalleryRepository(_memory_db(auth_client)).find_by_id(_object_id(media_id)))
            is not None
        )
        return original_delete(self, **kwargs)

    type(fake_s3).delete_object = recording_delete
    try:
        assert auth_client.delete(f"{MEDIA}/{media_id}").status_code == 204
    finally:
        type(fake_s3).delete_object = original_delete

    assert seen == [True], "the document must still be present during the S3 delete"


def test_delete_reports_a_storage_failure_and_keeps_the_record(
    auth_client: TestClient, fake_s3: FakeS3Client
) -> None:
    """A denied S3 delete must not be reported as success."""
    created = upload(auth_client).json()
    fake_s3.fail_delete = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "DeleteObject"
    )

    response = auth_client.delete(f"{MEDIA}/{created['id']}")

    assert_error(response, 502, "storage_access_denied")
    assert "Access Denied" not in response.text, "the AWS message must not be forwarded"
    # The record is retained so the failure is visible and retryable.
    assert (
        run(GalleryRepository(_memory_db(auth_client)).find_by_id(_object_id(created["id"])))
        is not None
    )


def test_delete_never_leaks_a_traceback_on_storage_failure(
    auth_client: TestClient, fake_s3: FakeS3Client
) -> None:
    created = upload(auth_client).json()
    fake_s3.fail_delete = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "denied for arn:aws:s3:::test-bucket"}},
        "DeleteObject",
    )

    body = auth_client.delete(f"{MEDIA}/{created['id']}").text

    assert "Traceback" not in body
    assert "botocore" not in body
    assert "arn:aws" not in body


def test_delete_of_unknown_media_returns_404(
    auth_client: TestClient, fake_s3: FakeS3Client
) -> None:
    assert_error(auth_client.delete(f"{MEDIA}/{'0' * 24}"), 404, "not_found")
    assert fake_s3.delete_calls == [], "an unknown id must not trigger an S3 call"


def test_delete_with_a_malformed_id_returns_400(
    auth_client: TestClient, fake_s3: FakeS3Client
) -> None:
    assert_error(auth_client.delete(f"{MEDIA}/not-an-object-id"), 400, "bad_request")
    assert fake_s3.delete_calls == []


def test_delete_of_media_without_a_file_still_works(
    auth_client: TestClient, fake_s3: FakeS3Client
) -> None:
    """A record created through /admin/gallery has no object; deletion is a no-op."""
    created = auth_client.post(
        "/api/v1/admin/gallery",
        json={"title": "No file", "image_url": "https://cdn.example.com/a.jpg"},
    )
    assert created.status_code == 201, created.text

    assert auth_client.delete(f"{MEDIA}/{created.json()['id']}").status_code == 204
    assert fake_s3.delete_calls == []


# --- 12: missing media --------------------------------------------------------


def test_update_of_unknown_media_returns_404(auth_client: TestClient) -> None:
    assert_error(auth_client.patch(f"{MEDIA}/{'0' * 24}", json={"title": "x"}), 404, "not_found")


def test_media_id_must_be_a_valid_object_id(auth_client: TestClient) -> None:
    assert_error(auth_client.patch(f"{MEDIA}/xyz", json={"title": "x"}), 400, "bad_request")


# --- 13: metadata update ------------------------------------------------------


def test_metadata_can_be_updated_without_re_uploading(
    auth_client: TestClient, fake_s3: FakeS3Client
) -> None:
    """Descriptive fields change; the object, key and provenance do not."""
    created = upload(auth_client).json()

    response = auth_client.patch(
        f"{MEDIA}/{created['id']}",
        json={
            "title": "Renamed",
            "description": "New description",
            "category": "offer",
            "display_order": 3,
            "is_active": False,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["title"] == "Renamed"
    assert body["description"] == "New description"
    assert body["category"] == "offer"
    assert body["display_order"] == 3
    assert body["is_active"] is False
    # The stored file is untouched and was not re-uploaded.
    assert body["s3_key"] == created["s3_key"]
    assert body["image_url"] == created["image_url"]
    assert body["content_type"] == created["content_type"]
    assert body["file_size"] == created["file_size"]
    assert len(fake_s3.put_calls) == 1, "no second upload"
    assert fake_s3.delete_calls == []


def test_metadata_update_rejects_an_unknown_category(
    auth_client: TestClient, fake_s3: FakeS3Client
) -> None:
    created = upload(auth_client).json()
    response = auth_client.patch(f"{MEDIA}/{created['id']}", json={"category": "nonsense"})
    assert_error(response, 422, "validation_error")


@pytest.mark.parametrize(
    "payload",
    [
        {"s3_key": "media/gallery/other.png"},
        {"image_url": "https://evil.example.com/x.png"},
        {"content_type": "image/gif"},
        {"file_size": 1},
        {"original_filename": "spoofed.png"},
    ],
)
def test_metadata_update_cannot_repoint_the_stored_object(
    auth_client: TestClient, fake_s3: FakeS3Client, payload: dict[str, object]
) -> None:
    """Physical-object fields are not editable through a metadata patch.

    Permitting this would let a record point at a key nobody uploaded, so the
    image and the bucket would silently disagree.
    """
    created = upload(auth_client).json()
    response = auth_client.patch(f"{MEDIA}/{created['id']}", json=payload)
    assert_error(response, 422, "validation_error")

    # Read the record back through the admin gallery route, which shares the
    # collection, and confirm the physical-object fields are untouched.
    unchanged = auth_client.get(f"/api/v1/admin/gallery/{created['id']}").json()
    assert unchanged["s3_key"] == created["s3_key"]
    assert unchanged["image_url"] == created["image_url"]
    assert unchanged["content_type"] == created["content_type"]


def test_metadata_update_rejects_out_of_range_values(
    auth_client: TestClient, fake_s3: FakeS3Client
) -> None:
    created = upload(auth_client).json()
    assert_error(
        auth_client.patch(f"{MEDIA}/{created['id']}", json={"display_order": -1}),
        422,
        "validation_error",
    )
    assert_error(
        auth_client.patch(f"{MEDIA}/{created['id']}", json={"title": ""}),
        422,
        "validation_error",
    )


# --- 14: public exposure ------------------------------------------------------


def test_public_api_returns_only_active_media(
    auth_client: TestClient, fake_s3: FakeS3Client
) -> None:
    active = upload(auth_client, title="Visible", category="gallery").json()
    hidden = upload(auth_client, title="Hidden", category="gallery", is_active="false").json()

    body = auth_client.get(PUBLIC_GALLERY).json()
    titles = [item["title"] for item in body["items"]]

    assert "Visible" in titles
    assert "Hidden" not in titles
    assert active["id"] in [item["id"] for item in body["items"]]
    assert hidden["id"] not in [item["id"] for item in body["items"]]


def test_public_media_never_exposes_internals(
    auth_client: TestClient, fake_s3: FakeS3Client
) -> None:
    """The public payload carries the image URL and nothing operational."""
    created = upload(auth_client, title="Public item").json()

    body = auth_client.get(PUBLIC_GALLERY).text

    assert "s3_key" not in body
    assert "content_type" not in body
    assert "file_size" not in body
    assert "original_filename" not in body
    assert created["image_url"] in body, "the public item still shows its image"


def test_inactive_media_is_not_reachable_by_id(
    auth_client: TestClient, fake_s3: FakeS3Client
) -> None:
    """An inactive item reads as missing, not as forbidden."""
    hidden = upload(auth_client, title="Hidden", is_active="false").json()
    assert_error(auth_client.get(f"{PUBLIC_GALLERY}/{hidden['id']}"), 404, "not_found")


def test_toggling_visibility_changes_public_availability(
    auth_client: TestClient, fake_s3: FakeS3Client
) -> None:
    created = upload(auth_client, title="Toggle me", is_active="false").json()
    media_id = created["id"]

    assert_error(auth_client.get(f"{PUBLIC_GALLERY}/{media_id}"), 404, "not_found")

    assert auth_client.patch(f"{MEDIA}/{media_id}", json={"is_active": True}).status_code == 200
    assert auth_client.get(f"{PUBLIC_GALLERY}/{media_id}").status_code == 200


# --- 15, 16: authentication ---------------------------------------------------


def test_unauthenticated_upload_is_rejected(
    anonymous_client: TestClient, fake_s3: FakeS3Client
) -> None:
    response = upload(anonymous_client)

    assert_error(response, 401, "not_authenticated")
    assert fake_s3.put_calls == [], "an anonymous request must not upload anything"


def test_unauthenticated_delete_is_rejected(anonymous_client: TestClient) -> None:
    assert_error(anonymous_client.delete(f"{MEDIA}/{'0' * 24}"), 401, "not_authenticated")


def test_unauthenticated_metadata_update_is_rejected(anonymous_client: TestClient) -> None:
    assert_error(
        anonymous_client.patch(f"{MEDIA}/{'0' * 24}", json={"title": "x"}),
        401,
        "not_authenticated",
    )


def test_upload_requires_a_csrf_header(auth_client: TestClient, fake_s3: FakeS3Client) -> None:
    """A session cookie alone is not enough for a state-changing request."""
    from app.core.cookies import CSRF_HEADER_NAME

    auth_client.headers.pop(CSRF_HEADER_NAME, None)

    assert_error(upload(auth_client), 403, "csrf_failed")
    assert fake_s3.put_calls == []


# --- unit tests for the validation and key helpers ----------------------------


@pytest.mark.parametrize(
    ("kind", "content_type", "extension"),
    [
        ("jpeg", "image/jpeg", "jpg"),
        ("png", "image/png", "png"),
        ("webp", "image/webp", "webp"),
    ],
)
def test_validator_accepts_real_signatures(kind: str, content_type: str, extension: str) -> None:
    result = validate_image_bytes(
        IMAGE_BYTES[kind], declared_content_type=content_type, max_bytes=5_242_880
    )
    assert result.content_type == content_type
    assert result.extension == extension
    assert result.size_bytes == len(IMAGE_BYTES[kind])


def test_validator_ignores_content_type_parameters() -> None:
    """``image/png; charset=binary`` is still image/png."""
    result = validate_image_bytes(
        IMAGE_BYTES["png"],
        declared_content_type="IMAGE/PNG; charset=binary",
        max_bytes=5_242_880,
    )
    assert result.content_type == "image/png"


def test_validator_requires_a_declared_type() -> None:
    from app.core.errors import InvalidMediaError

    with pytest.raises(InvalidMediaError):
        validate_image_bytes(IMAGE_BYTES["png"], declared_content_type=None, max_bytes=5_242_880)


def test_validator_enforces_the_size_limit() -> None:
    from app.core.errors import PayloadTooLargeError

    with pytest.raises(PayloadTooLargeError):
        validate_image_bytes(IMAGE_BYTES["png"], declared_content_type="image/png", max_bytes=10)


def test_build_object_key_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        build_object_key("nope", "png", token="a" * 32)
    with pytest.raises(ValueError):
        build_object_key("gallery", "exe", token="a" * 32)
    with pytest.raises(ValueError):
        build_object_key("gallery", "png", token="../../etc")


def test_category_defaults_to_general_and_is_normalised() -> None:
    assert validate_media_category(None) == "general"
    assert validate_media_category("  ") == "general"
    assert validate_media_category(" Gallery ") == "gallery"
    with pytest.raises(InvalidMediaError):
        validate_media_category("unknown")


# --- helpers ------------------------------------------------------------------


def _memory_db(client: TestClient):
    """The in-memory database the request was served from."""
    from app.api.deps import get_database
    from app.main import app

    return app.dependency_overrides[get_database]()


def _object_id(value: str):
    from bson import ObjectId

    return ObjectId(value)
