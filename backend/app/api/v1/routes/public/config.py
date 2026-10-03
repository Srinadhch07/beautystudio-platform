"""Public site configuration, theme catalogue and font catalogue.

Three read-only, unauthenticated endpoints that together let the future React
site boot from the API alone: the merged configuration, the list of selectable
themes, and the list of selectable fonts.

Nothing here reads environment configuration, so no credential can reach a
response - the payloads are built purely from the site settings document and the
curated preset tables.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import SiteSettingsServiceDependency
from app.core.fonts import FONT_CATALOGUE
from app.core.themes import THEME_CATALOGUE
from app.schemas.config import (
    FontCatalogueEntry,
    PublicConfig,
    ThemeCatalogueEntry,
)

router = APIRouter(tags=["public: configuration"])


@router.get(
    "/config",
    response_model=PublicConfig,
    summary="Everything the public site needs, in one response",
)
async def read_config(service: SiteSettingsServiceDependency) -> PublicConfig:
    """Identity, contact, social links, hero, about, theme and font.

    This is the intended single request for a cold page load: it avoids the
    frontend having to fetch the settings and then resolve a theme id against a
    second catalogue call.
    """
    return await service.build_public_config()


@router.get(
    "/themes",
    response_model=list[ThemeCatalogueEntry],
    summary="List the available theme presets",
)
async def list_themes() -> list[ThemeCatalogueEntry]:
    """The curated theme shortlist, with resolved design tokens.

    Public on purpose: the website has to be able to render a theme, and this
    contains nothing but colours and corner radii.
    """
    return [ThemeCatalogueEntry.model_validate(entry) for entry in THEME_CATALOGUE]


@router.get(
    "/fonts",
    response_model=list[FontCatalogueEntry],
    summary="List the available font presets",
)
async def list_fonts() -> list[FontCatalogueEntry]:
    """The five curated font pairings, with CSS-ready family stacks."""
    return [FontCatalogueEntry.model_validate(entry) for entry in FONT_CATALOGUE]
