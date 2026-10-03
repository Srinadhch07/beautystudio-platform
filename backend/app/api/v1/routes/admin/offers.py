"""Admin offer management."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.api.deps import OfferServiceDependency
from app.core.parsing import parse_object_id
from app.schemas.common import Page, PaginationDependency, ReorderRequest, ReorderResponse
from app.schemas.offers import OfferCreate, OfferPublic, OfferUpdate
from app.services.base import page_to_response, to_response

router = APIRouter(prefix="/offers", tags=["admin: offers"])


@router.get("", response_model=Page[OfferPublic], summary="List every offer")
async def list_offers(
    params: PaginationDependency,
    service: OfferServiceDependency,
) -> Page[OfferPublic]:
    page = await service.list_all(skip=params.skip, limit=params.limit)
    return page_to_response(page, OfferPublic)


@router.put("/order", response_model=ReorderResponse, summary="Reorder offers")
async def reorder_offers(
    payload: ReorderRequest,
    service: OfferServiceDependency,
) -> ReorderResponse:
    return ReorderResponse(updated=await service.reorder(payload))


@router.post(
    "",
    response_model=OfferPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create an offer",
)
async def create_offer(
    payload: OfferCreate,
    service: OfferServiceDependency,
) -> OfferPublic:
    document = await service.create(payload)
    return to_response(document, OfferPublic)


@router.get("/{offer_id}", response_model=OfferPublic, summary="Read an offer")
async def read_offer(
    offer_id: str,
    service: OfferServiceDependency,
) -> OfferPublic:
    document = await service.get(parse_object_id(offer_id, field="offer_id"))
    return to_response(document, OfferPublic)


@router.patch("/{offer_id}", response_model=OfferPublic, summary="Update an offer")
async def update_offer(
    offer_id: str,
    payload: OfferUpdate,
    service: OfferServiceDependency,
) -> OfferPublic:
    document = await service.update(parse_object_id(offer_id, field="offer_id"), payload)
    return to_response(document, OfferPublic)


@router.patch(
    "/{offer_id}/active",
    response_model=OfferPublic,
    summary="Activate or deactivate an offer",
)
async def set_offer_active(
    offer_id: str,
    is_active: bool,
    service: OfferServiceDependency,
) -> OfferPublic:
    document = await service.set_active(parse_object_id(offer_id, field="offer_id"), is_active)
    return to_response(document, OfferPublic)


@router.delete(
    "/{offer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an offer",
)
async def delete_offer(
    offer_id: str,
    service: OfferServiceDependency,
) -> Response:
    await service.delete(parse_object_id(offer_id, field="offer_id"))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
