"""Site settings request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.fonts import DEFAULT_FONT, FONT_PRESETS, is_known_font
from app.core.themes import (
    DEFAULT_THEME,
    OVERRIDABLE_TOKENS,
    THEME_PRESETS,
    is_hex_color,
    is_known_theme,
)
from app.models.base import PyObjectId
from app.models.site_settings import (
    CTA_BEHAVIOURS,
    Address,
    OpeningHour,
    SocialLinks,
)

#: Shared media-reference and curated-id fields, declared once so the write
#: schemas cannot drift apart.
_MEDIA_FIELD = Field(default=None, max_length=500)
_THEME_FIELD = Field(default=None, min_length=1, max_length=80)
_FONT_FIELD = Field(default=None, min_length=1, max_length=80)


class SiteSettingsBase(BaseModel):
    """Fields an administrator may write.

    Every field is optional so the same base serves both the full replace and
    the partial patch; the individual schemas tighten what they need.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    business_name: str | None = Field(default=None, min_length=1, max_length=160)
    tagline: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    logo: str | None = _MEDIA_FIELD
    favicon: str | None = _MEDIA_FIELD
    phone: str | None = Field(default=None, max_length=40)
    whatsapp_number: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    address: Address | None = None
    opening_hours: list[OpeningHour] | None = None
    social_links: SocialLinks | None = None
    about_title: str | None = Field(default=None, max_length=200)
    about_content: str | None = Field(default=None, max_length=5000)
    about_image: str | None = _MEDIA_FIELD
    hero_title: str | None = Field(default=None, max_length=200)
    hero_description: str | None = Field(default=None, max_length=1000)
    hero_image: str | None = _MEDIA_FIELD
    hero_cta_text: str | None = Field(default=None, max_length=80)
    hero_cta_url: str | None = _MEDIA_FIELD
    hero_cta_behaviour: str | None = Field(default=None, max_length=20)
    active_theme: str | None = _THEME_FIELD
    active_font: str | None = _FONT_FIELD
    theme_overrides: dict[str, str] = Field(default_factory=dict)

    @field_validator("active_theme")
    @classmethod
    def _check_theme(cls, value: str | None) -> str | None:
        """Only a curated preset id may be stored.

        Enforced here rather than on the document because this is the write
        boundary. There is deliberately no free-form CSS, stylesheet URL or
        ``font-family`` field anywhere in the schema, so presentation cannot be
        expressed as arbitrary code.
        """
        if value is not None and not is_known_theme(value):
            raise ValueError(
                f"active_theme must be one of: {', '.join(theme.id for theme in THEME_PRESETS)}"
            )
        return value

    @field_validator("active_font")
    @classmethod
    def _check_font(cls, value: str | None) -> str | None:
        """Only a curated font pairing id may be stored."""
        if value is not None and not is_known_font(value):
            raise ValueError(
                f"active_font must be one of: {', '.join(font.id for font in FONT_PRESETS)}"
            )
        return value

    @field_validator("hero_cta_behaviour")
    @classmethod
    def _check_cta_behaviour(cls, value: str | None) -> str | None:
        """A closed set, so the frontend can rely on the value's shape."""
        if value is not None and value not in CTA_BEHAVIOURS:
            raise ValueError(f"hero_cta_behaviour must be one of: {', '.join(CTA_BEHAVIOURS)}")
        return value

    @field_validator("theme_overrides")
    @classmethod
    def _check_theme_overrides(cls, value: dict[str, str]) -> dict[str, str]:
        """Colour overrides are restricted to known colour tokens and hex values.

        This is the write boundary and the only place overrides are trusted. It
        keeps arbitrary CSS - a ``url(...)``, a ``;`` or a second declaration -
        from ever being stored as a token value.
        """
        for name, color in value.items():
            if name not in OVERRIDABLE_TOKENS:
                raise ValueError(
                    f"theme_overrides keys must be one of: {', '.join(OVERRIDABLE_TOKENS)}"
                )
            if not is_hex_color(color):
                raise ValueError(
                    f"theme_overrides[{name}] must be a hex colour such as #B76E79"
                )
        return value


class SiteSettingsUpsert(SiteSettingsBase):
    """Full replacement payload for the single settings document.

    ``business_name`` is required because a settings document must always have
    a usable identity. The presentation fields fall back to the curated
    defaults rather than to empty strings.
    """

    business_name: str = Field(min_length=1, max_length=160)
    active_theme: str = Field(default=DEFAULT_THEME, min_length=1, max_length=80)
    active_font: str = Field(default=DEFAULT_FONT, min_length=1, max_length=80)
    hero_cta_behaviour: str = Field(default="services", max_length=20)


class SiteSettingsPatch(SiteSettingsBase):
    """Partial update. Omitted fields keep their stored value.

    The service merges the supplied fields over the stored document and
    revalidates the result, so a ``null``-cleared required field is still
    rejected and a cleared curated id falls back through the document defaults.
    """


class SiteSettingsPublic(BaseModel):
    """Public representation of the site settings.

    Everything in the document is safe to publish - the settings record holds no
    secrets, only business content. Secrets live in environment variables and
    never in this collection, which is what makes this whole object publishable.
    """

    model_config = ConfigDict(from_attributes=True)

    id: PyObjectId
    business_name: str
    tagline: str | None = None
    description: str | None = None
    logo: str | None = None
    favicon: str | None = None
    phone: str | None = None
    whatsapp_number: str | None = None
    email: EmailStr | None = None
    address: Address | None = None
    opening_hours: list[OpeningHour] = Field(default_factory=list)
    social_links: SocialLinks = Field(default_factory=SocialLinks)
    about_title: str | None = None
    about_content: str | None = None
    about_image: str | None = None
    hero_title: str | None = None
    hero_description: str | None = None
    hero_image: str | None = None
    hero_cta_text: str | None = None
    hero_cta_url: str | None = None
    hero_cta_behaviour: str = "services"
    active_theme: str = DEFAULT_THEME
    active_font: str = DEFAULT_FONT
    theme_overrides: dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


#: Re-exported so the route layer and OpenAPI can name the allowed values.
__all__ = [
    "CTA_BEHAVIOURS",
    "SiteSettingsBase",
    "SiteSettingsPatch",
    "SiteSettingsPublic",
    "SiteSettingsUpsert",
]
