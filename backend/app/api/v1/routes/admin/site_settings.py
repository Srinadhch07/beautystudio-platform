"""Admin site settings.

There is a single settings document, so the endpoints are an upsert pair rather
than create/read/delete. ``DELETE`` is intentionally omitted: removing the
only settings document would take the public site down with it.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import SiteSettingsServiceDependency
from app.schemas.site_settings import SiteSettingsPatch, SiteSettingsPublic, SiteSettingsUpsert
from app.services.base import to_response

router = APIRouter(prefix="/site-settings", tags=["admin: site-settings"])


@router.get(
    "",
    response_model=SiteSettingsPublic,
    summary="Read the site settings",
)
async def read_site_settings(
    service: SiteSettingsServiceDependency,
) -> SiteSettingsPublic:
    document = await service.get_or_create()
    return to_response(document, SiteSettingsPublic)


@router.put(
    "",
    response_model=SiteSettingsPublic,
    summary="Create or replace the site settings",
)
async def replace_site_settings(
    payload: SiteSettingsUpsert,
    service: SiteSettingsServiceDependency,
) -> SiteSettingsPublic:
    document = await service.upsert(payload)
    return to_response(document, SiteSettingsPublic)


@router.patch(
    "",
    response_model=SiteSettingsPublic,
    summary="Partially update the site settings",
)
async def patch_site_settings(
    payload: SiteSettingsPatch,
    service: SiteSettingsServiceDependency,
) -> SiteSettingsPublic:
    document = await service.patch(payload)
    return to_response(document, SiteSettingsPublic)
