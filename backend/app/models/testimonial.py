"""Testimonial document with a moderation workflow."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from app.models.base import BaseDocument

MIN_RATING = 1
MAX_RATING = 5
MAX_TESTIMONIAL_LENGTH = 2000


class TestimonialStatus(StrEnum):
    """Moderation states.

    ``PENDING`` is the default: a freshly submitted testimonial is never
    public until an administrator approves it.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


#: The only combination the public endpoint is allowed to return.
PUBLIC_FILTER: dict[str, object] = {
    "status": TestimonialStatus.APPROVED.value,
    "is_visible": True,
}


class TestimonialDocument(BaseDocument):
    """A customer review awaiting or holding moderation."""

    customer_name: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=MAX_TESTIMONIAL_LENGTH)
    rating: int = Field(ge=MIN_RATING, le=MAX_RATING)
    status: TestimonialStatus = TestimonialStatus.PENDING
    is_visible: bool = False
