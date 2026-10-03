"""Public site settings.

Reading creates the singleton document on first access, so a fresh deployment
serves a usable response with no manual seed step.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import SiteSettingsServiceDependency
from app.schemas.site_settings import SiteSettingsPublic
from app.services.base import to_response

router = APIRouter(tags=["public: site-settings"])


@router.get(
    "/site-settings",
    response_model=SiteSettingsPublic,
    summary="Read the site settings",
)
async def read_site_settings(
    service: SiteSettingsServiceDependency,
) -> SiteSettingsPublic:
    document = await service.get_or_create()
    return to_response(document, SiteSettingsPublic)
