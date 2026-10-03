"""Site settings repository: enforces the single-document invariant.

The unique index on ``singleton_key`` (see ``app.models.collections``) is the
last line of defence; the queries below additionally target that key so a
second document can never be addressed by accident.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pymongo import ReturnDocument

from app.models.base import to_bson_value, utcnow
from app.models.collections import SITE_SETTINGS
from app.models.site_settings import SINGLETON_KEY, SiteSettingsDocument
from app.repositories.base import BaseRepository

#: Never written through ``$set`` - ``created_at`` must survive updates.
IMMUTABLE_FIELDS = frozenset({"_id", "id", "created_at", "updated_at"})


class SiteSettingsRepository(BaseRepository[SiteSettingsDocument]):
    """Access to the one and only settings document."""

    collection_name = SITE_SETTINGS
    document_type = SiteSettingsDocument

    async def find_singleton(self) -> SiteSettingsDocument | None:
        return await self.find_one({"singleton_key": SINGLETON_KEY})

    async def get_or_create(self, default_business_name: str) -> SiteSettingsDocument:
        """Return the settings, seeding them on first access.

        A single atomic upsert, so concurrent first-time requests cannot create
        duplicates and a read never modifies stored content.
        """
        defaults = SiteSettingsDocument(business_name=default_business_name).to_mongo(
            include_id=False
        )
        return await self.upsert_by({"singleton_key": SINGLETON_KEY}, defaults)

    async def replace(self, values: Mapping[str, Any]) -> SiteSettingsDocument:
        """Create or overwrite the settings document, preserving ``created_at``."""
        payload = to_bson_value(
            {key: value for key, value in values.items() if key not in IMMUTABLE_FIELDS}
        )
        now = utcnow()

        raw = await self._collection.find_one_and_update(
            {"singleton_key": SINGLETON_KEY},
            {
                "$set": {**payload, "singleton_key": SINGLETON_KEY, "updated_at": now},
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return SiteSettingsDocument.from_mongo(raw)
