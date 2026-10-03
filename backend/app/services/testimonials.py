"""Testimonial business logic and moderation rules.

The important invariant lives here: a submitted testimonial is always ``pending``
and invisible, and only an explicit moderation call can make it public. The
public predicate ``status=approved AND is_visible=true`` therefore holds no
matter what a caller sends.
"""

from __future__ import annotations

from bson import ObjectId

from app.core.errors import ConflictError, NotFoundError
from app.models.testimonial import TestimonialDocument, TestimonialStatus
from app.repositories.testimonials import TestimonialsRepository
from app.schemas.testimonials import (
    TestimonialAdminCreate,
    TestimonialCreate,
    TestimonialModeration,
    TestimonialUpdate,
)
from app.services.base import CatalogService, DocumentPage


class TestimonialService(CatalogService[TestimonialDocument, TestimonialCreate, TestimonialUpdate]):
    """Submission, moderation and public retrieval."""

    resource_label = "Testimonial"
    document_type = TestimonialDocument

    def __init__(self, repository: TestimonialsRepository) -> None:
        super().__init__(repository)
        self._testimonials = repository

    async def submit(self, payload: TestimonialCreate) -> TestimonialDocument:
        """Accept a public submission.

        Moderation fields are not part of the public schema, and are forced to
        the safe defaults here, so nobody can self-approve a review.
        """
        values = payload.model_dump(mode="python")
        values.update({"status": TestimonialStatus.PENDING, "is_visible": False})
        return await self._repository.create(TestimonialDocument(**values))

    async def moderate(
        self, testimonial_id: ObjectId, payload: TestimonialModeration
    ) -> TestimonialDocument:
        """Approve, reject or hide a testimonial.

        Requesting ``is_visible=true`` together with a non-approved status is a
        contradictory state and is rejected with HTTP 409 instead of being
        silently coerced.
        """
        is_visible = self._resolve_visibility(payload.status, payload.is_visible)

        document = await self._repository.update(
            testimonial_id,
            {"status": payload.status, "is_visible": is_visible},
        )
        if document is None:
            return await self.get(testimonial_id)  # raises NotFoundError
        return document

    async def create_with_moderation(self, payload: TestimonialAdminCreate) -> TestimonialDocument:
        """Create a review with an explicit moderation state (e.g. taken in person)."""
        is_visible = self._resolve_visibility(payload.status, payload.is_visible)
        values = payload.model_dump(mode="python")
        values["is_visible"] = is_visible
        return await self._repository.create(TestimonialDocument(**values))

    @staticmethod
    def _resolve_visibility(status: TestimonialStatus, is_visible: bool) -> bool:
        """A testimonial may only be visible while it is approved."""
        if is_visible and status is not TestimonialStatus.APPROVED:
            raise ConflictError("A testimonial can only be visible while its status is 'approved'.")
        return is_visible

    async def list_public(self, *, skip: int = 0, limit: int = 50) -> DocumentPage:
        """Approved **and** visible testimonials, newest first."""
        documents, total = await self._testimonials.list_public(skip=skip, limit=limit)
        return DocumentPage(items=documents, total=total, skip=skip, limit=limit)

    async def get_public(self, testimonial_id: ObjectId) -> TestimonialDocument:
        """Read one testimonial, but only if it is approved and visible.

        Anything else is a 404, so a pending or rejected review is
        indistinguishable from one that does not exist.
        """
        document = await self.get(testimonial_id)
        is_public = document.is_visible and document.status is TestimonialStatus.APPROVED
        if not is_public:
            raise NotFoundError("Testimonial not found.")
        return document

    async def list_for_moderation(
        self, *, status: TestimonialStatus | None = None, skip: int = 0, limit: int = 50
    ) -> DocumentPage:
        """All testimonials for the admin queue, optionally filtered."""
        documents, total = await self._testimonials.list_by_status(
            status=status.value if status is not None else None,
            skip=skip,
            limit=limit,
        )
        return DocumentPage(items=documents, total=total, skip=skip, limit=limit)
