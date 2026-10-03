"""Shared service-layer plumbing.

Routes depend on these classes, never on repositories or MongoDB directly, so
business rules (defaults, public filtering, 404 semantics) stay in one place
and are easy to extend.
"""

from __future__ import annotations

from typing import Any, Generic, NamedTuple, TypeVar

from bson import ObjectId
from pydantic import BaseModel

from app.core.errors import NotFoundError
from app.models.base import DocumentT
from app.repositories.base import ACTIVE_DISPLAY_ORDER_SORT, BaseRepository
from app.schemas.common import Page, ReorderRequest

CreateT = TypeVar("CreateT", bound=BaseModel)
UpdateT = TypeVar("UpdateT", bound=BaseModel)
ResponseT = TypeVar("ResponseT", bound=BaseModel)

#: Human-readable noun used in 404 messages, e.g. "Service".
RESOURCE_LABEL = "Resource"


class DocumentPage(NamedTuple):
    """A page of stored documents.

    Deliberately *not* a ``Page[...]`` pydantic model: the service layer is
    generic over a ``TypeVar``, and pydantic cannot build a model schema for an
    unparametrized type variable. Routes convert this into ``Page[SomeSchema]``
    once the concrete response type is known.
    """

    items: list[Any]
    total: int
    skip: int
    limit: int


class CatalogService(Generic[DocumentT, CreateT, UpdateT]):
    """CRUD workflow shared by services, gallery items and offers."""

    resource_label: str = RESOURCE_LABEL
    document_type: type[BaseModel]

    def __init__(self, repository: BaseRepository[DocumentT]) -> None:
        self._repository = repository

    # -- Writes -------------------------------------------------------------

    async def create(self, payload: CreateT) -> DocumentT:
        """Validate the payload through the document model and persist it."""
        document = self.document_type.model_validate(payload.model_dump(mode="python"))
        return await self._repository.create(document)

    async def update(self, resource_id: ObjectId, payload: UpdateT) -> DocumentT:
        """Apply a partial update. Fields absent from the payload are untouched.

        The stored document and the submitted changes are merged and revalidated
        against the document model before anything is written. A single request
        body cannot express rules that span two fields (``valid_until`` versus the
        stored ``valid_from``, for example), so a patch that is individually
        plausible can still be rejected as 422 rather than corrupting the record.
        """
        changes = payload.model_dump(mode="python", exclude_unset=True)
        if changes:
            current = await self._repository.find_by_id(resource_id)
            if current is None:
                raise NotFoundError(f"{self.resource_label} not found.")
            merged = {**current.model_dump(mode="python"), **changes}
            self.document_type.model_validate(merged)

        document = await self._repository.update(resource_id, changes)
        if document is None:
            raise NotFoundError(f"{self.resource_label} not found.")
        return document

    async def delete(self, resource_id: ObjectId) -> None:
        if not await self._repository.delete(resource_id):
            raise NotFoundError(f"{self.resource_label} not found.")

    async def reorder(self, payload: ReorderRequest) -> int:
        """Reposition several documents in one request."""
        return await self._repository.set_display_order(
            (item.id, item.display_order) for item in payload.items
        )

    async def set_active(self, resource_id: ObjectId, is_active: bool) -> DocumentT:
        """Activate or deactivate a single document."""
        document = await self._repository.update(resource_id, {"is_active": is_active})
        if document is None:
            raise NotFoundError(f"{self.resource_label} not found.")
        return document

    # -- Reads --------------------------------------------------------------

    async def get(self, resource_id: ObjectId) -> DocumentT:
        document = await self._repository.find_by_id(resource_id)
        if document is None:
            raise NotFoundError(f"{self.resource_label} not found.")
        return document

    async def get_public(self, resource_id: ObjectId) -> DocumentT:
        """Read one document for the public API.

        An inactive document is reported as missing rather than as forbidden, so
        the public API never reveals content the business has switched off.
        """
        document = await self.get(resource_id)
        if not getattr(document, "is_active", True):
            raise NotFoundError(f"{self.resource_label} not found.")
        return document

    async def list_all(self, *, skip: int = 0, limit: int = 50) -> DocumentPage:
        documents, total = await self._repository.list(
            sort=[("display_order", 1), ("created_at", 1)],
            skip=skip,
            limit=limit,
        )
        return DocumentPage(items=documents, total=total, skip=skip, limit=limit)

    async def list_active(self, *, skip: int = 0, limit: int = 50) -> DocumentPage:
        """Active documents in display order - the public view."""
        documents, total = await self._repository.list(
            filters={"is_active": True},
            sort=ACTIVE_DISPLAY_ORDER_SORT,
            skip=skip,
            limit=limit,
        )
        return DocumentPage(items=documents, total=total, skip=skip, limit=limit)


def to_response(document: DocumentT, schema: type[ResponseT]) -> ResponseT:
    """Project a stored document onto a response schema.

    Pydantic ignores attributes the schema does not declare, which is how
    internal data (``s3_key``, moderation state) stays out of public payloads.
    """
    return schema.model_validate(document, from_attributes=True)


def page_to_response(page: DocumentPage, schema: type[ResponseT]) -> Page[ResponseT]:
    """Project a page of documents onto a response schema."""
    return Page[schema](
        items=[to_response(item, schema) for item in page.items],
        total=page.total,
        skip=page.skip,
        limit=page.limit,
    )
