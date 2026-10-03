"""Gallery repository."""

from __future__ import annotations

from bson import ObjectId

from app.models.collections import GALLERY
from app.models.gallery import GalleryDocument
from app.repositories.base import ACTIVE_DISPLAY_ORDER_SORT, BaseRepository


class GalleryRepository(BaseRepository[GalleryDocument]):
    """CRUD plus the active-only query used by the public API."""

    collection_name = GALLERY
    document_type = GalleryDocument

    async def list_active(self, *, skip: int, limit: int) -> tuple[list[GalleryDocument], int]:
        return await self.list(
            filters={"is_active": True},
            sort=ACTIVE_DISPLAY_ORDER_SORT,
            skip=skip,
            limit=limit,
        )

    async def find_active_by_id(self, item_id: ObjectId) -> GalleryDocument | None:
        return await self.find_one({"_id": item_id, "is_active": True})
