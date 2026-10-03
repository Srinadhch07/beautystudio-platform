"""Offer request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator

from app.models.base import HttpUrlStr, Price, PyObjectId, UtcDateTime
from app.models.service import MAX_DISPLAY_ORDER


class OfferCreate(BaseModel):
    """Payload for ``POST /api/v1/admin/offers``."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    price: Price
    original_price: Price | None = None
    image: HttpUrlStr | None = None
    is_active: StrictBool = True
    valid_from: UtcDateTime | None = None
    valid_until: UtcDateTime | None = None
    display_order: StrictInt = Field(default=0, ge=0, le=MAX_DISPLAY_ORDER)

    @model_validator(mode="after")
    def _validate_validity_window(self) -> OfferCreate:
        if (
            self.valid_from is not None
            and self.valid_until is not None
            and self.valid_until < self.valid_from
        ):
            raise ValueError("valid_until must not be earlier than valid_from")
        return self


class OfferUpdate(BaseModel):
    """Partial payload for ``PATCH /api/v1/admin/offers/{id}``."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    price: Price | None = None
    original_price: Price | None = None
    image: HttpUrlStr | None = None
    is_active: StrictBool | None = None
    valid_from: UtcDateTime | None = None
    valid_until: UtcDateTime | None = None
    display_order: StrictInt | None = Field(default=None, ge=0, le=MAX_DISPLAY_ORDER)

    @model_validator(mode="after")
    def _validate_supplied_window(self) -> OfferUpdate:
        """Check the window when a single patch carries both endpoints.

        A partial patch that touches only one endpoint is validated later by
        the service, which has access to the stored value of the other one.
        """

        if (
            self.valid_from is not None
            and self.valid_until is not None
            and self.valid_until < self.valid_from
        ):
            raise ValueError("valid_until must not be earlier than valid_from")
        return self


class OfferPublic(BaseModel):
    """Representation returned by the public and admin endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: PyObjectId
    title: str
    description: str | None = None
    price: Price
    original_price: Price | None = None
    image: HttpUrlStr | None = None
    is_active: bool
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    display_order: int
    created_at: datetime
    updated_at: datetime
