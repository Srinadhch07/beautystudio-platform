"""Public offers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import OfferServiceDependency
from app.core.parsing import parse_object_id
from app.schemas.common import Page, PaginationDependency
from app.schemas.offers import OfferPublic
from app.services.base import page_to_response, to_response

router = APIRouter(tags=["public: offers"])


@router.get(
    "/offers",
    response_model=Page[OfferPublic],
    summary="List active offers",
)
async def list_offers(
    params: PaginationDependency,
    service: OfferServiceDependency,
) -> Page[OfferPublic]:
    page = await service.list_active(skip=params.skip, limit=params.limit)
    return page_to_response(page, OfferPublic)


@router.get(
    "/offers/{offer_id}",
    response_model=OfferPublic,
    summary="Read a single active offer",
)
async def read_offer(
    offer_id: str,
    service: OfferServiceDependency,
) -> OfferPublic:
    document = await service.get_public(parse_object_id(offer_id, field="offer_id"))
    return to_response(document, OfferPublic)
