"""Shared building blocks for MongoDB document models.

Two problems are solved here:

1. ``ObjectId`` handling. MongoDB identifiers must never leak into JSON as raw
   objects, so :data:`PyObjectId` validates strings/ObjectIds and serialises to
   a plain string. The custom core schema means response schemas do **not** need
   ``arbitrary_types_allowed``.
2. BSON compatibility. Python ``Decimal`` and ``Enum`` values have no BSON
   encoding, so :func:`to_bson_value` converts them (``Decimal`` ->
   ``Decimal128``) on the way into MongoDB and back on the way out.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, TypeVar

from bson import Decimal128, ObjectId
from pydantic import (
    AnyHttpUrl,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    TypeAdapter,
)
from pydantic.networks import AnyUrl
from pydantic_core import core_schema


def utcnow() -> datetime:
    """Timezone-aware current UTC time. The single source of "now"."""
    return datetime.now(UTC)


def _ensure_utc(value: Any) -> Any:
    """Interpret a naive datetime as UTC.

    Every stored timestamp is UTC. Drivers and hand-written imports can hand
    back a naive value, and comparing a naive datetime with an aware one raises
    ``TypeError`` deep inside a validator, so the conversion is done at the
    model boundary where it is cheap to reason about.
    """
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


#: ``datetime`` guaranteed to be timezone-aware UTC.
UtcDateTime = Annotated[datetime, BeforeValidator(_ensure_utc)]


def _validate_object_id(value: Any) -> ObjectId:
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    raise ValueError("value must be a 24-character hexadecimal ObjectId")


class _ObjectIdAnnotation:
    """Pydantic v2 hook so ``ObjectId`` works in any model."""

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any) -> core_schema.CoreSchema:
        return core_schema.no_info_plain_validator_function(
            _validate_object_id,
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda value: str(value),
                return_schema=core_schema.str_schema(),
                when_used="json",
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(cls, schema: Any, handler: Any) -> dict[str, Any]:
        return {"type": "string", "examples": ["665f1b2c9e1d4a3f7c8b9a01"]}


#: ``ObjectId`` that is always a string in JSON.
PyObjectId = Annotated[ObjectId, _ObjectIdAnnotation]


def _coerce_decimal(value: Any) -> Any:
    if isinstance(value, Decimal128):
        return value.to_decimal()
    if isinstance(value, bool):  # bool is an int subclass; reject explicitly
        raise ValueError("a boolean is not a valid amount")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | str):
        try:
            return Decimal(str(value).strip())
        except (ArithmeticError, ValueError) as exc:
            # ``decimal.InvalidOperation`` is an ArithmeticError, not a
            # ValueError, so pydantic would not convert it into a 422 unless it
            # is re-raised as one here.
            raise ValueError("value must be a valid decimal number") from exc
    return value


#: ``Decimal`` that accepts BSON ``Decimal128`` on read and emits a JSON string.
Money = Annotated[
    Decimal,
    BeforeValidator(_coerce_decimal),
    PlainSerializer(lambda value: str(value), return_type=str, when_used="json"),
]

#: Non-negative monetary amount with 2 decimal places, at most 8 integer digits.
Price = Annotated[Money, Field(ge=Decimal("0"), max_digits=10, decimal_places=2)]


def _validate_http_url(value: str) -> str:
    """Accept only absolute http(s) URLs, returned as a plain ``str``.

    ``AnyHttpUrl`` would validate correctly but produces a ``Url`` object, which
    is neither a ``str`` nor BSON-encodable. This keeps stored documents plain
    strings while still rejecting ``ftp://``, ``javascript:`` and typos.
    """
    if not isinstance(value, str):  # pragma: no cover - annotation guards this
        raise ValueError("url must be a string")
    try:
        parsed = TypeAdapter(AnyHttpUrl).validate_python(value.strip())
    except ValueError as exc:
        raise ValueError("must be a valid absolute http(s) URL") from exc
    if parsed.scheme not in ("http", "https"):
        raise ValueError("must be a valid absolute http(s) URL")
    return str(parsed)


#: Absolute http(s) URL kept as a plain string so it stays BSON-friendly.
HttpUrlStr = Annotated[str, BeforeValidator(_validate_http_url), Field(max_length=500)]


def to_bson_value(value: Any) -> Any:
    """Recursively convert Python values into BSON-encodable equivalents."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return Decimal128(value)
    if isinstance(value, AnyUrl):
        # ``AnyHttpUrl`` and friends are not ``str`` subclasses, so leaving them
        # here would raise an opaque "Invalid document" error inside the driver.
        return str(value)
    if isinstance(value, dict):
        return {key: to_bson_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [to_bson_value(item) for item in value]
    return value


class StrictTextModel(BaseModel):
    """Base model that trims surrounding whitespace and ignores unknown keys."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")


DocumentT = TypeVar("DocumentT", bound="BaseDocument")


class BaseDocument(StrictTextModel):
    """Common shape of every stored document."""

    # ``populate_by_name`` is essential: the ``id`` field carries the Mongo
    # alias ``_id``, so without it ``from_mongo`` (which injects a plain ``id``
    # key) would silently fail validation and let ``default_factory=ObjectId``
    # mint a *new* identifier on every single read.
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="ignore",
        populate_by_name=True,
    )

    id: PyObjectId = Field(default_factory=ObjectId, alias="_id")
    created_at: UtcDateTime = Field(default_factory=utcnow)
    updated_at: UtcDateTime = Field(default_factory=utcnow)

    def to_mongo(self, *, include_id: bool = True) -> dict[str, Any]:
        """Serialise to a BSON-ready document.

        ``include_id=False`` is used for upserts, where MongoDB must generate
        the identifier itself.
        """
        data = to_bson_value(self.model_dump(mode="python", exclude={"id"}))
        if include_id:
            data["_id"] = self.id
        return data

    @classmethod
    def from_mongo(cls: type[DocumentT], document: dict[str, Any]) -> DocumentT:
        """Rebuild a document from a raw MongoDB result."""
        payload = dict(document)
        payload["id"] = payload.pop("_id", None) or ObjectId()
        return cls.model_validate(payload)

    def touch(self) -> None:
        """Mark the document as modified."""
        self.updated_at = utcnow()
