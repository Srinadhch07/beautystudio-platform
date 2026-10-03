"""AWS S3 client construction and the storage service built on top of it.

Two layers live here deliberately:

* :func:`get_s3_client` - a cached, explicitly-credentialed boto3 client. Passing
  the credentials explicitly is what stops boto3 from falling back to the EC2
  instance metadata endpoint, which would be both slow and a credential leak risk
  in a misconfigured environment.
* :class:`S3StorageService` - the only place in the application that calls
  ``put_object``/``delete_object``/``head_object``. Routes and services depend on
  this class, never on boto3 directly, so there is a single translation point
  from botocore exceptions to safe API errors.

boto3 is synchronous. Uploading a few megabytes would otherwise block the event
loop and stall every other in-flight request, so each call is dispatched to a
worker thread with :func:`asyncio.to_thread`.

No method here ever returns a credential, and no exception message from botocore
is forwarded to a client: those can contain the bucket ARN, the request id and,
on some failure paths, key material.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Final
from urllib.parse import quote

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectionError as BotoConnectionError,
    EndpointConnectionError,
    NoCredentialsError,
    PartialCredentialsError,
    ReadTimeoutError,
)

from app.core.config import Settings, get_settings
from app.core.errors import (
    StorageAccessDeniedError,
    StorageError,
    StorageNotConfiguredError,
    StorageObjectNotFoundError,
    StorageUnavailableError,
)
from app.core.media import is_safe_object_key

logger = logging.getLogger(__name__)

_client: dict[str, Any] = {}

#: AWS error codes meaning "this credential is not usable for this action".
_DENIED_CODES: Final[frozenset[str]] = frozenset(
    {
        "AccessDenied",
        "AllAccessDisabled",
        "InvalidAccessKeyId",
        "SignatureDoesNotMatch",
        "ExpiredToken",
        "InvalidToken",
        "AccountProblem",
    }
)

#: AWS error codes meaning "the object is not there".
_NOT_FOUND_CODES: Final[frozenset[str]] = frozenset(
    {
        "NoSuchKey",
        "NoSuchBucket",
        "NotFound",
        "404",
    }
)


class StorageConfigurationError(RuntimeError):
    """Raised when required storage settings are missing or invalid."""


def is_s3_configured(settings: Settings | None = None) -> bool:
    """Return ``True`` when credentials and a bucket name are present."""
    settings = settings or get_settings()
    return bool(
        settings.aws_access_key_id.get_secret_value()
        and settings.aws_secret_access_key.get_secret_value()
        and settings.aws_s3_bucket
    )



def get_s3_client(settings: Settings | None = None) -> Any:
    """Return a cached S3 client.

    Credentials are always passed explicitly, which prevents boto3 from
    falling back to the EC2 instance metadata endpoint.
    """
    settings = settings or get_settings()
    cache_key = f"{settings.aws_region}:{settings.aws_s3_bucket}"
    cached = _client.get(cache_key)
    if cached is not None:
        return cached

    if not is_s3_configured(settings):
        raise StorageConfigurationError(
            "AWS S3 is not configured. Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY "
            "and AWS_S3_BUCKET, or use STORAGE_MODE=local for development."
        )

    client = boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id.get_secret_value(),
        aws_secret_access_key=settings.aws_secret_access_key.get_secret_value(),
        config=BotoConfig(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=settings.mongo_timeout_ms / 1000,
            read_timeout=30,
        ),
    )
    _client[cache_key] = client
    logger.debug("S3 client initialised for region %r", settings.aws_region)
    return client


def get_bucket_name(settings: Settings | None = None) -> str:
    """Return the configured bucket name."""
    settings = settings or get_settings()
    if not settings.aws_s3_bucket:
        raise StorageConfigurationError("AWS_S3_BUCKET is not configured")
    return settings.aws_s3_bucket


def reset_s3_clients() -> None:
    """Drop cached clients (used by tests)."""
    _client.clear()


def _aws_error_code(exc: ClientError) -> str:
    """Pull the stable AWS error code out of a ``ClientError``.

    Only the code is used. ``Error.Message`` can echo the request, the key and
    account identifiers, so it is deliberately never propagated.
    """
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return ""
    error = response.get("Error")
    if not isinstance(error, dict):
        return ""
    code = error.get("Code", "")
    return code if isinstance(code, str) else ""


def _translate_storage_error(exc: Exception, *, operation: str, key: str) -> Exception:
    """Map a boto3/botocore failure onto a safe application error.

    The original exception type and the AWS error code are logged (never the
    message), because those are the two pieces of information an operator
    actually needs and neither contains a secret.
    """
    code = _aws_error_code(exc) if isinstance(exc, ClientError) else ""

    if isinstance(exc, NoCredentialsError | PartialCredentialsError | StorageConfigurationError):
        logger.error("S3 %s rejected: storage is not configured", operation)
        return StorageNotConfiguredError()

    if isinstance(exc, ClientError):
        logger.error("S3 %s failed for %r (aws_code=%s)", operation, key, code or "unknown")
        if code in _DENIED_CODES:
            return StorageAccessDeniedError()
        if code in _NOT_FOUND_CODES:
            return StorageObjectNotFoundError()
        return StorageError()

    if isinstance(exc, EndpointConnectionError | BotoConnectionError | ReadTimeoutError):
        # Network-level: the bucket is fine, this server just cannot reach it.
        logger.warning("S3 %s could not reach storage for %r (%s)", operation, key, type(exc).__name__)
        return StorageUnavailableError()

    if isinstance(exc, BotoCoreError):
        logger.error("S3 %s failed for %r (%s)", operation, key, type(exc).__name__)
        return StorageError()

    # Not a boto3 failure at all - re-raise so the global handler deals with it.
    return exc


class S3StorageService:
    """Upload, delete, inspect and address objects in the configured bucket.

    The client is resolved lazily so that constructing the service never performs
    I/O, and so tests can inject a stand-in with ``client=`` without any
    monkeypatching of module globals.
    """

    def __init__(self, settings: Settings | None = None, *, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client

    # -- Plumbing ------------------------------------------------------------

    def _resolve_settings(self) -> Settings:
        return self._settings or get_settings()

    def _resolve_client(self) -> Any:
        if self._client is None:
            try:
                self._client = get_s3_client(self._resolve_settings())
            except StorageConfigurationError as exc:
                raise _translate_storage_error(exc, operation="connect", key="-") from exc
        return self._client

    def _bucket(self) -> str:
        try:
            return get_bucket_name(self._resolve_settings())
        except StorageConfigurationError as exc:
            raise _translate_storage_error(exc, operation="connect", key="-") from exc

    @staticmethod
    def _require_safe_key(key: str) -> None:
        """Refuse to operate on a key outside the ``media/`` namespace.

        Keys are generated by the application, but they are persisted in
        documents that a human can also edit. Re-validating here means a
        corrupted or tampered key can never be turned into a delete against an
        arbitrary object in the bucket.
        """
        if not is_safe_object_key(key):
            raise StorageError("Refusing to operate on an unrecognised object key.")

    # -- Operations ----------------------------------------------------------

    def _put_object(self, key: str, data: bytes, content_type: str) -> None:
        self._require_safe_key(key)
        client, bucket = self._resolve_client(), self._bucket()
        try:
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                # A browser must never be talked into executing what we stored.
                ContentDisposition="inline",
                CacheControl="public, max-age=31536000, immutable",
            )
        except Exception as exc:  # noqa: BLE001 - re-raised as an AppError
            raise _translate_storage_error(exc, operation="upload", key=key) from exc

    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        """Store ``data`` under ``key`` and return the object's public URL.

        ``ContentType`` is taken from the sniffed file signature by the caller,
        never from the request, so the object is served with the type its bytes
        actually are.
        """
        await asyncio.to_thread(self._put_object, key, data, content_type)
        logger.info("Uploaded media object %r (%d bytes)", key, len(data))
        return self.public_url(key)

    def _delete_object(self, key: str) -> None:
        self._require_safe_key(key)
        client, bucket = self._resolve_client(), self._bucket()
        try:
            client.delete_object(Bucket=bucket, Key=key)
        except Exception as exc:  # noqa: BLE001 - re-raised as an AppError
            raise _translate_storage_error(exc, operation="delete", key=key) from exc

    async def delete(self, key: str) -> None:
        """Remove an object.

        S3's ``delete_object`` is idempotent and returns success for a key that
        is already absent, so deleting twice is not an error. Callers that need
        to know whether the object was really there should use :meth:`exists`.
        """
        await asyncio.to_thread(self._delete_object, key)
        logger.info("Deleted media object %r", key)

    def _head_object(self, key: str) -> bool:
        self._require_safe_key(key)
        client, bucket = self._resolve_client(), self._bucket()
        try:
            client.head_object(Bucket=bucket, Key=key)
        except Exception as exc:  # noqa: BLE001 - re-raised as an AppError
            translated = _translate_storage_error(exc, operation="exists", key=key)
            if isinstance(translated, StorageObjectNotFoundError):
                return False
            raise translated from exc
        return True

    async def exists(self, key: str) -> bool:
        """Return whether the object is present in the bucket."""
        return await asyncio.to_thread(self._head_object, key)

    def public_url(self, key: str) -> str:
        """Return the object's HTTPS address.

        Phase 1 uses the bucket's own virtual-hosted endpoint - the simplest
        thing that works, with no distribution and no signing.

        If a CDN is introduced later, this is the single method to change: a
        CloudFront base would be substituted here, and because every stored
        ``image_url`` is produced by this function rather than by a caller, the
        switch would not need a data migration.
        """
        settings = self._resolve_settings()
        bucket = self._bucket()
        region = settings.aws_region or "us-east-1"
        # ``safe="/"`` keeps the path separators; everything else is escaped, so
        # a key can never alter the host part of the URL.
        return f"https://{quote(bucket, safe='')}.s3.{region}.amazonaws.com/{quote(key, safe='/')}"

