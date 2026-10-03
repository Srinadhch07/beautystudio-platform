"""Pytest fixtures.

Three guarantees:

1. The real database configured in ``.env`` (MongoDB Atlas) is **never**
   contacted. ``MONGO_URI`` is pointed at an unreachable local port, so the
   start-up probe fails fast and harmlessly.
2. Every request runs against an in-memory MongoDB via ``mongomock_motor``, so
   tests are fast, deterministic and cannot modify production data.
3. The in-memory database is **fresh per test**, so an admin created by one test
   cannot authenticate in another.

Authentication model for the suite
----------------------------------
``client`` is the *unauthenticated* base client. ``auth_client`` is that same
client carrying a real signed-in session, and it is what the admin CRUD tests
use.

Defaulting the CRUD tests to an authenticated client is convenient, but it means
those tests would still pass if a route silently lost its protection. That
regression is therefore covered explicitly instead, by
``test_auth.py::test_every_admin_route_requires_authentication``, which walks
the real route table with no session. That is a stronger guarantee than hoping
dozens of individual tests notice.

The client is served over ``https://`` on purpose: the test environment sets
``COOKIE_SECURE=true``, and a client on ``http://`` makes httpx silently refuse
to store the session cookie, so every auth test would fail for a reason that has
nothing to do with authentication.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable, Iterator
from typing import Any

_TEST_ENV = {
    "APP_NAME": "Beauty Parlour Test",
    "APP_VERSION": "0.0.0-test",
    "DEBUG": "true",
    "LOG_LEVEL": "WARNING",
    "API_PREFIX": "/api",
    # Deliberately unreachable: proves the app degrades gracefully and keeps
    # the suite from ever touching the configured Atlas instance.
    "MONGO_URI": "mongodb://127.0.0.1:27099",
    "MONGO_DB_NAME": "beauty_parlour_test",
    "MONGO_TIMEOUT_MS": "200",
    "CORS_ORIGINS": "http://localhost:5173,http://localhost:4173",
    "JWT_SECRET": "unit-test-secret-value-not-a-real-credential",
    "JWT_ACCESS_MINUTES": "30",
    "COOKIE_SECURE": "true",
    "COOKIE_SAMESITE": "none",
    # https, to match COOKIE_SECURE=true. A mismatch here would (correctly)
    # trip the start-up transport warning and would not model a working deploy.
    "FRONTEND_URL": "https://localhost:5173",
    "PASSWORD_RESET_MINUTES": "30",
    "LOGIN_RATE_LIMIT_MAX": "5",
    "LOGIN_RATE_LIMIT_WINDOW_MINUTES": "15",
    "STORAGE_MODE": "s3",
    "AWS_REGION": "eu-west-1",
    "AWS_S3_BUCKET": "test-bucket",
    "AWS_ACCESS_KEY_ID": "test-access-key-id",
    "AWS_SECRET_ACCESS_KEY": "test-secret-access-key",
    "SMTP_HOST": "localhost",
    "SMTP_PORT": "1025",
    "SMTP_FROM_EMAIL": "no-reply@test.invalid",
}

for _key, _value in _TEST_ENV.items():
    os.environ[_key] = _value

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402

from app.api.deps import get_database, get_s3_storage_service  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.cookies import CSRF_HEADER_NAME  # noqa: E402
from app.core.passwords import hash_password  # noqa: E402
from app.core.rate_limit import reset_login_rate_limiter  # noqa: E402
from app.main import app  # noqa: E402
from app.models.admin import AdminDocument  # noqa: E402
from app.repositories.admins import AdminsRepository  # noqa: E402
from app.storage.s3 import S3StorageService, reset_s3_clients  # noqa: E402

#: Base URL. https so that ``COOKIE_SECURE=true`` cookies are actually sent.
BASE_URL = "https://testserver"

LOGIN_PATH = "/api/v1/auth/login"
ME_PATH = "/api/v1/auth/me"

#: Long enough to satisfy the strength rules and obviously not a real secret.
#: The domain must not be a reserved/special-use name, which ``EmailStr`` rejects.
ADMIN_EMAIL = "owner@beautyparlour.app"
ADMIN_PASSWORD = "correct-horse-battery-staple-9"
ADMIN_NAME = "Test Owner"


def run(coroutine: Any) -> Any:
    """Drive one coroutine to completion from a synchronous test."""
    return asyncio.run(coroutine)


@pytest.fixture(autouse=True)
def _isolate_rate_limiter() -> Iterator[None]:
    """Keep the process-wide login limiter from leaking between tests.

    Without this, the rate-limit test would exhaust the shared bucket and every
    later test in the session would fail with 429 for a reason of its own.
    """
    reset_login_rate_limiter()
    yield
    reset_login_rate_limiter()


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture()
def memory_database() -> Iterator[object]:
    """A fresh, empty in-memory database for every test."""
    client = AsyncMongoMockClient()
    yield client["beauty_parlour_test"]


@pytest.fixture()
def make_admin(memory_database: object) -> Callable[..., AdminDocument]:
    """Factory that provisions an admin straight into the in-memory database.

    Writes through the repository rather than over HTTP, so the suite needs no
    bootstrapping endpoint and the CLI stays the only account-creating path.

    Pass ``password=None`` together with ``password_hash=None`` to model a row
    that exists but has no usable credential.
    """

    def _make(
        email: str = ADMIN_EMAIL,
        name: str = ADMIN_NAME,
        password: str | None = ADMIN_PASSWORD,
        *,
        is_active: bool = True,
        password_hash: str | None = None,
    ) -> AdminDocument:
        if password_hash is None and password is not None:
            password_hash = hash_password(password)

        document = AdminDocument(
            email=email,
            name=name,
            is_active=is_active,
            password_hash=password_hash,
        )

        async def go() -> AdminDocument:
            return await AdminsRepository(memory_database).create(document)  # type: ignore[arg-type]

        return run(go())

    return _make


@pytest.fixture()
def admin(make_admin: Callable[..., AdminDocument]) -> AdminDocument:
    """A single active admin using the default credentials."""
    return make_admin()


@pytest.fixture()
def client(memory_database: object) -> Iterator[TestClient]:
    """Unauthenticated Test client wired to the in-memory database.

    ``raise_server_exceptions=False`` lets the tests assert on the 500 handler
    instead of the exception propagating out of the ASGI stack.
    """
    reset_s3_clients()
    app.dependency_overrides[get_database] = lambda: memory_database
    with TestClient(app, base_url=BASE_URL, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    reset_s3_clients()


@pytest.fixture()
def anonymous_client(client: TestClient) -> TestClient:
    """The same client with no session. Used by the protection tests."""
    return client


@pytest.fixture()
def auth_client(client: TestClient, admin: AdminDocument) -> TestClient:
    """A client with a real session cookie and the matching CSRF header.

    Authenticating for real - rather than forging a token - means the admin CRUD
    tests exercise the same login path a browser would.
    """
    response = client.post(LOGIN_PATH, json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert response.status_code == 200, response.text
    # Default header so state-changing calls carry the CSRF token. Explicit
    # per-request headers in a test still override this.
    client.headers[CSRF_HEADER_NAME] = response.json()["csrf_token"]
    return client


# -- S3 ------------------------------------------------------------------------

#: Byte strings that carry a real file signature. They are deliberately minimal:
#: validation classifies the *header* only, so the payload after the signature
#: does not need to be a decodable image. Each one starts with the bytes the
#: sniffer keys on, which is exactly what a mismatch test needs.
IMAGE_BYTES: dict[str, bytes] = {
    "jpeg": b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"\x00" * 32,
    "png": b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 32,
    "webp": b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 32,
    # Accepted signature, wrong declared type: the mismatch guard.
    "gif": b"GIF89a\x01\x00\x01\x00\x00\x00\x00," + b"\x00" * 16,
    # Refused types.
    "html": b"<!DOCTYPE html><html><script>alert(1)</script></html>",
    "svg": b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
    "xml": b'<?xml version="1.0"?><root/>',
    "exe": b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00" + b"\x00" * 16,
    "elf": b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 16,
    "shebang": b"#!/bin/sh\nrm -rf /\n",
    "pdf": b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n" + b"\x00" * 16,
    "zip": b"PK\x03\x04\x14\x00\x00\x00\x08\x00" + b"\x00" * 16,
    "text": b"just some plain text, not an image at all",
}


class FakeS3Client:
    """In-memory stand-in for the boto3 S3 client.

    Every boto3 method the application calls is implemented against a dict, so
    no test can reach a real bucket even by accident: there is no code path from
    here to AWS. ``fail_upload``/``fail_delete`` inject a botocore exception to
    exercise the error paths.

    Calls are recorded so a test can assert on what was sent, not just on the
    HTTP status the client saw.
    """

    def __init__(self) -> None:
        self.objects: dict[str, dict[str, Any]] = {}
        self.put_calls: list[dict[str, Any]] = []
        self.delete_calls: list[dict[str, Any]] = []
        self.head_calls: list[dict[str, Any]] = []
        self.fail_upload: BaseException | None = None
        self.fail_delete: BaseException | None = None
        self.fail_head: BaseException | None = None

    @property
    def bucket(self) -> str:
        return str(self.put_calls[-1]["Bucket"]) if self.put_calls else ""

    def put_object(self, **kwargs: Any) -> None:
        if self.fail_upload is not None:
            raise self.fail_upload
        self.put_calls.append(kwargs)
        self.objects[kwargs["Key"]] = kwargs

    def delete_object(self, **kwargs: Any) -> None:
        if self.fail_delete is not None:
            raise self.fail_delete
        self.delete_calls.append(kwargs)
        self.objects.pop(kwargs["Key"], None)

    def head_object(self, **kwargs: Any) -> None:
        if self.fail_head is not None:
            raise self.fail_head
        self.head_calls.append(kwargs)
        if kwargs["Key"] not in self.objects:
            raise _no_such_key(kwargs["Key"])

    @property
    def keys(self) -> list[str]:
        return sorted(self.objects)

    def clear(self) -> None:
        """Discard everything written so far, including recorded calls."""
        self.objects.clear()
        self.put_calls.clear()
        self.delete_calls.clear()
        self.head_calls.clear()
        self.fail_head = None


def _no_such_key(key: str) -> BaseException:
    """Build the botocore ``ClientError`` S3 raises for a missing key."""
    from botocore.exceptions import ClientError

    return ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": f"The specified key does not exist: {key}"}},
        "HeadObject",
    )


@pytest.fixture(autouse=True)
def _forbid_real_s3(settings) -> Iterator[FakeS3Client]:
    """Guarantee the test suite can never talk to AWS.

    The S3 service dependency is overridden with :class:`FakeS3Client` for every
    test, so the ordinary request path never constructs a real boto3 client. It
    is autouse rather than opt-in so no test can forget to request it.
    """
    fake = FakeS3Client()
    app.dependency_overrides[get_s3_storage_service] = lambda: S3StorageService(
        settings, client=fake
    )
    yield fake
    app.dependency_overrides.pop(get_s3_storage_service, None)


@pytest.fixture()
def fake_s3(_forbid_real_s3: FakeS3Client) -> FakeS3Client:
    """The in-memory S3 double for the current test.

    The override is installed by the autouse :func:`_forbid_real_s3` fixture; this
    fixture only hands tests a handle to it. It is cleared here so each test
    starts empty.
    """
    _forbid_real_s3.clear()
    return _forbid_real_s3
