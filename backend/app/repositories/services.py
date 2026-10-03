"""Service repository."""

from __future__ import annotations

from bson import ObjectId

from app.models.collections import SERVICES
from app.models.service import ServiceDocument
from app.repositories.base import ACTIVE_DISPLAY_ORDER_SORT, BaseRepository


class ServicesRepository(BaseRepository[ServiceDocument]):
    """CRUD plus the active-only queries used by the public API."""

    collection_name = SERVICES
    document_type = ServiceDocument

    async def list_active(self, *, skip: int, limit: int) -> tuple[list[ServiceDocument], int]:
        return await self.list(
            filters={"is_active": True},
            sort=ACTIVE_DISPLAY_ORDER_SORT,
            skip=skip,
            limit=limit,
        )

    async def find_active_by_id(self, service_id: ObjectId) -> ServiceDocument | None:
        return await self.find_one({"_id": service_id, "is_active": True})
