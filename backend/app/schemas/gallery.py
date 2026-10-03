"""Gallery request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator

from app.core.media import MEDIA_CATEGORIES, is_known_category, is_safe_object_key
from app.models.base import HttpUrlStr, PyObjectId
from app.models.service import MAX_DISPLAY_ORDER


class _S3KeyMixin(BaseModel):
    """Shared validation for the stored object key.

    ``s3_key`` names a physical object, so it is held to the same strict shape the
    key generator produces. Without this, a hand-typed or tampered key could be
    persisted and later turned into a delete against an arbitrary object in the
    bucket. Rejecting it at the write boundary means the storage layer's own
    re-check is defence in depth rather than the only line of defence.
    """

    @field_validator("s3_key", check_fields=False)
    @classmethod
    def _validate_s3_key(cls, value: str | None) -> str | None:
        if value is None or not value:
            return None
        if not is_safe_object_key(value):
            raise ValueError(
                "s3_key must be a key produced by the media upload endpoint "
                "(media/{category}/{32 hex characters}.{extension})"
            )
        return value


class GalleryCreate(_S3KeyMixin):
    """Payload for ``POST /api/v1/admin/gallery``."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    image_url: HttpUrlStr
    s3_key: str | None = Field(default=None, max_length=500)
    category: str | None = Field(default=None, max_length=80)
    is_active: StrictBool = True
    display_order: StrictInt = Field(default=0, ge=0, le=MAX_DISPLAY_ORDER)


class GalleryUpdate(_S3KeyMixin):
    """Partial payload for ``PATCH /api/v1/admin/gallery/{id}``."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    image_url: HttpUrlStr | None = None
    s3_key: str | None = Field(default=None, max_length=500)
    category: str | None = Field(default=None, max_length=80)
    is_active: StrictBool | None = None
    display_order: StrictInt | None = Field(default=None, ge=0, le=MAX_DISPLAY_ORDER)


class MediaMetadataUpdate(BaseModel):
    """Partial payload for ``PATCH /api/v1/admin/media/{id}``.

    Deliberately narrower than :class:`GalleryUpdate`: this endpoint changes
    descriptive metadata only. ``s3_key``, ``image_url``, ``content_type`` and
    ``file_size`` are *not* editable here, because they describe a physical
    object - letting a caller point a record at a different key through a
    metadata patch would desynchronise the database from the bucket. Replacing
    the image means uploading a new one.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    category: str | None = Field(default=None, max_length=80)
    is_active: StrictBool | None = None
    display_order: StrictInt | None = Field(default=None, ge=0, le=MAX_DISPLAY_ORDER)

    @field_validator("category")
    @classmethod
    def _validate_category(cls, value: str | None) -> str | None:
        """Only the closed set of storage categories may be stored.

        The gallery route keeps accepting free text for display grouping, but a
        media record's category also names its S3 key prefix, so it is held to
        the same allowlist the key generator uses.
        """
        if value is None:
            return None
        candidate = value.strip().lower()
        if candidate and not is_known_category(candidate):
            raise ValueError(f"category must be one of: {', '.join(MEDIA_CATEGORIES)}")
        return candidate or None


class GalleryPublic(BaseModel):
    """Public gallery item.

    ``s3_key`` is never exposed, and neither are the upload-provenance fields:
    the internal object key, byte size and the name the file arrived with are
    operational details, not public content.
    """

    model_config = ConfigDict(from_attributes=True)

    id: PyObjectId
    title: str
    description: str | None = None
    image_url: HttpUrlStr
    category: str | None = None
    is_active: bool
    display_order: int
    created_at: datetime
    updated_at: datetime


class GalleryAdmin(GalleryPublic):
    """Admin view, which additionally exposes the stored object key and provenance."""

    s3_key: str | None = None
    content_type: str | None = None
    file_size: int | None = None
    original_filename: str | None = None
