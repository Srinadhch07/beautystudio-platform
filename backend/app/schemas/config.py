"""Public site-configuration response.

This is the single payload the future React site boots from: business identity,
contact details, social links, the active theme and font, and the hero and about
sections in one request.

The security property that matters is **what is not here**. Nothing in this
response is sourced from environment configuration other than what is explicitly
copied below, so there is no path by which a JWT secret, an AWS credential, an
SMTP password or a MongoDB URI could reach it. Secrets are held in the process
environment and are never written to the database, so they cannot be read out of
a document either.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.fonts import FontPreset
from app.core.themes import ThemePreset, resolve_theme_tokens
from app.models.site_settings import (
    Address,
    OpeningHour,
    SocialLinks,
)


class PublicTheme(BaseModel):
    """The active theme, resolved to its full token set.

    The frontend receives resolved tokens rather than an id to look up, so a
    cached page needs a single request to style itself.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    tokens: dict[str, str] = Field(default_factory=dict)


class PublicFont(BaseModel):
    """The active font pairing, resolved to CSS-ready stacks."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    heading_family: str
    body_family: str
    heading_stack: str
    body_stack: str
    href: str


class PublicHero(BaseModel):
    """Hero section content and its call to action."""

    model_config = ConfigDict(from_attributes=True)

    title: str | None = None
    description: str | None = None
    image: str | None = None
    cta_text: str | None = None
    cta_url: str | None = None
    cta_behaviour: str = "services"


class PublicAbout(BaseModel):
    """About section content."""

    model_config = ConfigDict(from_attributes=True)

    title: str | None = None
    content: str | None = None
    image: str | None = None


class PublicContact(BaseModel):
    """How the business can be reached."""

    model_config = ConfigDict(from_attributes=True)

    phone: str | None = None
    whatsapp_number: str | None = None
    email: EmailStr | None = None
    address: Address | None = None
    opening_hours: list[OpeningHour] = Field(default_factory=list)


class PublicIdentity(BaseModel):
    """Business name, tagline, description and brand media."""

    model_config = ConfigDict(from_attributes=True)

    business_name: str
    tagline: str | None = None
    description: str | None = None
    logo: str | None = None
    favicon: str | None = None


class PublicConfig(BaseModel):
    """Everything the public website needs, in one document."""

    model_config = ConfigDict(from_attributes=True)

    identity: PublicIdentity
    contact: PublicContact
    social_links: SocialLinks = Field(default_factory=SocialLinks)
    hero: PublicHero = Field(default_factory=PublicHero)
    about: PublicAbout = Field(default_factory=PublicAbout)
    theme: PublicTheme
    font: PublicFont


class ThemeCatalogueEntry(BaseModel):
    """One selectable theme, as offered to the admin UI."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    tokens: dict[str, str]


class FontCatalogueEntry(BaseModel):
    """One selectable font pairing, as offered to the admin UI."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    heading_family: str
    body_family: str
    heading_stack: str
    body_stack: str
    href: str


def theme_to_public(
    preset: ThemePreset, overrides: Mapping[str, str] | None = None
) -> PublicTheme:
    """Project a preset onto the public theme shape.

    Any administrator colour overrides are merged over the preset's own tokens,
    so the frontend receives the effective palette and needs no second lookup.
    """
    data = preset.as_dict()
    data["tokens"] = resolve_theme_tokens(preset, overrides)
    return PublicTheme.model_validate(data)


def font_to_public(preset: FontPreset) -> PublicFont:
    """Project a preset onto the public font shape."""
    return PublicFont.model_validate(preset.as_dict())
