"""Index management."""

from __future__ import annotations

import logging

from pymongo.asynchronous.database import AsyncDatabase

from app.models.collections import ALL_COLLECTIONS, COLLECTION_INDEXES

logger = logging.getLogger(__name__)

Document = dict[str, object]


async def ensure_indexes(database: AsyncDatabase[Document]) -> list[str]:
    """Create the declared indexes.

    Returns the collections whose indexes were applied. A failure on one
    collection is logged and does not prevent the others from being processed,
    because degraded indexing must never stop the API from starting.
    """
    applied: list[str] = []

    for collection_name in ALL_COLLECTIONS:
        indexes = COLLECTION_INDEXES.get(collection_name)
        if not indexes:
            continue
        try:
            await database[collection_name].create_indexes(indexes)
        except Exception as exc:  # noqa: BLE001 - index creation must not block start-up
            logger.warning(
                "Could not create indexes for %r (%s)", collection_name, type(exc).__name__
            )
            continue
        applied.append(collection_name)

    logger.info("Indexes ensured for: %s", ", ".join(applied) or "none")
    return applied
