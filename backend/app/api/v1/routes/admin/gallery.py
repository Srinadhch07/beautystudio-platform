"""Admin gallery management.

Image uploads are not implemented: ``s3_key`` is stored as supplied.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.api.deps import GalleryServiceDependency
from app.core.parsing import parse_object_id
from app.schemas.common import Page, PaginationDependency, ReorderRequest, ReorderResponse
from app.schemas.gallery import GalleryAdmin, GalleryCreate, GalleryUpdate
from app.services.base import page_to_response, to_response

router = APIRouter(prefix="/gallery", tags=["admin: gallery"])


@router.get("", response_model=Page[GalleryAdmin], summary="List every gallery item")
async def list_gallery(
    params: PaginationDependency,
    service: GalleryServiceDependency,
) -> Page[GalleryAdmin]:
    page = await service.list_all(skip=params.skip, limit=params.limit)
    return page_to_response(page, GalleryAdmin)


@router.put("/order", response_model=ReorderResponse, summary="Reorder gallery items")
async def reorder_gallery(
    payload: ReorderRequest,
    service: GalleryServiceDependency,
) -> ReorderResponse:
    return ReorderResponse(updated=await service.reorder(payload))


@router.post(
    "",
    response_model=GalleryAdmin,
    status_code=status.HTTP_201_CREATED,
    summary="Create a gallery item",
)
async def create_gallery_item(
    payload: GalleryCreate,
    service: GalleryServiceDependency,
) -> GalleryAdmin:
    document = await service.create(payload)
    return to_response(document, GalleryAdmin)


@router.get("/{item_id}", response_model=GalleryAdmin, summary="Read a gallery item")
async def read_gallery_item(
    item_id: str,
    service: GalleryServiceDependency,
) -> GalleryAdmin:
    document = await service.get(parse_object_id(item_id, field="item_id"))
    return to_response(document, GalleryAdmin)


@router.patch("/{item_id}", response_model=GalleryAdmin, summary="Update a gallery item")
async def update_gallery_item(
    item_id: str,
    payload: GalleryUpdate,
    service: GalleryServiceDependency,
) -> GalleryAdmin:
    document = await service.update(parse_object_id(item_id, field="item_id"), payload)
    return to_response(document, GalleryAdmin)


@router.patch(
    "/{item_id}/active",
    response_model=GalleryAdmin,
    summary="Activate or deactivate a gallery item",
)
async def set_gallery_item_active(
    item_id: str,
    is_active: bool,
    service: GalleryServiceDependency,
) -> GalleryAdmin:
    document = await service.set_active(parse_object_id(item_id, field="item_id"), is_active)
    return to_response(document, GalleryAdmin)


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a gallery item",
)
async def delete_gallery_item(
    item_id: str,
    service: GalleryServiceDependency,
) -> Response:
    await service.delete(parse_object_id(item_id, field="item_id"))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
