"""Testimonial repository.

The public filter lives here (as a constant in the model module) so the rule
"only approved **and** visible testimonials are public" is defined exactly once.
"""

from __future__ import annotations

from typing import Any

from app.models.collections import TESTIMONIALS
from app.models.testimonial import PUBLIC_FILTER, TestimonialDocument
from app.repositories.base import BaseRepository


class TestimonialsRepository(BaseRepository[TestimonialDocument]):
    """CRUD plus moderation-aware queries."""

    collection_name = TESTIMONIALS
    document_type = TestimonialDocument

    async def list_public(self, *, skip: int, limit: int) -> tuple[list[TestimonialDocument], int]:
        """Approved **and** visible testimonials, newest first."""
        return await self.list(
            filters=PUBLIC_FILTER,
            sort=[("created_at", -1)],
            skip=skip,
            limit=limit,
        )

    async def list_by_status(
        self, *, status: str | None = None, skip: int = 0, limit: int = 50
    ) -> tuple[list[TestimonialDocument], int]:
        filters: dict[str, Any] = {} if status is None else {"status": status}
        return await self.list(
            filters=filters,
            sort=[("created_at", -1)],
            skip=skip,
            limit=limit,
        )
