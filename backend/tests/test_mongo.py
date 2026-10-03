"""MongoDB wiring tests.

No live server is required: creating an async client does not open a socket.
"""

from __future__ import annotations

import asyncio

import pytest

from app.core.config import Settings
from app.db import mongo

UNREACHABLE_URI = "mongodb://127.0.0.1:27099"


@pytest.fixture(autouse=True)
def _reset_client():
    mongo._client = None
    yield
    mongo._client = None


def test_client_is_created_lazily_without_connecting() -> None:
    client = mongo.get_client(Settings(MONGO_URI=UNREACHABLE_URI))

    assert client is not None
    assert mongo.get_client() is client


def test_database_handle_uses_configured_name() -> None:
    database = mongo.get_database(Settings(MONGO_DB_NAME="unit_test_db"))

    assert database.name == "unit_test_db"


def test_connection_string_credentials_are_never_exposed() -> None:
    client = mongo.get_client(
        Settings(MONGO_URI="mongodb://some-user:some-password@127.0.0.1:27099/admin")
    )

    assert "some-password" not in repr(client)
    assert "some-user" not in repr(client)


async def _ping_and_close(uri: str) -> bool:
    result = await mongo.ping_database(Settings(MONGO_URI=uri))
    await mongo.close_database()
    return result


def test_ping_reports_unreachable_instead_of_raising() -> None:
    # create -> ping -> close must share one event loop: AsyncMongoClient is
    # bound to the loop that created it.
    result = asyncio.run(_ping_and_close(UNREACHABLE_URI))

    assert result is False
