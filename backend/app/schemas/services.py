"""Service request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from app.models.base import HttpUrlStr, Price, PyObjectId
from app.models.service import MAX_DISPLAY_ORDER, MAX_DURATION_MINUTES


class ServiceCreate(BaseModel):
    """Payload for ``POST /api/v1/admin/services``."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    price: Price
    category: str | None = Field(default=None, max_length=80)
    duration: StrictInt | None = Field(default=None, ge=1, le=MAX_DURATION_MINUTES)
    image: HttpUrlStr | None = None
    is_active: StrictBool = True
    display_order: StrictInt = Field(default=0, ge=0, le=MAX_DISPLAY_ORDER)


class ServiceUpdate(BaseModel):
    """Partial payload for ``PATCH /api/v1/admin/services/{id}``.

    ``exclude_unset`` semantics mean an explicit ``null`` clears a field.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    price: Price | None = None
    category: str | None = Field(default=None, max_length=80)
    duration: StrictInt | None = Field(default=None, ge=1, le=MAX_DURATION_MINUTES)
    image: HttpUrlStr | None = None
    is_active: StrictBool | None = None
    display_order: StrictInt | None = Field(default=None, ge=0, le=MAX_DISPLAY_ORDER)


class ServicePublic(BaseModel):
    """Representation returned by the public and admin endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: PyObjectId
    name: str
    description: str | None = None
    price: Price
    category: str | None = None
    duration: int | None = None
    image: str | None = None
    is_active: bool
    display_order: int
    created_at: datetime
    updated_at: datetime
