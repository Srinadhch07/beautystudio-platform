"""Shared response envelopes and pagination helpers."""

from __future__ import annotations

from typing import Annotated, Generic, TypeVar

from fastapi import Depends, Query
from pydantic import BaseModel, Field

from app.models.base import PyObjectId

ItemT = TypeVar("ItemT")

MAX_SKIP = 10_000
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
MAX_REORDER_ITEMS = 500


class Page(BaseModel, Generic[ItemT]):
    """Consistent envelope for every list endpoint."""

    items: list[ItemT]
    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1)

    @property
    def has_more(self) -> bool:
        return self.skip + len(self.items) < self.total


class PaginationParams(BaseModel):
    """Validated ``skip`` / ``limit`` query parameters."""

    skip: int = Field(default=0, ge=0, le=MAX_SKIP)
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)


def get_pagination_params(
    skip: Annotated[int, Query(ge=0, le=MAX_SKIP, description="Documents to skip.")] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=MAX_LIMIT, description="Maximum documents to return."),
    ] = DEFAULT_LIMIT,
) -> PaginationParams:
    return PaginationParams(skip=skip, limit=limit)


PaginationDependency = Annotated[PaginationParams, Depends(get_pagination_params)]


class ReorderItem(BaseModel):
    """One position in a bulk ordering request."""

    id: PyObjectId
    display_order: int = Field(ge=0, le=100_000)


class ReorderRequest(BaseModel):
    """Bulk ordering payload."""

    items: list[ReorderItem] = Field(min_length=1, max_length=MAX_REORDER_ITEMS)


class ReorderResponse(BaseModel):
    """How many documents were repositioned."""

    updated: int = Field(ge=0)


class MessageResponse(BaseModel):
    """Simple acknowledgement payload."""

    message: str
