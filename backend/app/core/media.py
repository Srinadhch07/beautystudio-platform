"""Uploaded-file validation and safe object-key construction.

The browser-supplied ``Content-Type`` and the filename extension are both
attacker-controlled, so neither is trusted here. A file is accepted only when

1. it is non-empty and within the configured size limit,
2. its leading bytes match one of a small set of known image signatures, and
3. the declared ``Content-Type`` agrees with what those bytes actually are.

Step 3 is the one that matters. Without it a request can send
``Content-Type: image/png`` together with HTML or an executable and have it
stored under a public URL, which is a stored-XSS / drive-by-download vector. The
extension used in the S3 key is derived from the *sniffed* type, so a file called
``payload.png`` cannot end up as ``payload.svg``.

SVG is rejected on purpose. It is an XML document that can carry inline
``<script>``, event handlers and external references, and serving one from the
site's own origin would be a same-origin script injection. If vector artwork is
needed later it should be sanitised by a dedicated tool and stored as a raster
format, not accepted as raw SVG.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Final, Literal, get_args

from app.core.errors import (
    InvalidMediaError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)

#: The only media categories that may appear as a path segment in an object key.
#: A closed set is what keeps user input out of the key namespace: anything not
#: listed here is rejected rather than sanitised, so ``../`` and bucket-relative
#: prefixes can never be smuggled in.
MEDIA_CATEGORIES: Final[tuple[str, ...]] = (
    "logo",
    "gallery",
    "service",
    "offer",
    "general",
)

MediaCategory = Literal["logo", "gallery", "service", "offer", "general"]

DEFAULT_MEDIA_CATEGORY: Final[MediaCategory] = "general"

#: Key namespace for every object this application owns.
MEDIA_KEY_PREFIX: Final[str] = "media"

#: Characters permitted in a generated key. Enforced on *generation* and then
#: re-asserted before any S3 call, so a hand-edited document cannot turn into a
#: write outside the prefix.
_SAFE_KEY_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9/_-]*\.[a-z0-9]{2,5}$")

#: A generated key segment: a uuid4 hex, i.e. 32 lowercase hex characters.
_KEY_COMPONENT_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

#: The exact shape :func:`build_object_key` produces. Re-asserted before every
#: S3 call, so a hand-edited or tampered key cannot redirect a delete at an
#: arbitrary object.
_UUID_HEX_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{32}$")

#: How many leading bytes are needed to classify a file.
_SIGNATURE_LENGTH: Final[int] = 32


@dataclass(frozen=True, slots=True)
class ImageFormat:
    """One accepted image type and how to recognise it."""

    content_type: str
    extension: str
    #: ``(offset, bytes)`` pairs that must all match at their offsets.
    signature: tuple[tuple[int, bytes], ...]


def _signature(content_type: str, extension: str, *parts: tuple[int, bytes]) -> ImageFormat:
    return ImageFormat(content_type=content_type, extension=extension, signature=parts)


#: Accepted image formats. WebP is ``RIFF....WEBP``: the container and the form
#: type are both checked, because ``RIFF`` alone is also a WAV file.
IMAGE_FORMATS: Final[dict[str, ImageFormat]] = {
    image.content_type: image
    for image in (
        _signature("image/jpeg", "jpg", (0, b"\xff\xd8\xff")),
        _signature("image/png", "png", (0, b"\x89PNG\r\n\x1a\n")),
        _signature("image/webp", "webp", (0, b"RIFF"), (8, b"WEBP")),
    )
}

#: Signatures that must be refused with a pointed message rather than the generic
#: "unsupported type" one. Detecting them explicitly is what stops someone
#: re-labelling an executable as an image and still getting a clear refusal.
_BLOCKED_SIGNATURES: Final[tuple[tuple[str, tuple[tuple[int, bytes], ...]], ...]] = (
    ("executable", ((0, b"MZ"),)),  # DOS/PE: .exe .dll .scr
    ("executable", ((0, b"\x7fELF"),)),  # Linux ELF
    ("executable", ((0, b"\xcf\xfa\xed\xfe"),)),  # Mach-O 64-bit
    ("executable", ((0, b"\xca\xfe\xba\xbe"),)),  # Java class / Mach-O fat
    ("executable", ((0, b"#!"),)),  # script with a shebang
    ("script", ((0, b"<?xml"),)),  # XML, which is how SVG starts
    ("script", ((0, b"<svg"),)),
    ("script", ((0, b"<!doctype html"),)),
    ("script", ((0, b"<html"),)),
    ("script", ((0, b"<script"),)),
    ("script", ((0, b"<head"),)),
    ("script", ((0, b"<body"),)),
    ("document", ((0, b"%PDF-"),)),
)

#: ``application/pdf`` and the generic octet-stream are called out because
#: "unsupported media type" reads like a client mistake when the real problem is
#: that a document was uploaded to an image endpoint.
_DOCUMENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "application/pdf",
        "text/html",
        "text/plain",
        "application/octet-stream",
        "application/x-msdownload",
        "application/x-executable",
        "image/svg+xml",
    }
)

_SUPPORTED_EXTENSIONS: Final[frozenset[str]] = frozenset(
    format.extension for format in IMAGE_FORMATS.values()
)


@dataclass(frozen=True, slots=True)
class ValidatedImage:
    """An upload that passed every check."""

    content_type: str
    extension: str
    size_bytes: int


def _matches(prefix: bytes, spec: tuple[tuple[int, bytes], ...]) -> bool:
    return all(prefix[offset : offset + len(magic)] == magic for offset, magic in spec)


def normalise_declared_type(declared: str | None) -> str:
    """Reduce a client-supplied content type to a bare lowercase type.

    ``image/jpeg; charset=binary`` and ``IMAGE/JPEG`` both normalise to
    ``image/jpeg``. An unparseable value is returned stripped and lowercased so
    it fails the allowlist check below with a clean message.
    """
    if not declared:
        return ""
    return declared.split(";", 1)[0].strip().lower()


def _describe_blocked(kind: str) -> str:
    return {
        "executable": "Executable and script files cannot be uploaded.",
        "script": "SVG, HTML and XML files cannot be uploaded.",
        "document": "Documents cannot be uploaded to a media endpoint.",
    }[kind]


def validate_image_bytes(
    data: bytes,
    *,
    declared_content_type: str | None,
    max_bytes: int,
) -> ValidatedImage:
    """Check an in-memory upload and report its real type.

    Raises :class:`PayloadTooLargeError`, :class:`UnsupportedMediaTypeError` or
    :class:`InvalidMediaError`; all three carry a fixed, safe message.
    """
    if not data:
        raise InvalidMediaError("The uploaded file is empty.")

    if len(data) > max_bytes:
        raise PayloadTooLargeError(
            f"The uploaded file exceeds the {max_bytes // (1024 * 1024)} MB limit."
        )

    prefix = data[:_SIGNATURE_LENGTH]

    for kind, spec in _BLOCKED_SIGNATURES:
        if _matches(prefix, spec):
            raise UnsupportedMediaTypeError(_describe_blocked(kind))

    sniffed: ImageFormat | None = next(
        (image for image in IMAGE_FORMATS.values() if _matches(prefix, image.signature)),
        None,
    )
    if sniffed is None:
        raise UnsupportedMediaTypeError(
            "Only JPEG, PNG and WebP images are accepted, verified by file signature."
        )

    declared = normalise_declared_type(declared_content_type)
    if not declared:
        raise InvalidMediaError("The upload did not declare a content type.")
    if declared != sniffed.content_type:
        # Either an unsupported type or a spoof: the bytes are authoritative, so
        # the declared type is what gets reported as wrong.
        if declared in _DOCUMENT_TYPES:
            raise UnsupportedMediaTypeError(_describe_blocked("document"))
        raise UnsupportedMediaTypeError(
            f"Declared content type '{declared}' does not match the file's actual "
            f"content type '{sniffed.content_type}'."
        )

    return ValidatedImage(
        content_type=sniffed.content_type,
        extension=sniffed.extension,
        size_bytes=len(data),
    )


def validate_media_category(value: str | None) -> MediaCategory:
    """Return a validated category, defaulting to ``general``.

    Raises :class:`InvalidMediaError` for an unrecognised value instead of
    silently coercing it: a typo in a category should be visible, not quietly
    filed under ``general``.
    """
    if value is None or not value.strip():
        return DEFAULT_MEDIA_CATEGORY
    candidate = value.strip().lower()
    if candidate not in MEDIA_CATEGORIES:
        raise InvalidMediaError(f"'category' must be one of: {', '.join(MEDIA_CATEGORIES)}.")
    return candidate  # type: ignore[return-value]


def build_object_key(category: str, extension: str, *, token: str) -> str:
    """Build ``media/{category}/{token}.{extension}``.

    ``token`` is supplied by the caller (a ``uuid4().hex``) rather than generated
    here so the caller can log or test the exact key it produced.

    The user-provided filename is *not* part of the key. Filenames are attacker
    controlled and can contain path separators, unicode homoglyphs or a
    pre-existing extension, so deriving the key from one would make the key
    namespace unpredictable.
    """
    if category not in MEDIA_CATEGORIES:
        raise ValueError(f"unknown media category: {category!r}")
    if extension.lower() not in _SUPPORTED_EXTENSIONS:
        raise ValueError(f"unsupported image extension: {extension!r}")
    if not _UUID_HEX_RE.match(token):
        raise ValueError("object key token must be 32 lowercase hexadecimal characters")
    return f"{MEDIA_KEY_PREFIX}/{category}/{token}.{extension.lower()}"


def is_safe_object_key(key: str) -> bool:
    """Return ``True`` when ``key`` sits inside the media namespace.

    The check is deliberately strict - prefix, category, a 32-character
    lowercase-hex token and a supported extension must all match. Re-checked
    immediately before every S3 call so a corrupted or hand-edited document
    cannot direct a delete at an arbitrary key in the bucket.
    """
    if not key or not _SAFE_KEY_RE.match(key):
        return False
    parts = key.split("/")
    if len(parts) != 3:
        return False
    prefix, category, name = parts
    if prefix != MEDIA_KEY_PREFIX or category not in MEDIA_CATEGORIES:
        return False
    token, _, extension = name.rpartition(".")
    return bool(_UUID_HEX_RE.match(token)) and extension in _SUPPORTED_EXTENSIONS


def available_categories() -> tuple[str, ...]:
    """Public, JSON-friendly view of :data:`MEDIA_CATEGORIES`."""
    return MEDIA_CATEGORIES


def is_known_category(value: str) -> bool:
    """``True`` when ``value`` is an accepted category (used by schema validators)."""
    return value in get_args(MediaCategory)


#: Chunk size for bounded reads. Small enough that the read-ahead cost is
#: negligible, large enough that the per-call overhead stays irrelevant.
READ_CHUNK_SIZE: Final[int] = 64 * 1024


async def read_upload_limited(source: Any, max_bytes: int) -> bytes:
    """Read at most ``max_bytes + 1`` bytes from ``source``.

    ``source`` is anything with an async ``read(size)`` - a FastAPI
    ``UploadFile`` qualifies. The extra byte is what makes the size check
    possible: the reader stops as soon as the payload is provably over the limit
    instead of buffering an arbitrarily large body first, so a client cannot
    exhaust server memory by declaring a small limit and sending a huge file.
    """
    chunks: list[bytes] = []
    total = 0
    ceiling = max_bytes + 1
    while total < ceiling:
        chunk = await source.read(min(READ_CHUNK_SIZE, ceiling - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    if total > max_bytes:
        raise PayloadTooLargeError(
            f"The uploaded file exceeds the {max_bytes // (1024 * 1024)} MB limit."
        )
    return b"".join(chunks)


def sanitise_original_filename(raw: str | None, *, max_length: int) -> str | None:
    """Reduce a client-supplied filename to a safe, display-only string.

    Only the final path component is kept, so a value like
    ``../../etc/passwd`` becomes ``passwd``. Control characters and shell
    metacharacters are dropped and the result is truncated. The value is only
    ever shown back to an admin - it is never used to build a key or a path.
    """
    if not raw:
        return None
    candidate = raw.replace("\\", "/").rsplit("/", 1)[-1].strip()
    cleaned = "".join(char for char in candidate if char.isprintable()).strip(" .")
    if not cleaned:
        return None
    return cleaned[:max_length]
