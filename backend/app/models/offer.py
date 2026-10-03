"""Offer / package document."""

from __future__ import annotations

from pydantic import Field, model_validator

from app.models.base import BaseDocument, Price, UtcDateTime
from app.models.service import MAX_DISPLAY_ORDER


class OfferDocument(BaseDocument):
    """A promotional package."""

    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    price: Price
    original_price: Price | None = None
    image: str | None = Field(default=None, max_length=500)
    is_active: bool = True
    valid_from: UtcDateTime | None = None
    valid_until: UtcDateTime | None = None
    display_order: int = Field(default=0, ge=0, le=MAX_DISPLAY_ORDER)

    @model_validator(mode="after")
    def _validate_validity_window(self) -> OfferDocument:
        if (
            self.valid_from is not None
            and self.valid_until is not None
            and self.valid_until < self.valid_from
        ):
            raise ValueError("valid_until must not be earlier than valid_from")
        return self
