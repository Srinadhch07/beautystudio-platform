"""Service document."""

from __future__ import annotations

from pydantic import Field

from app.models.base import BaseDocument, Price

#: ``duration`` is stored in whole minutes.
MAX_DURATION_MINUTES = 1440
MAX_DISPLAY_ORDER = 100_000


class ServiceDocument(BaseDocument):
    """A treatment or package offered by the parlour."""

    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    price: Price
    category: str | None = Field(default=None, max_length=80)
    duration: int | None = Field(default=None, ge=1, le=MAX_DURATION_MINUTES)
    image: str | None = Field(default=None, max_length=500)
    is_active: bool = True
    display_order: int = Field(default=0, ge=0, le=MAX_DISPLAY_ORDER)
