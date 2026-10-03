"""Index definitions and idempotent index creation.

The in-memory database records index metadata but does not enforce uniqueness,
so these tests assert on the index specifications actually sent to MongoDB
rather than on enforcement behaviour.
"""

from __future__ import annotations

import asyncio

from mongomock_motor import AsyncMongoMockClient

from app.db.indexes import COLLECTION_INDEXES, ensure_indexes
from app.models.collections import (
    ADMINS,
    GALLERY,
    OFFERS,
    SERVICES,
    SITE_SETTINGS,
    TESTIMONIALS,
)


def run(coroutine):
    """Drive one coroutine to completion from a synchronous test."""
    return asyncio.run(coroutine)


def indexed(database, collection_name: str):
    """Index metadata for a collection (excluding the implicit ``_id_``)."""
    info = run(database[collection_name].index_information())
    return {name: spec for name, spec in info.items() if name != "_id_"}


def test_ensure_indexes_creates_expected_indexes() -> None:
    database = AsyncMongoMockClient()["test"]

    run(ensure_indexes(database))

    assert "uniq_email" in indexed(database, ADMINS)
    assert "uniq_singleton_key" in indexed(database, SITE_SETTINGS)
    assert "active_display_order" in indexed(database, SERVICES)
    assert "active_display_order" in indexed(database, GALLERY)
    assert "active_display_order" in indexed(database, OFFERS)
    assert "moderation_recency" in indexed(database, TESTIMONIALS)


def test_ensure_indexes_is_idempotent() -> None:
    database = AsyncMongoMockClient()["test"]

    run(ensure_indexes(database))
    first = {name: set(indexed(database, name)) for name in COLLECTION_INDEXES}
    run(ensure_indexes(database))
    second = {name: set(indexed(database, name)) for name in COLLECTION_INDEXES}

    assert first == second


def test_admin_email_index_is_unique() -> None:
    database = AsyncMongoMockClient()["test"]

    run(ensure_indexes(database))

    assert indexed(database, ADMINS)["uniq_email"]["unique"] is True


def test_site_settings_singleton_index_is_unique() -> None:
    database = AsyncMongoMockClient()["test"]

    run(ensure_indexes(database))

    assert indexed(database, SITE_SETTINGS)["uniq_singleton_key"]["unique"] is True


def test_public_listing_index_leads_with_is_active() -> None:
    """The public query filters on is_active, so it must be the index prefix."""
    database = AsyncMongoMockClient()["test"]

    run(ensure_indexes(database))

    for collection in (SERVICES, GALLERY, OFFERS):
        spec = indexed(database, collection)["active_display_order"]
        keys = [field for field, _direction in spec["key"]]
        assert keys == ["is_active", "display_order"], collection


def test_only_necessary_collections_are_indexed() -> None:
    assert set(COLLECTION_INDEXES) == {
        ADMINS,
        SITE_SETTINGS,
        SERVICES,
        GALLERY,
        TESTIMONIALS,
        OFFERS,
    }
