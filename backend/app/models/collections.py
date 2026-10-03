"""Collection names and the index definitions created at start-up."""

from __future__ import annotations

from pymongo import ASCENDING, DESCENDING, IndexModel

ADMINS = "admins"
SITE_SETTINGS = "site_settings"
SERVICES = "services"
GALLERY = "gallery"
TESTIMONIALS = "testimonials"
OFFERS = "offers"

#: Every collection owned by the application, in creation order.
ALL_COLLECTIONS: tuple[str, ...] = (
    ADMINS,
    SITE_SETTINGS,
    SERVICES,
    GALLERY,
    TESTIMONIALS,
    OFFERS,
)

#: Only indexes the application actually queries through are declared.
#:
#: * ordered content is always filtered by ``is_active`` and sorted by
#:   ``display_order``, so one compound index serves both;
#: * the public testimonial feed filters on ``status`` + ``is_visible`` and
#:   sorts by recency;
#: * ``site_settings.singleton_key`` is unique, which is what guarantees a
#:   single settings document.
COLLECTION_INDEXES: dict[str, list[IndexModel]] = {
    ADMINS: [
        IndexModel([("email", ASCENDING)], unique=True, name="uniq_email"),
    ],
    SITE_SETTINGS: [
        IndexModel([("singleton_key", ASCENDING)], unique=True, name="uniq_singleton_key"),
    ],
    SERVICES: [
        IndexModel(
            [("is_active", ASCENDING), ("display_order", ASCENDING)],
            name="active_display_order",
        ),
    ],
    GALLERY: [
        IndexModel(
            [("is_active", ASCENDING), ("display_order", ASCENDING)],
            name="active_display_order",
        ),
    ],
    TESTIMONIALS: [
        IndexModel(
            [("status", ASCENDING), ("is_visible", ASCENDING), ("created_at", DESCENDING)],
            name="moderation_recency",
        ),
    ],
    OFFERS: [
        IndexModel(
            [("is_active", ASCENDING), ("display_order", ASCENDING)],
            name="active_display_order",
        ),
    ],
}
