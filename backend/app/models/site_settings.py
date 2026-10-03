"""Site settings document: exactly one per business."""

from __future__ import annotations

import re
from typing import Literal, get_args

from pydantic import AnyHttpUrl, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.fonts import DEFAULT_FONT
from app.core.themes import DEFAULT_THEME
from app.models.base import BaseDocument, StrictTextModel

#: Stored on every settings document and covered by a unique index, which is
#: what makes the collection single-document.
SINGLETON_KEY = "site_settings"

#: Fallback business name used only when no settings document exists yet.
#: Prefer ``APP_NAME`` from the environment; see ``SiteSettingsService``.
DEFAULT_BUSINESS_NAME = "Beauty Parlour"

#: Opening hours are stored as zero-padded ``HH:MM`` strings. BSON has no
#: time-of-day type, so a ``datetime.time`` would fail to encode and a naive
#: ``datetime`` would invent a meaningless date. Zero padding also makes plain
#: string comparison equivalent to chronological comparison.
TIME_PATTERN = r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$"

#: How the hero's primary call to action behaves. A closed set rather than a
#: free-form string, so the frontend can rely on the shape of the value.
CtaBehaviour = Literal["services", "offers", "gallery", "contact", "testimonials", "book", "none"]

#: Accepted values, in the order an admin UI should present them.
CTA_BEHAVIOURS: tuple[str, ...] = get_args(CtaBehaviour)


class Address(StrictTextModel):
    """Structured postal address."""

    line1: str | None = Field(default=None, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, max_length=32)
    country: str | None = Field(default=None, max_length=120)


class OpeningHour(StrictTextModel):
    """Opening hours for one weekday.

    Unknown fields are tolerated so the shape can grow (public holidays, notes)
    without a migration.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")

    day: str = Field(min_length=1, max_length=20)
    is_closed: bool = True
    open_time: str | None = Field(default=None, pattern=TIME_PATTERN)
    close_time: str | None = Field(default=None, pattern=TIME_PATTERN)
    note: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _require_times_when_open(self) -> OpeningHour:
        if not self.is_closed and (self.open_time is None or self.close_time is None):
            raise ValueError("open_time and close_time are required when the day is not closed")
        # String comparison is safe because TIME_PATTERN forces zero padding.
        if (
            self.open_time is not None
            and self.close_time is not None
            and self.close_time <= self.open_time
        ):
            raise ValueError("close_time must be later than open_time")
        return self


class SocialLinks(StrictTextModel):
    """Social profile URLs.

    ``extra="allow"`` keeps the model extensible: a new network can be added
    later without touching the document shape. Values must still be absolute
    http(s) URLs, which ``AnyHttpUrl`` enforces on the declared fields.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")

    facebook: AnyHttpUrl | None = None
    instagram: AnyHttpUrl | None = None
    whatsapp: AnyHttpUrl | None = None
    x: AnyHttpUrl | None = None
    youtube: AnyHttpUrl | None = None
    linkedin: AnyHttpUrl | None = None
    tiktok: AnyHttpUrl | None = None


#: Phone numbers are stored as entered by the business, because formatting
#: conventions vary by country. What is enforced is the character set: digits and
#: the punctuation that legitimately appears in a phone number. This is a
#: permissive sanity check, not a numbering-plan validator - it rejects typos and
#: pasted markup without pretending to know which country codes are real.
PHONE_PATTERN = re.compile(r"^[0-9+()\-.\s]{3,40}$")


def _validate_phone(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if not PHONE_PATTERN.match(candidate):
        raise ValueError(
            f"{field} must contain only digits and the characters + ( ) - . and spaces"
        )
    return candidate


class SiteSettingsDocument(BaseDocument):
    """Single business-wide configuration document."""

    singleton_key: str = Field(default=SINGLETON_KEY)

    # Identity
    business_name: str = Field(min_length=1, max_length=160)
    tagline: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    logo: str | None = Field(default=None, max_length=500)
    favicon: str | None = Field(default=None, max_length=500)

    # Contact
    phone: str | None = Field(default=None, max_length=40)
    whatsapp_number: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    address: Address | None = None
    opening_hours: list[OpeningHour] = Field(default_factory=list)
    social_links: SocialLinks = Field(default_factory=SocialLinks)

    # About section
    about_title: str | None = Field(default=None, max_length=200)
    about_content: str | None = Field(default=None, max_length=5000)
    about_image: str | None = Field(default=None, max_length=500)

    # Hero section
    hero_title: str | None = Field(default=None, max_length=200)
    hero_description: str | None = Field(default=None, max_length=1000)
    hero_image: str | None = Field(default=None, max_length=500)
    hero_cta_text: str | None = Field(default=None, max_length=80)
    #: Either a named in-page destination or an absolute http(s) URL. Left
    #: optional so an omitted CTA is valid; the behaviour tells the frontend
    #: which section to link to.
    hero_cta_url: str | None = Field(default=None, max_length=500)
    hero_cta_behaviour: str = Field(default="services", min_length=1, max_length=20)

    # Presentation: a curated preset id, never arbitrary CSS or a font URL.
    #
    # These are *not* validated here. This model is the storage shape, and it
    # also parses documents written by an earlier version of the application or
    # edited directly in the database. Enforcing the curated list on read would
    # mean a renamed or retired preset turned every existing document into an
    # unreadable one and took the public site down with it. The write boundary
    # (the request schemas) is where the curated list is enforced, and the
    # public config endpoint falls back to the default preset for anything
    # unrecognised.
    active_theme: str = Field(default=DEFAULT_THEME, min_length=1, max_length=80)
    active_font: str = Field(default=DEFAULT_FONT, min_length=1, max_length=80)

    #: Per-token colour overrides on top of the active preset, keyed by token
    #: name. Like ``active_theme``, this is the storage shape and is not
    #: validated against the curated table here: a document written by an older
    #: version of the app, or edited directly in the database, must still parse.
    #: The write boundary validates, and the public config endpoint filters on
    #: read through ``sanitize_overrides``.
    theme_overrides: dict[str, str] = Field(default_factory=dict)

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, value: str | None) -> str | None:
        return _validate_phone(value, "phone")

    @field_validator("whatsapp_number")
    @classmethod
    def _check_whatsapp(cls, value: str | None) -> str | None:
        return _validate_phone(value, "whatsapp_number")

    @field_validator("hero_cta_behaviour")
    @classmethod
    def _check_cta_behaviour(cls, value: str) -> str:
        if value not in CTA_BEHAVIOURS:
            raise ValueError(f"hero_cta_behaviour must be one of: {', '.join(CTA_BEHAVIOURS)}")
        return value

    @field_validator("logo", "favicon", "about_image", "hero_image", "hero_cta_url")
    @classmethod
    def _check_media_reference(cls, value: str | None) -> str | None:
        """Media references are absolute http(s) URLs, never local paths.

        A media field must point at something the browser can actually load.
        Accepting ``/static/x.png`` or ``file:///etc/passwd`` would let an
        admin store a reference the site cannot render, or one that resolves
        somewhere unexpected.
        """
        if value is None:
            return None
        candidate = value.strip()
        if not candidate:
            return None
        if not candidate.startswith(("https://", "http://")):
            raise ValueError("must be an absolute http(s) URL")
        return candidate
