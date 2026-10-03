"""Generic MongoDB repository.

Every persistence detail lives here: ``_id`` mapping, ``$set`` conversion of
``Decimal``/``Enum`` values, ``updated_at`` bookkeeping and pagination. Domain
modules only add the queries their collection needs.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Generic

from bson import ObjectId
from pymongo import ASCENDING, ReturnDocument
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase

from app.models.base import BaseDocument, DocumentT, to_bson_value, utcnow

Document = dict[str, Any]


class BaseRepository(Generic[DocumentT]):
    """CRUD access to a single collection."""

    collection_name: str
    document_type: type[BaseDocument]

    def __init__(self, database: AsyncDatabase[Document]) -> None:
        self._collection: AsyncCollection[Document] = database[self.collection_name]

    # -- Read ---------------------------------------------------------------

    async def find_by_id(self, document_id: ObjectId) -> DocumentT | None:
        raw = await self._collection.find_one({"_id": document_id})
        return self.document_type.from_mongo(raw) if raw is not None else None

    async def find_one(self, filters: Mapping[str, Any] | None = None) -> DocumentT | None:
        raw = await self._collection.find_one(dict(filters or {}))
        return self.document_type.from_mongo(raw) if raw is not None else None

    async def list(
        self,
        *,
        filters: Mapping[str, Any] | None = None,
        sort: Sequence[tuple[str, int]] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[DocumentT], int]:
        """Return a page of documents plus the total number of matches."""
        query = to_bson_value(dict(filters or {}))
        total = await self._collection.count_documents(query)

        cursor = self._collection.find(query)
        if sort:
            cursor = cursor.sort(list(sort))
        if skip:
            cursor = cursor.skip(skip)
        cursor = cursor.limit(limit)

        documents = await cursor.to_list(length=limit)
        return [self.document_type.from_mongo(document) for document in documents], total

    # -- Write --------------------------------------------------------------

    async def create(self, document: DocumentT) -> DocumentT:
        await self._collection.insert_one(document.to_mongo())
        return document

    async def update(self, document_id: ObjectId, changes: Mapping[str, Any]) -> DocumentT | None:
        """Apply a partial update. Returns ``None`` when the id is unknown."""
        payload = to_bson_value(dict(changes))
        payload["updated_at"] = utcnow()

        raw = await self._collection.find_one_and_update(
            {"_id": document_id},
            {"$set": payload},
            return_document=ReturnDocument.AFTER,
        )
        return self.document_type.from_mongo(raw) if raw is not None else None

    async def upsert_by(
        self,
        filters: Mapping[str, Any],
        defaults: Mapping[str, Any],
        *,
        changes: Mapping[str, Any] | None = None,
    ) -> DocumentT:
        """Insert ``defaults`` when nothing matches, otherwise apply ``changes``.

        Backed by a single atomic ``find_one_and_update`` so concurrent callers
        cannot create duplicates.
        """
        update: dict[str, Any] = {"$setOnInsert": to_bson_value(dict(defaults))}
        if changes:
            payload = to_bson_value(dict(changes))
            payload["updated_at"] = utcnow()
            update["$set"] = payload

        raw = await self._collection.find_one_and_update(
            to_bson_value(dict(filters)),
            update,
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return self.document_type.from_mongo(raw)

    async def delete(self, document_id: ObjectId) -> bool:
        result = await self._collection.delete_one({"_id": document_id})
        return result.deleted_count == 1

    async def set_display_order(self, positions: Iterable[tuple[ObjectId, int]]) -> int:
        """Reposition documents. Returns how many matched."""
        updated = 0
        now = utcnow()
        for document_id, position in positions:
            result = await self._collection.update_one(
                {"_id": document_id},
                {"$set": {"display_order": position, "updated_at": now}},
            )
            updated += result.matched_count
        return updated

    @property
    def collection(self) -> AsyncCollection[Document]:
        """Escape hatch for queries that do not warrant a dedicated method."""
        return self._collection


#: Default ordering helper: ascending ``display_order``, then oldest first.
ACTIVE_DISPLAY_ORDER_SORT: Sequence[tuple[str, int]] = [
    ("display_order", ASCENDING),
    ("created_at", ASCENDING),
]
