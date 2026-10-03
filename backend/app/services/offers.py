"""Offer business logic."""

from __future__ import annotations

from bson import ObjectId

from app.core.errors import NotFoundError
from app.models.offer import OfferDocument
from app.repositories.offers import OffersRepository
from app.schemas.offers import OfferCreate, OfferUpdate
from app.services.base import CatalogService, DocumentPage


class OfferService(CatalogService[OfferDocument, OfferCreate, OfferUpdate]):
    """Create, update, order, activate and delete offers.

    The public view additionally applies the validity window, so an offer whose
    end date has passed stops being served without anyone having to deactivate
    it. Deactivating is still the explicit override for "hide this now".
    """

    resource_label = "Offer"
    document_type = OfferDocument

    def __init__(self, repository: OffersRepository) -> None:
        super().__init__(repository)
        self._offers = repository

    async def list_active(self, *, skip: int = 0, limit: int = 50) -> DocumentPage:
        """Current offers in display order - the public view."""
        documents, total = await self._offers.list_active(skip=skip, limit=limit)
        return DocumentPage(items=documents, total=total, skip=skip, limit=limit)

    async def get_public(self, resource_id: ObjectId) -> OfferDocument:
        """Read one offer, but only while it is active and currently valid.

        Anything else is a ``404`` rather than a ``403``, so the public API never
        reveals that an offer exists but has expired.
        """
        document = await self._offers.find_active_by_id(resource_id)
        if document is None:
            raise NotFoundError(f"{self.resource_label} not found.")
        return document
