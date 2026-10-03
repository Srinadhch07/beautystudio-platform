"""MongoDB client / database factory."""

from __future__ import annotations

import logging
from typing import Any

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

Document = dict[str, Any]

_client: AsyncMongoClient[Document] | None = None


def get_client(settings: Settings | None = None) -> AsyncMongoClient[Document]:
    """Return the lazily created async client.

    Instantiating a client does not open a socket, so this is safe to call
    during start-up and in unit tests without a running MongoDB server.
    """
    global _client
    if _client is None:
        settings = settings or get_settings()
        _client = AsyncMongoClient(
            settings.mongo_uri.get_secret_value(),
            serverSelectionTimeoutMS=settings.mongo_timeout_ms,
            connectTimeoutMS=settings.mongo_timeout_ms,
            appname=settings.app_name,
            tz_aware=True,
        )
        logger.debug("MongoDB client initialised for database %r", settings.mongo_db_name)
    return _client


def get_database(settings: Settings | None = None) -> AsyncDatabase[Document]:
    """Return the configured application database handle."""
    settings = settings or get_settings()
    return get_client(settings)[settings.mongo_db_name]


async def init_database(settings: Settings | None = None) -> bool:
    """Create the client and probe the server. Never raises.

    Called from the application lifespan so the client is always bound to the
    same event loop that later serves requests and closes it.
    """
    reachable = await ping_database(settings)
    if reachable:
        logger.info("MongoDB reachable (database=%s)", (settings or get_settings()).mongo_db_name)
    return reachable


async def ping_database(settings: Settings | None = None) -> bool:
    """Check reachability. Never raises and never logs the connection string."""
    try:
        await get_client(settings).admin.command("ping")
    except Exception as exc:  # noqa: BLE001 - connectivity probe must not fail start-up
        # Only the exception type is logged; messages may embed host details.
        logger.warning("MongoDB is not reachable (%s)", type(exc).__name__)
        return False
    return True


async def close_database() -> None:
    """Close the client and drop the cached handle.

    The client is bound to the event loop that created it, so any mismatch is
    reported rather than allowed to break application shutdown.
    """
    global _client
    client, _client = _client, None
    if client is None:
        return
    try:
        await client.close()
    except Exception as exc:  # noqa: BLE001 - shutdown must always complete
        logger.warning("MongoDB client did not close cleanly (%s)", type(exc).__name__)
    else:
        logger.debug("MongoDB client closed")
