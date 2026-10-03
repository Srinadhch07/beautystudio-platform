"""Offer repository."""

from __future__ import annotations

from datetime import UTC, datetime

from bson import ObjectId

from app.models.collections import OFFERS
from app.models.offer import OfferDocument
from app.repositories.base import ACTIVE_DISPLAY_ORDER_SORT, BaseRepository


class OffersRepository(BaseRepository[OfferDocument]):
    """CRUD plus the current-offer query used by the public API."""

    collection_name = OFFERS
    document_type = OfferDocument

    @staticmethod
    def _current_filter(now: datetime) -> dict[str, object]:
        """Filters an offer must satisfy to be shown publicly.

        An offer is current when it is active and its validity window contains
        ``now``. An absent bound means "open ended on that side", which in
        MongoDB is matched by a plain ``None`` comparison (it matches an explicit
        null *and* a missing field). ``$lte`` alone would exclude an offer with no
        start date, so each side is an explicit disjunction.
        """
        return {
            "is_active": True,
            "$and": [
                {"$or": [{"valid_from": None}, {"valid_from": {"$lte": now}}]},
                {"$or": [{"valid_until": None}, {"valid_until": {"$gte": now}}]},
            ],
        }

    async def list_active(self, *, skip: int, limit: int) -> tuple[list[OfferDocument], int]:
        """Active *and* currently valid offers, in display order."""
        return await self.list(
            filters=self._current_filter(datetime.now(UTC)),
            sort=ACTIVE_DISPLAY_ORDER_SORT,
            skip=skip,
            limit=limit,
        )

    async def find_active_by_id(self, offer_id: ObjectId) -> OfferDocument | None:
        return await self.find_one({"_id": offer_id, **self._current_filter(datetime.now(UTC))})
