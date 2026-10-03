"""Site settings business logic.

There is exactly one settings document. It is created on first read, so the
public endpoint works on a brand new installation without a seed script.
"""

from __future__ import annotations

from app.core.config import Settings
from app.core.fonts import DEFAULT_FONT, FONTS_BY_ID
from app.core.themes import DEFAULT_THEME, THEMES_BY_ID
from app.models.site_settings import SiteSettingsDocument
from app.repositories.site_settings import SiteSettingsRepository
from app.schemas.config import (
    PublicAbout,
    PublicConfig,
    PublicContact,
    PublicHero,
    PublicIdentity,
    font_to_public,
    theme_to_public,
)
from app.schemas.site_settings import SiteSettingsPatch, SiteSettingsUpsert


class SiteSettingsService:
    """Read and upsert the singleton settings document."""

    def __init__(self, repository: SiteSettingsRepository, app_settings: Settings) -> None:
        self._repository = repository
        self._app_settings = app_settings

    async def get_or_create(self) -> SiteSettingsDocument:
        """Return the settings, seeding them from ``APP_NAME`` on first access."""
        return await self._repository.get_or_create(self._app_settings.app_name)

    async def upsert(self, payload: SiteSettingsUpsert) -> SiteSettingsDocument:
        """Create or fully replace the settings document."""
        return await self._repository.replace(payload.model_dump(mode="python"))

    async def patch(self, payload: SiteSettingsPatch) -> SiteSettingsDocument:
        """Partially update the settings, creating it if it does not exist yet.

        The patch is merged over the stored values and revalidated, so a caller
        cannot clear a required field or break an opening-hours entry by patching
        one field in isolation.
        """
        changes = payload.model_dump(mode="python", exclude_unset=True)
        if not changes:
            return await self.get_or_create()

        current = await self._repository.find_singleton()
        if current is None:
            # Seed the full default shape first so the stored document always
            # carries theme/font defaults, then apply the caller's changes.
            current = await self.get_or_create()

        merged = {**current.model_dump(mode="python", exclude={"id"}), **changes}
        # Raises pydantic.ValidationError -> 422 via the registered handler.
        SiteSettingsDocument.model_validate(merged)
        return await self._repository.replace(merged)

    async def build_public_config(self) -> PublicConfig:
        """Assemble the one-shot configuration document for the public site.

        The theme and font are resolved from their curated tables rather than
        returned as bare ids, so the frontend can style a page from this single
        response.

        Resolution is defensive: a stored id that is not in the table (a document
        written before the preset list existed, or edited directly in the
        database) falls back to the default preset instead of raising. A
        styling regression is a far better failure than a 500 on the public
        configuration endpoint.
        """
        document = await self.get_or_create()

        theme = THEMES_BY_ID.get(document.active_theme) or THEMES_BY_ID[DEFAULT_THEME]
        font = FONTS_BY_ID.get(document.active_font) or FONTS_BY_ID[DEFAULT_FONT]

        return PublicConfig(
            identity=PublicIdentity(
                business_name=document.business_name,
                tagline=document.tagline,
                description=document.description,
                logo=document.logo,
                favicon=document.favicon,
            ),
            contact=PublicContact(
                phone=document.phone,
                whatsapp_number=document.whatsapp_number,
                email=document.email,
                address=document.address,
                opening_hours=document.opening_hours,
            ),
            social_links=document.social_links,
            hero=PublicHero(
                title=document.hero_title,
                description=document.hero_description,
                image=document.hero_image,
                cta_text=document.hero_cta_text,
                cta_url=document.hero_cta_url,
                cta_behaviour=document.hero_cta_behaviour,
            ),
            about=PublicAbout(
                title=document.about_title,
                content=document.about_content,
                image=document.about_image,
            ),
            theme=theme_to_public(theme, document.theme_overrides),
            font=font_to_public(font),
        )
