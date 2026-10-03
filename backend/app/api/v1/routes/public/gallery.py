"""Public gallery."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import GalleryServiceDependency
from app.core.parsing import parse_object_id
from app.schemas.common import Page, PaginationDependency
from app.schemas.gallery import GalleryPublic
from app.services.base import page_to_response, to_response

router = APIRouter(tags=["public: gallery"])


@router.get(
    "/gallery",
    response_model=Page[GalleryPublic],
    summary="List active gallery items",
)
async def list_gallery(
    params: PaginationDependency,
    service: GalleryServiceDependency,
) -> Page[GalleryPublic]:
    page = await service.list_active(skip=params.skip, limit=params.limit)
    return page_to_response(page, GalleryPublic)


@router.get(
    "/gallery/{item_id}",
    response_model=GalleryPublic,
    summary="Read a single active gallery item",
)
async def read_gallery_item(
    item_id: str,
    service: GalleryServiceDependency,
) -> GalleryPublic:
    document = await service.get_public(parse_object_id(item_id, field="item_id"))
    return to_response(document, GalleryPublic)
