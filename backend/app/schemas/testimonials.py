"""Testimonial request/response schemas.

The create schema deliberately exposes **no** moderation fields: ``status`` and
``is_visible`` are set to their safe defaults on submission and can only be
changed through the moderation endpoint.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from app.models.base import PyObjectId
from app.models.testimonial import (
    MAX_RATING,
    MAX_TESTIMONIAL_LENGTH,
    MIN_RATING,
    TestimonialStatus,
)


class TestimonialCreate(BaseModel):
    """Public submission payload."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    customer_name: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=MAX_TESTIMONIAL_LENGTH)
    rating: StrictInt = Field(ge=MIN_RATING, le=MAX_RATING)


class TestimonialModeration(BaseModel):
    """Moderation payload for ``PATCH /api/v1/admin/testimonials/{id}/moderate``."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    status: TestimonialStatus
    is_visible: StrictBool = False


class TestimonialAdminCreate(TestimonialCreate):
    """Admin creation, where the moderation state is chosen up front.

    Used for reviews captured in person; public submissions use
    :class:`TestimonialCreate`, which cannot set these fields.
    """

    status: TestimonialStatus = TestimonialStatus.PENDING
    is_visible: StrictBool = False


class TestimonialUpdate(BaseModel):
    """Partial content edit (does not change moderation state)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    customer_name: str | None = Field(default=None, min_length=1, max_length=120)
    content: str | None = Field(default=None, min_length=1, max_length=MAX_TESTIMONIAL_LENGTH)
    rating: StrictInt | None = Field(default=None, ge=MIN_RATING, le=MAX_RATING)


class TestimonialPublic(BaseModel):
    """Public testimonial.

    Moderation fields are omitted on purpose - a visitor never needs to know
    whether a review was approved.
    """

    model_config = ConfigDict(from_attributes=True)

    id: PyObjectId
    customer_name: str
    content: str
    rating: int = Field(ge=MIN_RATING, le=MAX_RATING)
    created_at: datetime


class TestimonialAdmin(TestimonialPublic):
    """Admin view including moderation state."""

    status: TestimonialStatus
    is_visible: bool
    updated_at: datetime
