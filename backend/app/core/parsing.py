"""Identifier parsing for path parameters."""

from __future__ import annotations

from bson import ObjectId

from app.core.errors import BadRequestError

OBJECT_ID_LENGTH = 24


def parse_object_id(value: str, *, field: str = "id") -> ObjectId:
    """Convert a path parameter into an ``ObjectId``.

    Raises :class:`BadRequestError` (HTTP 400) rather than leaking a pydantic
    error for what is a malformed identifier. A well-formed but unknown id is a
    404 and is handled by the service layer.
    """
    if not isinstance(value, str) or not ObjectId.is_valid(value):
        raise BadRequestError(
            f"'{field}' must be a {OBJECT_ID_LENGTH}-character hexadecimal identifier."
        )
    return ObjectId(value)
