"""Gallery / media document.

Media and gallery items share **one** collection. A gallery entry is a media
record, so introducing a second ``media`` collection would have split the same
entity across two stores and made "show me the gallery" ambiguous.

Binary image data is never stored here: the document holds only the object key
and the public URL of a file living in S3. The three upload-related fields
(:attr:`content_type`, :attr:`file_size`, :attr:`original_filename`) are optional
because records created through the metadata-only ``/admin/gallery`` route have
no uploaded file behind them.
"""

from __future__ import annotations

from pydantic import Field, field_validator

from app.models.base import BaseDocument
from app.models.service import MAX_DISPLAY_ORDER

#: Longest original filename kept for display. Anything longer is truncated by
#: the service; the limit exists so a hostile header cannot be used to push an
#: unbounded string into the database.
MAX_ORIGINAL_FILENAME_LENGTH = 255

#: Largest ``file_size`` that can be recorded, as a sanity bound. The real limit
#: for an upload is ``PRODUCT_IMAGE_MAX_BYTES`` and is enforced before any byte
#: reaches this model.
MAX_RECORDED_FILE_SIZE = 1_073_741_824  # 1 GiB


class GalleryDocument(BaseDocument):
    """One media item."""

    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    image_url: str | None = Field(default=None, max_length=500)
    s3_key: str | None = Field(default=None, max_length=500)
    category: str | None = Field(default=None, max_length=80)
    is_active: bool = True
    display_order: int = Field(default=0, ge=0, le=MAX_DISPLAY_ORDER)

    # -- Upload provenance (populated by POST /admin/media) --------------------

    content_type: str | None = Field(default=None, max_length=100)
    file_size: int | None = Field(default=None, ge=0, le=MAX_RECORDED_FILE_SIZE)
    #: The name the file arrived with, sanitised to a bare basename. Kept for
    #: display only; it is never used to build the S3 key.
    original_filename: str | None = Field(
        default=None,
        max_length=MAX_ORIGINAL_FILENAME_LENGTH,
    )

    @field_validator("content_type")
    @classmethod
    def _normalise_content_type(cls, value: str | None) -> str | None:
        """Store the bare media type, without any ``; charset=`` parameters."""
        if value is None:
            return None
        return value.split(";", 1)[0].strip().lower() or None
